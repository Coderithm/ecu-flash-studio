#!/usr/bin/env python3
"""
hex_parsing.py

Generate a profile-driven UDS flashing trace from Intel HEX files.

This script does not modify the existing parser or overwrite existing .asc
outputs. It reads .hex files from the local firmware folder and writes new
trace files next to this script using the suffix "_uds.asc".

Implemented features:
- Address-aware Intel HEX parsing
- Profile-driven CAN, UDS, timing, and routine configuration
- Optional plugin-based seed-key computation
- ISO-TP segmentation with configurable FlowControl block size and STmin
- Simulated UDS session flow, flashing services, positive responses
- Simulated ResponsePending and TesterPresent behavior for long operations

Notes:
- This is still a simulated trace generator, not a live flashing tool.
- OEM-exact behavior still depends on the accuracy of the selected profile
  and any custom plugin logic referenced by that profile.
"""

from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import importlib.util
import json
import os
import sys
try:
    from core.verify_trace import parse_asc_transfer_data
except ImportError:
    from verify_trace import parse_asc_transfer_data
import uuid
from dataclasses import dataclass


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
FIRMWARE_DIR = os.path.join(ROOT_DIR, "firmware")
OUTPUT_DIR = ROOT_DIR
PROFILE_DIR = os.path.join(ROOT_DIR, "profiles")
PLUGIN_DIR = os.path.join(ROOT_DIR, "profile_plugins")
DEFAULT_PROFILE = os.path.join(PROFILE_DIR, "mahindra_template.json")


def crc16_ccitt(data: bytes, init: int = 0xFFFF) -> int:
    """CRC-16/CCITT (x^16 + x^12 + x^5 + 1) used by Mahindra checksum verify."""
    crc = init
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc = crc << 1
            crc &= 0xFFFF
    return crc


@dataclass
class MemorySegment:
    start: int
    data: bytes

    @property
    def end(self) -> int:
        return self.start + len(self.data) - 1


@dataclass
class TraceFrame:
    timestamp: float
    can_id: str
    direction: str
    data: list[int]
    comment: str = ""


@dataclass
class MemoryRegion:
    name: str
    start: int
    end: int
    erase_before_download: bool = True


@dataclass
class RuntimeContext:
    profile: dict
    request_id: str
    response_id: str
    functional_id: str
    channel: int
    frame_interval: float
    pad_byte: int
    fc_block_size: int
    fc_stmin: int
    max_frame_data_length: int
    allow_response_pending: bool
    response_pending_nrc: int
    p2_timeout_ms: int
    tester_present_enabled: bool
    tester_present_interval_ms: int
    tester_present_can_id: str
    tester_present_request: bytes
    tester_present_response: bytes
    transfer_payload_bytes: int
    transfer_wait_positive_response: bool
    block_sequence_start: int
    block_sequence_rollover: int
    negative_response_service: int
    seed_key_function: object | None
    memory_regions: list[MemoryRegion]
    session_timing_bytes: bytes


def _require_hex_byte(value: str, field_name: str) -> int:
    try:
        result = int(value, 16)
    except ValueError as exc:
        raise ValueError(f"Invalid hex byte for {field_name}: {value}") from exc

    if not 0 <= result <= 0xFF:
        raise ValueError(f"Hex byte out of range for {field_name}: {value}")
    return result


def _hex_to_bytes(value: str, field_name: str) -> bytes:
    cleaned = value.replace(" ", "")
    if len(cleaned) % 2 != 0:
        raise ValueError(f"Hex string for {field_name} must have even length: {value}")
    try:
        return bytes.fromhex(cleaned)
    except ValueError as exc:
        raise ValueError(f"Invalid hex string for {field_name}: {value}") from exc


def _parse_hex_line(line: str, lineno: int) -> tuple[int, int, int, str, int]:
    if not line.startswith(":"):
        raise ValueError(f"Line {lineno}: expected Intel HEX record")

    try:
        byte_count = int(line[1:3], 16)
        load_offset = int(line[3:7], 16)
        record_type = int(line[7:9], 16)
        data_field = line[9 : 9 + byte_count * 2]
        checksum_rx = int(line[9 + byte_count * 2 : 11 + byte_count * 2], 16)
    except (ValueError, IndexError) as exc:
        raise ValueError(f"Line {lineno}: malformed record - {exc}") from exc

    raw_bytes = bytes.fromhex(line[1 : 9 + byte_count * 2])
    checksum_calc = (256 - (sum(raw_bytes) % 256)) % 256
    if checksum_calc != checksum_rx:
        raise ValueError(
            f"Line {lineno}: checksum mismatch "
            f"(calc=0x{checksum_calc:02X}, file=0x{checksum_rx:02X})"
        )

    return byte_count, load_offset, record_type, data_field, checksum_rx


def parse_intel_hex_segments(filepath: str) -> list[MemorySegment]:
    """
    Parse Intel HEX while preserving actual address segments.

    A new segment is created whenever there is a gap in the address space.
    """
    memory: dict[int, int] = {}
    extended_address = 0

    with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
        for lineno, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line:
                continue

            byte_count, load_offset, record_type, data_field, _ = _parse_hex_line(line, lineno)

            if record_type == 0x00:
                abs_addr = extended_address + load_offset
                for i, value in enumerate(bytes.fromhex(data_field)):
                    memory[abs_addr + i] = value
            elif record_type == 0x01:
                break
            elif record_type == 0x02:
                extended_address = int(data_field, 16) << 4
            elif record_type == 0x04:
                extended_address = int(data_field, 16) << 16
            elif record_type in (0x03, 0x05):
                pass
            else:
                raise ValueError(f"Line {lineno}: unsupported record type 0x{record_type:02X}")

    if not memory:
        raise ValueError("HEX file contains no data records")

    segments: list[MemorySegment] = []
    sorted_items = sorted(memory.items())

    start_addr = sorted_items[0][0]
    current_bytes = bytearray([sorted_items[0][1]])
    prev_addr = start_addr

    for addr, value in sorted_items[1:]:
        if addr == prev_addr + 1:
            current_bytes.append(value)
        else:
            segments.append(MemorySegment(start=start_addr, data=bytes(current_bytes)))
            start_addr = addr
            current_bytes = bytearray([value])
        prev_addr = addr

    segments.append(MemorySegment(start=start_addr, data=bytes(current_bytes)))
    return segments


def _parse_memory_regions(profile: dict) -> list[MemoryRegion]:
    regions_cfg = profile.get("memory", {}).get("regions", [])
    regions: list[MemoryRegion] = []
    for index, region in enumerate(regions_cfg, start=1):
        try:
            start = int(region["start"], 16)
            end = int(region["end"], 16)
        except (KeyError, ValueError) as exc:
            raise ValueError(f"Invalid memory region entry at index {index}") from exc
        if end < start:
            raise ValueError(f"Memory region {region.get('name', index)} has end < start")
        regions.append(
            MemoryRegion(
                name=region.get("name", f"region_{index}"),
                start=start,
                end=end,
                erase_before_download=bool(region.get("erase_before_download", True)),
            )
        )
    return regions


def _segment_intersects_region(segment: MemorySegment, region: MemoryRegion) -> bool:
    return segment.start <= region.end and segment.end >= region.start


def select_flash_segments(segments: list[MemorySegment], ctx: RuntimeContext) -> list[MemorySegment]:
    if not ctx.memory_regions:
        return segments

    selected: list[MemorySegment] = []
    for segment in segments:
        if any(_segment_intersects_region(segment, region) for region in ctx.memory_regions):
            selected.append(segment)
    if not selected:
        raise ValueError("No parsed HEX segments intersect the configured memory regions")
    return selected


def segment_regions(segment: MemorySegment, ctx: RuntimeContext) -> list[MemoryRegion]:
    if not ctx.memory_regions:
        return []
    return [region for region in ctx.memory_regions if _segment_intersects_region(segment, region)]


def segment_needs_erase(segment: MemorySegment, ctx: RuntimeContext) -> bool:
    regions = segment_regions(segment, ctx)
    if not regions:
        return True
    return any(region.erase_before_download for region in regions)


def pad_classic_can(frame_bytes: list[int], pad_byte: int) -> list[int]:
    if len(frame_bytes) > 8:
        raise ValueError("Classic CAN frame cannot exceed 8 bytes")
    return frame_bytes + [pad_byte] * (8 - len(frame_bytes))


def isotp_encode(payload: bytes, pad_byte: int) -> list[list[int]]:
    """
    Encode a full UDS payload into classic CAN ISO-TP frames.
    """
    if len(payload) <= 7:
        return [pad_classic_can([len(payload)] + list(payload), pad_byte)]

    if len(payload) > 0xFFF:
        raise ValueError("Payload too large for 12-bit ISO-TP First Frame length")

    frames: list[list[int]] = []
    ff = [0x10 | ((len(payload) >> 8) & 0x0F), len(payload) & 0xFF] + list(payload[:6])
    frames.append(pad_classic_can(ff, pad_byte))

    seq_num = 1
    offset = 6
    while offset < len(payload):
        cf_data = [0x20 | (seq_num & 0x0F)] + list(payload[offset : offset + 7])
        frames.append(pad_classic_can(cf_data, pad_byte))
        offset += 7
        seq_num = (seq_num + 1) & 0x0F

    return frames


def format_asc_date(now: dt.datetime) -> str:
    ms = now.microsecond // 1000
    date_str = now.strftime(f"%a %b %d %I:%M:%S.{ms:03d} %p %Y").lower()
    return date_str[0].upper() + date_str[1:4].lower() + date_str[4].upper() + date_str[5:]


def append_frame(
    trace: list[TraceFrame],
    can_id: str,
    direction: str,
    data: list[int],
    timestamp: float,
    frame_interval: float,
    comment: str = "",
) -> float:
    trace.append(
        TraceFrame(timestamp=timestamp, can_id=can_id, direction=direction, data=data, comment=comment)
    )
    return timestamp + frame_interval


def append_isotp_message(
    trace: list[TraceFrame],
    payload: bytes,
    can_id: str,
    direction: str,
    timestamp: float,
    frame_interval: float,
    pad_byte: int,
    comment_prefix: str,
) -> float:
    frames = isotp_encode(payload, pad_byte)
    for index, frame in enumerate(frames):
        suffix = "SF" if len(frames) == 1 else ("FF" if index == 0 else f"CF{index}")
        timestamp = append_frame(
            trace=trace,
            can_id=can_id,
            direction=direction,
            data=frame,
            timestamp=timestamp,
            frame_interval=frame_interval,
            comment=f"{comment_prefix} {suffix}",
        )
    return timestamp


def add_delay(trace: list[TraceFrame], ctx: RuntimeContext, timestamp: float, delay_ms: int) -> float:
    """
    Advance simulated time while injecting TesterPresent traffic when enabled.
    """
    remaining = max(delay_ms, 0)
    if not ctx.tester_present_enabled or ctx.tester_present_interval_ms <= 0:
        return timestamp + (remaining / 1000.0)

    interval = ctx.tester_present_interval_ms
    while remaining >= interval:
        timestamp += interval / 1000.0
        timestamp = append_isotp_message(
            trace=trace,
            payload=ctx.tester_present_request,
            can_id=ctx.tester_present_can_id,
            direction="Tx",
            timestamp=timestamp,
            frame_interval=ctx.frame_interval,
            pad_byte=ctx.pad_byte,
            comment_prefix="TesterPresent",
        )
        suppress_tp = (
            len(ctx.tester_present_request) >= 2
            and (ctx.tester_present_request[1] & 0x80) != 0
        )
        if not suppress_tp:
            timestamp = append_isotp_message(
                trace=trace,
                payload=ctx.tester_present_response,
                can_id=ctx.response_id,
                direction="Rx",
                timestamp=timestamp,
                frame_interval=ctx.frame_interval,
                pad_byte=ctx.pad_byte,
                comment_prefix="TesterPresent positive response",
            )
        remaining -= interval

    return timestamp + (remaining / 1000.0)


def maybe_emit_response_pending(
    trace: list[TraceFrame],
    ctx: RuntimeContext,
    timestamp: float,
    request_sid: int,
    response_comment: str,
    delay_ms: int,
) -> float:
    if not ctx.allow_response_pending or delay_ms <= ctx.p2_timeout_ms:
        return timestamp

    pending_payload = bytes([ctx.negative_response_service, request_sid, ctx.response_pending_nrc])
    return append_isotp_message(
        trace=trace,
        payload=pending_payload,
        can_id=ctx.response_id,
        direction="Rx",
        timestamp=timestamp,
        frame_interval=ctx.frame_interval,
        pad_byte=ctx.pad_byte,
        comment_prefix=f"{response_comment} ResponsePending",
    )


def append_request_response(
    trace: list[TraceFrame],
    ctx: RuntimeContext,
    request_payload: bytes,
    response_payload: bytes,
    timestamp: float,
    request_comment: str,
    response_comment: str,
    response_delay_ms: int = 0,
    request_can_id: str | None = None,
    suppress_positive_response: bool = False,
) -> float:
    tx_can_id = request_can_id or ctx.request_id
    request_frames = isotp_encode(request_payload, ctx.pad_byte)
    cf_burst_size = ctx.fc_block_size if ctx.fc_block_size > 0 else len(request_frames)
    cf_sent_since_fc = 0

    if len(request_frames) == 1:
        timestamp = append_frame(
            trace=trace,
            can_id=tx_can_id,
            direction="Tx",
            data=request_frames[0],
            timestamp=timestamp,
            frame_interval=ctx.frame_interval,
            comment=f"{request_comment} SF",
        )
    else:
        timestamp = append_frame(
            trace=trace,
            can_id=tx_can_id,
            direction="Tx",
            data=request_frames[0],
            timestamp=timestamp,
            frame_interval=ctx.frame_interval,
            comment=f"{request_comment} FF",
        )
        timestamp = append_frame(
            trace=trace,
            can_id=ctx.response_id,
            direction="Rx",
            data=[0x30, ctx.fc_block_size & 0xFF, ctx.fc_stmin & 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00],
            timestamp=timestamp,
            frame_interval=ctx.frame_interval,
            comment=f"{request_comment} FlowControl",
        )
        for index, frame in enumerate(request_frames[1:], start=1):
            timestamp = append_frame(
                trace=trace,
                can_id=tx_can_id,
                direction="Tx",
                data=frame,
                timestamp=timestamp,
                frame_interval=ctx.frame_interval,
                comment=f"{request_comment} CF{index}",
            )
            cf_sent_since_fc += 1
            if ctx.fc_stmin > 0:
                timestamp += ctx.fc_stmin / 1000.0
            more_frames_left = index < len(request_frames) - 1
            if ctx.fc_block_size > 0 and more_frames_left and cf_sent_since_fc >= cf_burst_size:
                timestamp = append_frame(
                    trace=trace,
                    can_id=ctx.response_id,
                    direction="Rx",
                    data=[0x30, ctx.fc_block_size & 0xFF, ctx.fc_stmin & 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00],
                    timestamp=timestamp,
                    frame_interval=ctx.frame_interval,
                    comment=f"{request_comment} FlowControl",
                )
                cf_sent_since_fc = 0

    if suppress_positive_response:
        return timestamp

    timestamp = maybe_emit_response_pending(
        trace=trace,
        ctx=ctx,
        timestamp=timestamp,
        request_sid=request_payload[0],
        response_comment=response_comment,
        delay_ms=response_delay_ms,
    )
    timestamp = add_delay(trace=trace, ctx=ctx, timestamp=timestamp, delay_ms=response_delay_ms)

    timestamp = append_isotp_message(
        trace=trace,
        payload=response_payload,
        can_id=ctx.response_id,
        direction="Rx",
        timestamp=timestamp,
        frame_interval=ctx.frame_interval,
        pad_byte=ctx.pad_byte,
        comment_prefix=response_comment,
    )
    return timestamp


def load_profile(profile_path: str) -> dict:
    with open(profile_path, "r", encoding="utf-8") as fh:
        profile = json.load(fh)

    required_sections = [
        "meta",
        "can",
        "isotp",
        "session",
        "communication_control",
        "control_dtc_setting",
        "security",
        "download",
        "transfer",
        "routines",
        "timing",
        "responses",
        "reset",
        "sequence",
    ]
    for section in required_sections:
        if section not in profile:
            raise ValueError(f"Profile missing required section: {section}")

    return profile


def load_seed_key_function(profile: dict):
    algorithm = profile["security"].get("algorithm", {})
    if profile["security"].get("enabled") is not True:
        return None

    algo_type = algorithm.get("type", "python").lower()

    # --- DLL-based seed-key ---
    if algo_type == "dll":
        dll_path = algorithm.get("dll_path", "")
        if not dll_path:
            raise ValueError(
                "Security algorithm type is 'dll' but 'dll_path' is not set. "
                "Set the path to the OEM security DLL in the profile."
            )
        if not os.path.isfile(dll_path):
            raise FileNotFoundError(f"Security DLL not found: {dll_path}")

        dll_function_name = algorithm.get("dll_function", "ComputeKey")
        seed_length = int(profile["security"].get("seed_length", 8))
        key_length = int(profile["security"].get("key_length", 8))

        dll = ctypes.CDLL(dll_path)
        try:
            dll_func = getattr(dll, dll_function_name)
        except AttributeError as exc:
            raise AttributeError(
                f"DLL {dll_path} does not export function '{dll_function_name}'"
            ) from exc

        def _dll_compute_key(seed: bytes) -> bytes:
            seed_buf = ctypes.create_string_buffer(seed, len(seed))
            key_buf = ctypes.create_string_buffer(key_length)
            dll_func(seed_buf, len(seed), key_buf, key_length)
            return key_buf.raw[:key_length]

        return _dll_compute_key

    # --- Python plugin-based seed-key ---
    if algo_type == "python":
        module_name = algorithm.get("module")
        function_name = algorithm.get("function")
        if not module_name or not function_name:
            raise ValueError("Security algorithm profile entry must define module and function")

        plugin_path = os.path.join(PLUGIN_DIR, f"{module_name}.py")
        if not os.path.isfile(plugin_path):
            raise FileNotFoundError(f"Security plugin not found: {plugin_path}")

        spec = importlib.util.spec_from_file_location(module_name, plugin_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load plugin spec for {plugin_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        try:
            function = getattr(module, function_name)
        except AttributeError as exc:
            raise AttributeError(f"Plugin {module_name} missing function {function_name}") from exc

        return function

    raise ValueError(f"Unsupported security algorithm type: '{algo_type}' (expected 'python' or 'dll')")


def build_runtime_context(profile: dict) -> RuntimeContext:
    can_cfg = profile["can"]
    isotp_cfg = profile["isotp"]
    timing_cfg = profile["timing"]
    session_cfg = profile["session"]
    transfer_cfg = profile["transfer"]
    responses_cfg = profile["responses"]
    tester_present_cfg = session_cfg.get("tester_present", {})

    tester_present_request = bytes()
    tester_present_response = bytes()
    session_timing_bytes = bytes.fromhex("003201f4")
    if tester_present_cfg.get("enabled"):
        tester_present_request = bytes(
            [
                _require_hex_byte(tester_present_cfg["service"], "session.tester_present.service"),
                _require_hex_byte(tester_present_cfg["subfunction"], "session.tester_present.subfunction"),
            ]
        )
        tester_present_response = bytes(
            [
                _require_hex_byte(
                    tester_present_cfg["positive_response"], "session.tester_present.positive_response"
                ),
                _require_hex_byte(tester_present_cfg["subfunction"], "session.tester_present.subfunction"),
            ]
        )
    session_timing_cfg = session_cfg.get("session_timing", {})
    if session_timing_cfg:
        p2_server_max_ms = int(session_timing_cfg.get("p2_server_max_ms", 50))
        p2_star_server_max_ms = int(session_timing_cfg.get("p2_star_server_max_ms", 5000))
        p2_star_resolution = int(session_timing_cfg.get("p2_star_resolution_ms", 10))
        p2_star_encoded = p2_star_server_max_ms // max(p2_star_resolution, 1)
        session_timing_bytes = (
            p2_server_max_ms.to_bytes(2, byteorder="big")
            + p2_star_encoded.to_bytes(2, byteorder="big")
        )

    tester_present_addressing = tester_present_cfg.get("addressing", "physical").lower()
    tester_present_can_id = can_cfg["request_id"].lower()
    if tester_present_addressing == "functional":
        tester_present_can_id = can_cfg.get("functional_id", can_cfg["request_id"]).lower()

    return RuntimeContext(
        profile=profile,
        request_id=can_cfg["request_id"].lower(),
        response_id=can_cfg["response_id"].lower(),
        functional_id=can_cfg.get("functional_id", can_cfg["request_id"]).lower(),
        channel=int(can_cfg.get("channel", 1)),
        frame_interval=int(timing_cfg.get("frame_interval_ms", 1)) / 1000.0,
        pad_byte=_require_hex_byte(can_cfg.get("padding_byte", "00"), "can.padding_byte"),
        fc_block_size=int(isotp_cfg.get("flow_control_block_size", 0)),
        fc_stmin=int(isotp_cfg.get("flow_control_stmin_ms", 0)),
        max_frame_data_length=int(isotp_cfg.get("max_frame_data_length", 8)),
        allow_response_pending=bool(responses_cfg.get("allow_response_pending", False)),
        response_pending_nrc=_require_hex_byte(
            responses_cfg.get("response_pending_nrc", "78"), "responses.response_pending_nrc"
        ),
        p2_timeout_ms=int(timing_cfg.get("p2_timeout_ms", 50)),
        tester_present_enabled=bool(tester_present_cfg.get("enabled", False)),
        tester_present_interval_ms=int(tester_present_cfg.get("interval_ms", 2000)),
        tester_present_can_id=tester_present_can_id,
        tester_present_request=tester_present_request,
        tester_present_response=tester_present_response,
        transfer_payload_bytes=int(transfer_cfg.get("payload_bytes_per_request", 64)),
        transfer_wait_positive_response=bool(
            transfer_cfg.get("wait_for_positive_response_per_block", True)
        ),
        block_sequence_start=int(transfer_cfg.get("block_sequence_start", 1)),
        block_sequence_rollover=int(transfer_cfg.get("block_sequence_rollover", 256)),
        negative_response_service=_require_hex_byte(
            responses_cfg.get("negative_response_service", "7f"), "responses.negative_response_service"
        ),
        seed_key_function=load_seed_key_function(profile),
        memory_regions=_parse_memory_regions(profile),
        session_timing_bytes=session_timing_bytes,
    )


def profile_service_payload(service_cfg: dict, service_key: str, response_key: str, subfunction_key: str = "subfunction"):
    request = bytes(
        [
            _require_hex_byte(service_cfg[service_key], f"{service_key}"),
            _require_hex_byte(service_cfg[subfunction_key], f"{subfunction_key}"),
        ]
    )
    response = bytes(
        [
            _require_hex_byte(service_cfg[response_key], f"{response_key}"),
            _require_hex_byte(service_cfg[subfunction_key], f"{subfunction_key}"),
        ]
    )
    return request, response


def build_security_key(ctx: RuntimeContext, seed: bytes) -> bytes:
    if ctx.seed_key_function is None:
        return seed

    key = ctx.seed_key_function(seed)
    if not isinstance(key, (bytes, bytearray)):
        raise TypeError("Seed-key plugin must return bytes")

    expected_length = int(ctx.profile["security"].get("key_length", len(key)))
    key = bytes(key)
    if len(key) != expected_length:
        raise ValueError(
            f"Seed-key plugin returned {len(key)} bytes but profile expects {expected_length}"
        )
    return key


def build_flash_sequence(segments: list[MemorySegment], ctx: RuntimeContext) -> list[TraceFrame]:
    trace: list[TraceFrame] = []
    timestamp = 0.0
    profile = ctx.profile
    timing_cfg = profile["timing"]
    security_cfg = profile["security"]
    download_cfg = profile["download"]
    transfer_cfg = profile["transfer"]
    reset_cfg = profile["reset"]
    session_cfg = profile["session"]
    routines_cfg = profile["routines"]
    segments = select_flash_segments(segments, ctx)

    programming_request, programming_response = profile_service_payload(
        session_cfg["programming_session"], "service", "positive_response"
    )
    seed_request_cfg = security_cfg["request_seed"]
    send_key_cfg = security_cfg["send_key"]
    reset_request, reset_response = profile_service_payload(
        reset_cfg, "service", "positive_response"
    )

    sequence = profile["sequence"]
    block_sequence_counter = ctx.block_sequence_start
    rollover = max(ctx.block_sequence_rollover, 1)

    for step in sequence:
        if step == "extended_session":
            ext_cfg = session_cfg["extended_session"]
            addressing = ext_cfg.get("addressing", "physical").lower()
            suppress = bool(ext_cfg.get("suppress_positive_response", False))
            sf_byte = _require_hex_byte(ext_cfg["subfunction"], "session.extended_session.subfunction")
            if suppress:
                sf_byte |= 0x80
            request_payload = bytes([
                _require_hex_byte(ext_cfg["service"], "session.extended_session.service"),
                sf_byte,
            ])
            response_payload = bytes([
                _require_hex_byte(ext_cfg["positive_response"], "session.extended_session.positive_response"),
                _require_hex_byte(ext_cfg["subfunction"], "session.extended_session.subfunction"),
            ]) + ctx.session_timing_bytes
            tx_can_id = ctx.functional_id if addressing == "functional" else ctx.request_id
            timestamp = append_request_response(
                trace=trace,
                ctx=ctx,
                request_payload=request_payload,
                response_payload=response_payload,
                timestamp=timestamp,
                request_comment="DiagnosticSessionControl extended",
                response_comment="DiagnosticSessionControl extended response",
                response_delay_ms=0,
                request_can_id=tx_can_id,
                suppress_positive_response=suppress,
            )

        elif step == "tester_present":
            if ctx.tester_present_enabled:
                timestamp = append_request_response(
                    trace=trace,
                    ctx=ctx,
                    request_payload=ctx.tester_present_request,
                    response_payload=ctx.tester_present_response,
                    timestamp=timestamp,
                request_comment="TesterPresent",
                response_comment="TesterPresent positive response",
                response_delay_ms=0,
                request_can_id=ctx.tester_present_can_id,
            )

        elif step == "communication_control":
            comm_cfg = profile["communication_control"]
            if comm_cfg.get("enabled"):
                addressing = comm_cfg.get("addressing", "physical").lower()
                suppress = bool(comm_cfg.get("suppress_positive_response", False))
                sf_byte = _require_hex_byte(comm_cfg["subfunction"], "communication_control.subfunction")
                if suppress:
                    sf_byte |= 0x80
                request_payload = bytes([
                    _require_hex_byte(comm_cfg["service"], "communication_control.service"),
                    sf_byte,
                    _require_hex_byte(
                        comm_cfg["communication_type"], "communication_control.communication_type"
                    ),
                ])
                response_payload = bytes([
                    _require_hex_byte(
                        comm_cfg["positive_response"], "communication_control.positive_response"
                    ),
                    _require_hex_byte(comm_cfg["subfunction"], "communication_control.subfunction"),
                ])
                tx_can_id = ctx.functional_id if addressing == "functional" else ctx.request_id
                timestamp = append_request_response(
                    trace=trace,
                    ctx=ctx,
                    request_payload=request_payload,
                    response_payload=response_payload,
                    timestamp=timestamp,
                    request_comment="CommunicationControl",
                    response_comment="CommunicationControl positive response",
                    response_delay_ms=0,
                    request_can_id=tx_can_id,
                    suppress_positive_response=suppress,
                )

        elif step == "control_dtc_setting":
            dtc_cfg = profile["control_dtc_setting"]
            if dtc_cfg.get("enabled"):
                addressing = dtc_cfg.get("addressing", "physical").lower()
                suppress = bool(dtc_cfg.get("suppress_positive_response", False))
                sf_byte = _require_hex_byte(dtc_cfg["subfunction"], "control_dtc_setting.subfunction")
                if suppress:
                    sf_byte |= 0x80
                request_payload = bytes([
                    _require_hex_byte(dtc_cfg["service"], "control_dtc_setting.service"),
                    sf_byte,
                ])
                response_payload = bytes([
                    _require_hex_byte(
                        dtc_cfg["positive_response"], "control_dtc_setting.positive_response"
                    ),
                    _require_hex_byte(dtc_cfg["subfunction"], "control_dtc_setting.subfunction"),
                ])
                tx_can_id = ctx.functional_id if addressing == "functional" else ctx.request_id
                timestamp = append_request_response(
                    trace=trace,
                    ctx=ctx,
                    request_payload=request_payload,
                    response_payload=response_payload,
                    timestamp=timestamp,
                    request_comment="ControlDTCSetting",
                    response_comment="ControlDTCSetting positive response",
                    response_delay_ms=0,
                    request_can_id=tx_can_id,
                    suppress_positive_response=suppress,
                )

        elif step == "programming_session":
            response_payload = programming_response + ctx.session_timing_bytes
            timestamp = append_request_response(
                trace=trace,
                ctx=ctx,
                request_payload=programming_request,
                response_payload=response_payload,
                timestamp=timestamp,
                request_comment="DiagnosticSessionControl programming",
                response_comment="DiagnosticSessionControl positive response",
                response_delay_ms=0,
            )

        elif step == "security_request_seed" and security_cfg.get("enabled"):
            seed_length = int(security_cfg.get("seed_length", 4))
            seed = bytes((0x12 + index * 0x22) & 0xFF for index in range(seed_length))
            ctx.profile["_runtime_seed"] = seed.hex()
            request_payload = bytes(
                [
                    _require_hex_byte(seed_request_cfg["service"], "security.request_seed.service"),
                    _require_hex_byte(seed_request_cfg["subfunction"], "security.request_seed.subfunction"),
                ]
            )
            response_payload = bytes(
                [
                    _require_hex_byte(
                        seed_request_cfg["positive_response"], "security.request_seed.positive_response"
                    ),
                    _require_hex_byte(seed_request_cfg["subfunction"], "security.request_seed.subfunction"),
                ]
            ) + seed
            timestamp = append_request_response(
                trace=trace,
                ctx=ctx,
                request_payload=request_payload,
                response_payload=response_payload,
                timestamp=timestamp,
                request_comment="SecurityAccess request seed",
                response_comment="SecurityAccess seed response",
                response_delay_ms=0,
            )

        elif step == "security_send_key" and security_cfg.get("enabled"):
            seed = bytes.fromhex(ctx.profile.get("_runtime_seed", ""))
            key = build_security_key(ctx, seed)
            request_payload = bytes(
                [
                    _require_hex_byte(send_key_cfg["service"], "security.send_key.service"),
                    _require_hex_byte(send_key_cfg["subfunction"], "security.send_key.subfunction"),
                ]
            ) + key
            response_payload = bytes(
                [
                    _require_hex_byte(
                        send_key_cfg["positive_response"], "security.send_key.positive_response"
                    ),
                    _require_hex_byte(send_key_cfg["subfunction"], "security.send_key.subfunction"),
                ]
            )
            timestamp = append_request_response(
                trace=trace,
                ctx=ctx,
                request_payload=request_payload,
                response_payload=response_payload,
                timestamp=timestamp,
                request_comment="SecurityAccess send key",
                response_comment="SecurityAccess unlock response",
                response_delay_ms=0,
            )

        elif step in {"erase_memory", "request_download", "transfer_data", "transfer_exit"}:
            for segment_index, segment in enumerate(segments, start=1):
                address_bytes = segment.start.to_bytes(
                    int(download_cfg["address_length_bytes"]), byteorder="big"
                )
                size_bytes = len(segment.data).to_bytes(
                    int(download_cfg["size_length_bytes"]), byteorder="big"
                )
                memory_identifier = (
                    _hex_to_bytes(download_cfg.get("memory_identifier", ""), "download.memory_identifier")
                    if download_cfg.get("use_memory_identifier")
                    else b""
                )

                if step == "erase_memory":
                    erase_cfg = routines_cfg.get("erase_memory", {})
                    if not erase_cfg.get("enabled"):
                        continue
                    if not segment_needs_erase(segment, ctx):
                        continue
                    routine_id = _hex_to_bytes(erase_cfg["routine_id"], "routines.erase_memory.routine_id")
                    request_payload = bytes(
                        [
                            _require_hex_byte(erase_cfg["service"], "routines.erase_memory.service"),
                            _require_hex_byte(erase_cfg["subfunction"], "routines.erase_memory.subfunction"),
                        ]
                    ) + routine_id + _hex_to_bytes(
                        erase_cfg.get("erase_target", "02"), "routines.erase_memory.erase_target"
                    )
                    response_payload = bytes(
                        [
                            _require_hex_byte(
                                erase_cfg["positive_response"], "routines.erase_memory.positive_response"
                            ),
                            _require_hex_byte(erase_cfg["subfunction"], "routines.erase_memory.subfunction"),
                        ]
                    ) + routine_id
                    timestamp = append_request_response(
                        trace=trace,
                        ctx=ctx,
                        request_payload=request_payload,
                        response_payload=response_payload,
                        timestamp=timestamp,
                        request_comment=f"RoutineControl erase segment {segment_index}",
                        response_comment=f"RoutineControl erase response segment {segment_index}",
                        response_delay_ms=int(timing_cfg.get("erase_delay_ms", 0)),
                    )

                elif step == "request_download":
                    download_length_format = (
                        (int(download_cfg["address_length_bytes"]) << 4)
                        | int(download_cfg["size_length_bytes"])
                    )
                    request_payload = bytes(
                        [
                            _require_hex_byte(
                                download_cfg["request_download_service"], "download.request_download_service"
                            ),
                            _require_hex_byte(
                                download_cfg.get("data_format_identifier", "00"),
                                "download.data_format_identifier",
                            ),
                            download_length_format,
                        ]
                    ) + memory_identifier + address_bytes + size_bytes

                    negotiated_block_length = min(
                        ctx.transfer_payload_bytes + 2,
                        (1 << (8 * int(download_cfg["size_length_bytes"]))) - 1,
                    )
                    response_payload = bytes(
                        [
                            _require_hex_byte(
                                download_cfg["positive_response"], "download.positive_response"
                            ),
                            0x20,
                            (negotiated_block_length >> 8) & 0xFF,
                            negotiated_block_length & 0xFF,
                        ]
                    )
                    timestamp = append_request_response(
                        trace=trace,
                        ctx=ctx,
                        request_payload=request_payload,
                        response_payload=response_payload,
                        timestamp=timestamp,
                        request_comment=f"RequestDownload segment {segment_index}",
                        response_comment=f"RequestDownload response segment {segment_index}",
                        response_delay_ms=int(timing_cfg.get("download_delay_ms", 0)),
                    )

                elif step == "transfer_data":
                    transfer_service = _require_hex_byte(
                        transfer_cfg["transfer_data_service"], "transfer.transfer_data_service"
                    )
                    transfer_positive = _require_hex_byte(
                        transfer_cfg["transfer_data_positive_response"],
                        "transfer.transfer_data_positive_response",
                    )
                    for offset in range(0, len(segment.data), ctx.transfer_payload_bytes):
                        chunk = segment.data[offset : offset + ctx.transfer_payload_bytes]
                        request_payload = bytes([transfer_service, block_sequence_counter & 0xFF]) + chunk
                        response_payload = bytes([transfer_positive, block_sequence_counter & 0xFF])
                        timestamp = append_request_response(
                            trace=trace,
                            ctx=ctx,
                            request_payload=request_payload,
                            response_payload=response_payload,
                            timestamp=timestamp,
                            request_comment=(
                                f"TransferData segment {segment_index} block "
                                f"{block_sequence_counter:02X}"
                            ),
                            response_comment=(
                                f"TransferData positive response block "
                                f"{block_sequence_counter:02X}"
                            ),
                            response_delay_ms=int(timing_cfg.get("transfer_block_delay_ms", 0)),
                        )
                        block_sequence_counter = (block_sequence_counter + 1) % rollover

                elif step == "transfer_exit":
                    request_payload = bytes(
                        [_require_hex_byte(transfer_cfg["transfer_exit_service"], "transfer.transfer_exit_service")]
                    )
                    response_payload = bytes(
                        [
                            _require_hex_byte(
                                transfer_cfg["transfer_exit_positive_response"],
                                "transfer.transfer_exit_positive_response",
                            )
                        ]
                    )
                    timestamp = append_request_response(
                        trace=trace,
                        ctx=ctx,
                        request_payload=request_payload,
                        response_payload=response_payload,
                        timestamp=timestamp,
                        request_comment=f"RequestTransferExit segment {segment_index}",
                        response_comment=f"TransferExit response segment {segment_index}",
                        response_delay_ms=int(timing_cfg.get("transfer_exit_delay_ms", 0)),
                    )

        elif step == "checksum_verify":
            cs_cfg = routines_cfg.get("checksum_verify", {})
            if not cs_cfg.get("enabled"):
                continue
            routine_id = _hex_to_bytes(cs_cfg["routine_id"], "routines.checksum_verify.routine_id")
            all_data = b"".join(seg.data for seg in segments)
            crc = crc16_ccitt(all_data)
            crc_bytes = crc.to_bytes(2, byteorder="big")
            request_payload = bytes([
                _require_hex_byte(cs_cfg["service"], "routines.checksum_verify.service"),
                _require_hex_byte(cs_cfg["subfunction"], "routines.checksum_verify.subfunction"),
            ]) + routine_id + crc_bytes
            response_payload = bytes([
                _require_hex_byte(cs_cfg["positive_response"], "routines.checksum_verify.positive_response"),
                _require_hex_byte(cs_cfg["subfunction"], "routines.checksum_verify.subfunction"),
            ]) + routine_id
            timestamp = append_request_response(
                trace=trace,
                ctx=ctx,
                request_payload=request_payload,
                response_payload=response_payload,
                timestamp=timestamp,
                request_comment="RoutineControl compare checksum",
                response_comment="RoutineControl compare checksum response",
                response_delay_ms=int(timing_cfg.get("checksum_delay_ms", timing_cfg.get("post_routine_delay_ms", 0))),
            )

        elif step == "dependency_check":
            routine_cfg = routines_cfg.get("dependency_check", {})
            if not routine_cfg.get("enabled"):
                continue
            routine_id = _hex_to_bytes(routine_cfg["routine_id"], "routines.dependency_check.routine_id")
            request_payload = bytes([
                _require_hex_byte(routine_cfg["service"], "routines.dependency_check.service"),
                _require_hex_byte(routine_cfg["subfunction"], "routines.dependency_check.subfunction"),
            ]) + routine_id
            response_payload = bytes([
                _require_hex_byte(routine_cfg["positive_response"], "routines.dependency_check.positive_response"),
                _require_hex_byte(routine_cfg["subfunction"], "routines.dependency_check.subfunction"),
            ]) + routine_id
            timestamp = append_request_response(
                trace=trace,
                ctx=ctx,
                request_payload=request_payload,
                response_payload=response_payload,
                timestamp=timestamp,
                request_comment="RoutineControl dependency_check",
                response_comment="RoutineControl dependency_check response",
                response_delay_ms=int(timing_cfg.get("post_routine_delay_ms", 0)),
            )

        elif step == "ecu_reset":
            timestamp = append_request_response(
                trace=trace,
                ctx=ctx,
                request_payload=reset_request,
                response_payload=reset_response,
                timestamp=timestamp,
                request_comment="ECUReset",
                response_comment="ECUReset positive response",
                response_delay_ms=int(timing_cfg.get("reset_delay_ms", 0)),
            )

        elif step == "set_boot_flag":
            bf_cfg = routines_cfg.get("set_boot_flag", {})
            if not bf_cfg.get("enabled"):
                continue
            routine_id = _hex_to_bytes(bf_cfg["routine_id"], "routines.set_boot_flag.routine_id")
            flag_data = _hex_to_bytes(bf_cfg.get("data", "01"), "routines.set_boot_flag.data")
            request_payload = bytes([
                _require_hex_byte(bf_cfg["service"], "routines.set_boot_flag.service"),
                _require_hex_byte(bf_cfg["subfunction"], "routines.set_boot_flag.subfunction"),
            ]) + routine_id + flag_data
            response_payload = bytes([
                _require_hex_byte(bf_cfg["positive_response"], "routines.set_boot_flag.positive_response"),
                _require_hex_byte(bf_cfg["subfunction"], "routines.set_boot_flag.subfunction"),
            ]) + routine_id
            timestamp = append_request_response(
                trace=trace,
                ctx=ctx,
                request_payload=request_payload,
                response_payload=response_payload,
                timestamp=timestamp,
                request_comment="RoutineControl set boot flag",
                response_comment="RoutineControl set boot flag response",
                response_delay_ms=int(timing_cfg.get("boot_flag_delay_ms", 0)),
            )

        elif step == "clear_boot_flag":
            cbf_cfg = routines_cfg.get("clear_boot_flag", {})
            if not cbf_cfg.get("enabled"):
                continue
            routine_id = _hex_to_bytes(cbf_cfg["routine_id"], "routines.clear_boot_flag.routine_id")
            flag_data = _hex_to_bytes(cbf_cfg.get("data", "00"), "routines.clear_boot_flag.data")
            request_payload = bytes([
                _require_hex_byte(cbf_cfg["service"], "routines.clear_boot_flag.service"),
                _require_hex_byte(cbf_cfg["subfunction"], "routines.clear_boot_flag.subfunction"),
            ]) + routine_id + flag_data
            response_payload = bytes([
                _require_hex_byte(cbf_cfg["positive_response"], "routines.clear_boot_flag.positive_response"),
                _require_hex_byte(cbf_cfg["subfunction"], "routines.clear_boot_flag.subfunction"),
            ]) + routine_id
            timestamp = append_request_response(
                trace=trace,
                ctx=ctx,
                request_payload=request_payload,
                response_payload=response_payload,
                timestamp=timestamp,
                request_comment="RoutineControl clear boot flag",
                response_comment="RoutineControl clear boot flag response",
                response_delay_ms=int(timing_cfg.get("boot_flag_delay_ms", 0)),
            )

        elif step == "access_timing_parameters":
            at_cfg = profile.get("access_timing", {})
            if not at_cfg.get("enabled"):
                continue
            p2_min = int(at_cfg.get("p2_min_ms", 0))
            p2_max = int(at_cfg.get("p2_max_ms", 50))
            p3_min = int(at_cfg.get("p3_min_ms", 0))
            p3_max = int(at_cfg.get("p3_max_ms", 0))
            stmin = int(at_cfg.get("stmin_ms", 0))
            request_payload = bytes([
                _require_hex_byte(at_cfg["service"], "access_timing.service"),
                _require_hex_byte(at_cfg["subfunction"], "access_timing.subfunction"),
                (p2_min >> 8) & 0xFF, p2_min & 0xFF,
                (p2_max >> 8) & 0xFF, p2_max & 0xFF,
                (p3_min >> 8) & 0xFF, p3_min & 0xFF,
                p3_max & 0xFF,
            ])
            response_payload = bytes([
                _require_hex_byte(at_cfg["positive_response"], "access_timing.positive_response"),
                _require_hex_byte(at_cfg["subfunction"], "access_timing.subfunction"),
            ])
            timestamp = append_request_response(
                trace=trace,
                ctx=ctx,
                request_payload=request_payload,
                response_payload=response_payload,
                timestamp=timestamp,
                request_comment="AccessTimingParameter setToGivenValues",
                response_comment="AccessTimingParameter positive response",
                response_delay_ms=int(timing_cfg.get("access_timing_delay_ms", 0)),
            )

        elif step == "update_history_zone":
            hz_cfg = routines_cfg.get("update_history_zone", {})
            if not hz_cfg.get("enabled"):
                continue
            routine_id = _hex_to_bytes(hz_cfg["routine_id"], "routines.update_history_zone.routine_id")
            record_length = int(hz_cfg.get("record_length", 25))
            now = dt.datetime.now()
            record = now.strftime("%Y%m%d%H%M%S").encode("ascii")[:record_length]
            record = record.ljust(record_length, b"\x00")
            request_payload = bytes([
                _require_hex_byte(hz_cfg["service"], "routines.update_history_zone.service"),
                _require_hex_byte(hz_cfg["subfunction"], "routines.update_history_zone.subfunction"),
            ]) + routine_id + record
            response_payload = bytes([
                _require_hex_byte(hz_cfg["positive_response"], "routines.update_history_zone.positive_response"),
                _require_hex_byte(hz_cfg["subfunction"], "routines.update_history_zone.subfunction"),
            ]) + routine_id
            timestamp = append_request_response(
                trace=trace,
                ctx=ctx,
                request_payload=request_payload,
                response_payload=response_payload,
                timestamp=timestamp,
                request_comment="RoutineControl update service history zone",
                response_comment="RoutineControl update history zone response",
                response_delay_ms=int(timing_cfg.get("history_zone_delay_ms", 0)),
            )

        elif step == "link_control":
            lc_cfg = profile.get("link_control", {})
            if not lc_cfg.get("enabled"):
                continue
            mode_param = _hex_to_bytes(
                lc_cfg.get("mode_parameter", "000000"), "link_control.mode_parameter"
            )
            verify_payload = bytes([
                _require_hex_byte(lc_cfg["service"], "link_control.service"),
                _require_hex_byte(lc_cfg["verify_subfunction"], "link_control.verify_subfunction"),
            ]) + mode_param
            verify_response = bytes([
                _require_hex_byte(lc_cfg["positive_response"], "link_control.positive_response"),
                _require_hex_byte(lc_cfg["verify_subfunction"], "link_control.verify_subfunction"),
            ])
            timestamp = append_request_response(
                trace=trace, ctx=ctx,
                request_payload=verify_payload,
                response_payload=verify_response,
                timestamp=timestamp,
                request_comment="LinkControl verify mode transition",
                response_comment="LinkControl verify response",
                response_delay_ms=0,
            )
            transition_payload = bytes([
                _require_hex_byte(lc_cfg["service"], "link_control.service"),
                _require_hex_byte(lc_cfg["transition_subfunction"], "link_control.transition_subfunction"),
            ])
            transition_response = bytes([
                _require_hex_byte(lc_cfg["positive_response"], "link_control.positive_response"),
                _require_hex_byte(lc_cfg["transition_subfunction"], "link_control.transition_subfunction"),
            ])
            timestamp = append_request_response(
                trace=trace, ctx=ctx,
                request_payload=transition_payload,
                response_payload=transition_response,
                timestamp=timestamp,
                request_comment="LinkControl transition mode",
                response_comment="LinkControl transition response",
                response_delay_ms=0,
            )

        elif step == "clear_dtc":
            cd_cfg = profile.get("clear_dtc", {})
            if not cd_cfg.get("enabled"):
                continue
            dtc_group = _hex_to_bytes(cd_cfg.get("group_of_dtc", "ffffff"), "clear_dtc.group_of_dtc")
            request_payload = bytes([
                _require_hex_byte(cd_cfg["service"], "clear_dtc.service"),
            ]) + dtc_group
            response_payload = bytes([
                _require_hex_byte(cd_cfg["positive_response"], "clear_dtc.positive_response"),
            ])
            timestamp = append_request_response(
                trace=trace,
                ctx=ctx,
                request_payload=request_payload,
                response_payload=response_payload,
                timestamp=timestamp,
                request_comment="ClearDiagnosticInformation clear all DTCs",
                response_comment="ClearDTC positive response",
                response_delay_ms=int(timing_cfg.get("clear_dtc_delay_ms", 0)),
            )

        elif step == "communication_control_enable":
            comm_en_cfg = profile.get("communication_control_enable", {})
            if not comm_en_cfg.get("enabled"):
                continue
            addressing = comm_en_cfg.get("addressing", "physical").lower()
            suppress = bool(comm_en_cfg.get("suppress_positive_response", False))
            sf_byte = _require_hex_byte(
                comm_en_cfg.get("subfunction", "00"), "communication_control_enable.subfunction"
            )
            if suppress:
                sf_byte |= 0x80
            request_payload = bytes([
                _require_hex_byte(comm_en_cfg["service"], "communication_control_enable.service"),
                sf_byte,
                _require_hex_byte(
                    comm_en_cfg.get("communication_type", "03"),
                    "communication_control_enable.communication_type",
                ),
            ])
            response_payload = bytes([
                _require_hex_byte(
                    comm_en_cfg.get("positive_response", "68"),
                    "communication_control_enable.positive_response",
                ),
                _require_hex_byte(
                    comm_en_cfg.get("subfunction", "00"),
                    "communication_control_enable.subfunction",
                ),
            ])
            tx_can_id = ctx.functional_id if addressing == "functional" else ctx.request_id
            timestamp = append_request_response(
                trace=trace,
                ctx=ctx,
                request_payload=request_payload,
                response_payload=response_payload,
                timestamp=timestamp,
                request_comment="CommunicationControl enable",
                response_comment="CommunicationControl enable response",
                response_delay_ms=0,
                request_can_id=tx_can_id,
                suppress_positive_response=suppress,
            )

        elif step == "control_dtc_setting_enable":
            dtc_en_cfg = profile.get("control_dtc_setting_enable", {})
            if not dtc_en_cfg.get("enabled"):
                continue
            addressing = dtc_en_cfg.get("addressing", "physical").lower()
            suppress = bool(dtc_en_cfg.get("suppress_positive_response", False))
            sf_byte = _require_hex_byte(
                dtc_en_cfg.get("subfunction", "01"), "control_dtc_setting_enable.subfunction"
            )
            if suppress:
                sf_byte |= 0x80
            request_payload = bytes([
                _require_hex_byte(dtc_en_cfg["service"], "control_dtc_setting_enable.service"),
                sf_byte,
            ])
            response_payload = bytes([
                _require_hex_byte(
                    dtc_en_cfg.get("positive_response", "c5"),
                    "control_dtc_setting_enable.positive_response",
                ),
                _require_hex_byte(
                    dtc_en_cfg.get("subfunction", "01"),
                    "control_dtc_setting_enable.subfunction",
                ),
            ])
            tx_can_id = ctx.functional_id if addressing == "functional" else ctx.request_id
            timestamp = append_request_response(
                trace=trace,
                ctx=ctx,
                request_payload=request_payload,
                response_payload=response_payload,
                timestamp=timestamp,
                request_comment="ControlDTCSetting enable",
                response_comment="ControlDTCSetting enable response",
                response_delay_ms=0,
                request_can_id=tx_can_id,
                suppress_positive_response=suppress,
            )

        else:
            raise ValueError(f"Unsupported sequence step in profile: {step}")

    return trace


def write_asc(trace: list[TraceFrame], output_path: str, source_name: str, ctx: RuntimeContext) -> None:
    now = dt.datetime.now()
    file_uuid = str(uuid.uuid4())

    with open(output_path, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write(f"date {format_asc_date(now)}\n")
        fh.write("base hex  timestamps absolute\n")
        fh.write("no internal events logged\n")
        fh.write("version 6.0\n")
        fh.write("// ;\n")
        fh.write(f"   UUID: {file_uuid}\n")
        fh.write(f"// Source: {source_name}\n")
        fh.write(
            f"// Profile: {ctx.profile['meta'].get('name', 'Unknown')}  "
            f"Request ID: 0x{ctx.request_id.upper()}  Response ID: 0x{ctx.response_id.upper()}\n"
        )
        fh.write(f"// Frames: {len(trace)}\n")
        fh.write("\n")

        for frame in trace:
            hex_bytes = "  ".join(f"{value:02x}" for value in frame.data)
            line = (
                f"   {frame.timestamp:10.6f} {ctx.channel}  {frame.can_id}  "
                f"{frame.direction:<4} d {len(frame.data)}  {hex_bytes}"
            )
            if frame.comment:
                line += f" // {frame.comment}"
            fh.write(line + "\n")

        fh.write("\n")
        fh.write("End TriggerBlock\n")


def process_file(hex_path: str, output_dir: str, ctx: RuntimeContext) -> tuple[str, int, int, int]:
    parsed_segments = parse_intel_hex_segments(hex_path)
    selected_segments = select_flash_segments(parsed_segments, ctx)
    total_bytes = sum(len(segment.data) for segment in selected_segments)
    trace = build_flash_sequence(selected_segments, ctx)

    base_name = os.path.splitext(os.path.basename(hex_path))[0]
    profile_name = ctx.profile["meta"].get("name", "profile").lower().replace(" ", "_")
    output_name = f"{base_name}_{profile_name}_uds.asc"
    output_path = os.path.join(output_dir, output_name)
    write_asc(trace, output_path, os.path.basename(hex_path), ctx)

    return output_path, len(selected_segments), total_bytes, len(trace), selected_segments


def process_all(profile_path: str) -> int:
    profile = load_profile(profile_path)
    ctx = build_runtime_context(profile)

    if not os.path.isdir(FIRMWARE_DIR):
        print(f"[ERROR] Firmware folder not found: {FIRMWARE_DIR}")
        return 1

    hex_files = sorted(name for name in os.listdir(FIRMWARE_DIR) if name.lower().endswith(".hex"))
    if not hex_files:
        print(f"[WARN] No .hex files found in: {FIRMWARE_DIR}")
        return 0

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("-" * 78)
    print(f"  Profile         : {profile['meta'].get('name', 'Unknown')}")
    print(f"  Found           : {len(hex_files)} hex file(s)")
    print(f"  Input dir       : {FIRMWARE_DIR}")
    print(f"  Output dir      : {OUTPUT_DIR}")
    print(f"  Request/Resp ID : 0x{ctx.request_id.upper()} / 0x{ctx.response_id.upper()}")
    print(f"  Transfer bytes  : {ctx.transfer_payload_bytes} per TransferData request")
    print(f"  TesterPresent   : {'ON' if ctx.tester_present_enabled else 'OFF'}")
    print(f"  ResponsePending : {'ON' if ctx.allow_response_pending else 'OFF'}")
    print("-" * 78)

    failures = 0
    for name in hex_files:
        hex_path = os.path.join(FIRMWARE_DIR, name)
        print(f"\nProcessing {name}")
        try:
            output_path, segments, total_bytes, frames, selected_segments = process_file(hex_path, OUTPUT_DIR, ctx)
            print(f"  Segments        : {segments}")
            print(f"  Firmware bytes  : {total_bytes:,}")
            print(f"  Trace frames    : {frames:,}")
            print(f"  Output          : {output_path}")

            # -- Auto-verification: re-read ASC and compare against HEX --
            original_data = b"".join(seg.data for seg in selected_segments)
            extracted_data = parse_asc_transfer_data(output_path, silent=True)
            if len(original_data) != len(extracted_data):
                print(f"  Verification    : FAIL (length mismatch: HEX={len(original_data):,}, ASC={len(extracted_data):,})")
                print("  Status          : VERIFICATION ERROR")
                failures += 1
                continue
            mismatch_offset = -1
            for i in range(len(original_data)):
                if original_data[i] != extracted_data[i]:
                    mismatch_offset = i
                    break
            if mismatch_offset >= 0:
                print(f"  Verification    : FAIL at offset 0x{mismatch_offset:08X} "
                      f"(expected 0x{original_data[mismatch_offset]:02X}, "
                      f"got 0x{extracted_data[mismatch_offset]:02X})")
                print("  Status          : VERIFICATION ERROR")
                failures += 1
            else:
                print(f"  Verification    : PASS ({len(original_data):,} / {len(extracted_data):,} bytes match)")
                print("  Status          : OK")
        except Exception as exc:
            failures += 1
            print(f"  Status          : FAILED ({type(exc).__name__}: {exc})")

    print("\n" + "-" * 78)
    print(f"  Completed. Failures: {failures}")
    print("-" * 78)
    return 1 if failures else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate UDS flashing ASC traces from Intel HEX files.")
    parser.add_argument(
        "--profile",
        default=DEFAULT_PROFILE,
        help="Path to OEM profile JSON file. Defaults to profiles/mahindra_template.json",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    sys.exit(process_all(os.path.abspath(args.profile)))
