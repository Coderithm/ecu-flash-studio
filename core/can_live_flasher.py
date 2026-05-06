import argparse
from dataclasses import dataclass
from datetime import datetime
import os
import sys
import time

try:
    import can
except ImportError:
    can = None

try:
    from core.hex_parsing import (
        parse_intel_hex_segments,
        select_flash_segments,
        build_runtime_context,
        build_flash_sequence,
        build_security_key,
        isotp_encode,
        load_profile,
        DEFAULT_PROFILE,
        FIRMWARE_DIR,
        ROOT_DIR,
        PROFILE_DIR,
        PLUGIN_DIR
    )
except ImportError:
    from hex_parsing import (
        parse_intel_hex_segments,
        select_flash_segments,
        build_runtime_context,
        build_flash_sequence,
        build_security_key,
        isotp_encode,
        load_profile,
        DEFAULT_PROFILE,
        FIRMWARE_DIR,
        ROOT_DIR,
        PROFILE_DIR,
        PLUGIN_DIR
    )


MAX_FLASH_REPEAT = 10000


@dataclass
class ReceivedResponse:
    """ECU response plus decoded UDS payload."""
    msg: object
    payload: bytes
    raw_frames: list[bytes]


@dataclass
class LiveRuntime:
    """Runtime-only live flashing safeguards."""
    request_id: int
    response_id: int
    functional_id: int
    p2_timeout: float
    p2_star_timeout: float
    recent_tx: list
    external_count: int
    external_request_ids: set
    fail_on_external: bool
    drain_before_critical: bool
    post_reset_cleanup_delay: float
    clear_dtc_retry_delay: float
    clear_dtc_retries: int
    bus_idle_before_clear_dtc: float
    bus_idle_max_wait: float

    def mark_tx(self, msg) -> None:
        self.recent_tx.append((time.time(), msg.arbitration_id, bytes(msg.data)))
        cutoff = time.time() - 2.0
        self.recent_tx = [entry for entry in self.recent_tx if entry[0] >= cutoff]

    def is_own_echo(self, msg) -> bool:
        msg_data = bytes(msg.data)
        cutoff = time.time() - 2.0
        self.recent_tx = [entry for entry in self.recent_tx if entry[0] >= cutoff]
        return any(
            can_id == msg.arbitration_id and data == msg_data
            for _, can_id, data in self.recent_tx
        )

    def inspect_external(self, msg, phase: str) -> bool:
        if msg.arbitration_id not in self.external_request_ids:
            return False
        if self.is_own_echo(msg):
            return False
        self.external_count += 1
        log(
            "  WARNING: External tester traffic detected "
            f"during {phase}: {msg.arbitration_id:03X} "
            f"{' '.join(f'{b:02X}' for b in msg.data)}"
        )
        return self.fail_on_external


def timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def log(message: str = "") -> None:
    if message.startswith("\n"):
        print()
        message = message.lstrip("\n")
    if not message:
        print(f"[{timestamp()}]")
        return
    for line in message.splitlines():
        print(f"[{timestamp()}] {line}" if line else "")


def decode_single_frame_payload(data) -> bytes | None:
    """Return the UDS payload for a Single Frame, or None for other PCI types."""
    if not data:
        return None
    if (data[0] >> 4) != 0x0:
        return None
    sf_len = data[0] & 0x0F
    return bytes(data[1:1 + sf_len])


def expected_payload_prefix(expected_data: bytes | list[int]) -> bytes:
    """
    Decode the generated trace frame into the prefix we must see live.

    Security seed bytes and some negotiated responses can vary on a real ECU, so
    live validation checks the positive response SID/subfunction prefix rather
    than requiring the whole simulated payload to match.
    """
    payload = decode_single_frame_payload(expected_data)
    if payload is not None:
        if len(payload) >= 3 and payload[0] == 0x62:
            return payload[:3]
        return payload[:2] if len(payload) >= 2 else payload

    if expected_data and (expected_data[0] >> 4) == 0x1:
        total_length = ((expected_data[0] & 0x0F) << 8) | expected_data[1]
        payload = bytes(expected_data[2:8])[:total_length]
        if len(payload) >= 3 and payload[0] == 0x62:
            return payload[:3]
        return payload[:2] if len(payload) >= 2 else payload

    return bytes()


def describe_negative_response(payload: bytes) -> str:
    if len(payload) >= 3 and payload[0] == 0x7F:
        nrc_names = {
            0x10: "generalReject",
            0x11: "serviceNotSupported",
            0x12: "subFunctionNotSupported",
            0x13: "incorrectMessageLengthOrInvalidFormat",
            0x22: "conditionsNotCorrect",
            0x24: "requestSequenceError",
            0x31: "requestOutOfRange",
            0x33: "securityAccessDenied",
            0x35: "invalidKey",
            0x36: "exceedNumberOfAttempts",
            0x37: "requiredTimeDelayNotExpired",
            0x70: "uploadDownloadNotAccepted",
            0x71: "transferDataSuspended",
            0x72: "generalProgrammingFailure",
            0x73: "wrongBlockSequenceCounter",
            0x78: "responsePending",
        }
        nrc_name = nrc_names.get(payload[2], "unknownNRC")
        return f"7F {payload[1]:02X} {payload[2]:02X} ({nrc_name})"
    return ""


def is_response_pending_frame(data) -> bool:
    payload = decode_single_frame_payload(data)
    return bool(payload and len(payload) >= 3 and payload[0] == 0x7F and payload[2] == 0x78)


def response_timeout_for(frame) -> float:
    comment = (frame.comment or "").lower()
    expected_payload = decode_single_frame_payload(frame.data)
    if expected_payload and expected_payload[0] == 0x54:
        return 10.0
    if "set boot flag" in comment or "clear boot flag" in comment:
        return 5.0
    if "update" in comment and "history" in comment:
        return 5.0
    if "routinecontrol" in comment or "routine control" in comment:
        return 5.0
    if "erase" in comment:
        return 60.0
    if "checksum" in comment or "compare checksum" in comment:
        return 30.0
    if "transferexit" in comment or "transfer exit" in comment:
        return 15.0
    return 5.0


def should_retry_response(frame) -> bool:
    comment = (frame.comment or "").lower()
    expected_payload = decode_single_frame_payload(frame.data)
    return (
        "cleardtc" in comment
        or "clear all dtcs" in comment
        or bool(expected_payload and expected_payload[0] == 0x54)
    )


def is_clear_dtc_request(msg) -> bool:
    payload = decode_single_frame_payload(msg.data)
    return bool(payload and payload[0] == 0x14)


def is_control_dtc_setting_enable_request(msg) -> bool:
    payload = decode_single_frame_payload(msg.data)
    return bool(payload and len(payload) >= 2 and payload[0] == 0x85 and payload[1] == 0x81)


def did_value_bytes(payload: bytes, did: bytes) -> bytes:
    if len(payload) < 3 or payload[0] != 0x62 or payload[1:3] != did:
        return b""
    raw = payload[3:]
    raw = raw.split(b"\x00", 1)[0]
    return raw.rstrip(b"\x55\x00\xff")


def did_value_bytes_from_raw_frames(raw_frames: list[bytes], did: bytes, value_length: int) -> bytes:
    if not value_length:
        return b""

    raw_payload = bytearray()
    for frame_data in raw_frames:
        frame = bytes(frame_data)
        if not frame:
            continue
        pci_nibble = frame[0] >> 4
        if pci_nibble == 0x0:
            raw_payload.extend(frame[1:])
        elif pci_nibble == 0x1:
            raw_payload.extend(frame[2:])
        elif pci_nibble == 0x2:
            raw_payload.extend(frame[1:])

    marker = bytes([0x62]) + did
    pos = bytes(raw_payload).find(marker)
    if pos < 0:
        return b""
    raw = bytes(raw_payload[pos + len(marker):])
    raw = raw.split(b"\x00", 1)[0]
    raw = raw.rstrip(b"\x55\x00\xff")
    if len(raw) < value_length:
        return b""
    return raw


def decode_ascii_did(payload: bytes, did: bytes) -> str:
    raw = did_value_bytes(payload, did)
    if not raw:
        return ""

    try:
        return raw.decode("ascii", errors="replace").strip()
    except Exception:
        return raw.hex(" ").upper()


def decode_did_value(raw: bytes, mode: str) -> str:
    mode = (mode or "ascii").lower()

    if mode == "ascii":
        return raw.decode("ascii", errors="replace").strip()
    if mode == "hex":
        return raw.hex("").upper()
    if mode == "bcd":
        return "".join(f"{byte:02X}" for byte in raw)

    return raw.hex(" ").upper()


def build_did_request(did: bytes, pad_byte: int) -> bytes:
    payload = bytes([0x22]) + did
    if len(payload) > 7:
        raise ValueError("DID request is too long for a single-frame request")
    return bytes([len(payload)]) + payload + bytes([pad_byte] * (8 - 1 - len(payload)))


def prompt_flash_count(file_name: str) -> int:
    prompt = (
        f"[{timestamp()}] How many times should '{file_name}' be flashed? "
        f"(0 to skip, max {MAX_FLASH_REPEAT}, blank=1): "
    )
    while True:
        try:
            answer = input(prompt).strip()
        except EOFError:
            log(f"No input available for {file_name}; defaulting flash count to 1.")
            return 1

        if answer == "":
            return 1

        try:
            count = int(answer)
        except ValueError:
            log("Please enter a whole number.")
            continue

        if 0 <= count <= MAX_FLASH_REPEAT:
            return count
        log(f"Flash count must be between 0 and {MAX_FLASH_REPEAT}.")


def build_live_runtime(profile: dict, ctx) -> LiveRuntime:
    live_cfg = profile.get("live", {})
    timing_cfg = profile.get("timing", {})

    def seconds(name: str, default_ms: int) -> float:
        return int(live_cfg.get(name, default_ms)) / 1000.0

    external_ids = {
        int(value, 16)
        for value in live_cfg.get(
            "external_request_ids",
            [ctx.request_id, ctx.functional_id],
        )
    }

    return LiveRuntime(
        request_id=int(ctx.request_id, 16),
        response_id=int(ctx.response_id, 16),
        functional_id=int(ctx.functional_id, 16),
        p2_timeout=int(timing_cfg.get("p2_timeout_ms", 50)) / 1000.0,
        p2_star_timeout=int(timing_cfg.get("p2_star_timeout_ms", 5000)) / 1000.0,
        recent_tx=[],
        external_count=0,
        external_request_ids=external_ids,
        fail_on_external=bool(live_cfg.get("fail_on_external_tester_traffic", False)),
        drain_before_critical=bool(live_cfg.get("drain_before_critical_requests", True)),
        post_reset_cleanup_delay=seconds("post_reset_cleanup_delay_ms", 5000),
        clear_dtc_retry_delay=seconds("clear_dtc_retry_delay_ms", 3000),
        clear_dtc_retries=int(live_cfg.get("clear_dtc_retries", 2)),
        bus_idle_before_clear_dtc=seconds("bus_idle_before_clear_dtc_ms", 1000),
        bus_idle_max_wait=seconds("bus_idle_max_wait_ms", 5000),
    )


def send_live(bus, msg, runtime: LiveRuntime) -> None:
    bus.send(msg)
    runtime.mark_tx(msg)


def drain_bus(bus, runtime: LiveRuntime, phase: str, max_duration: float = 0.2) -> bool:
    """Drain queued frames before critical requests and warn on external testers."""
    deadline = time.time() + max_duration
    while time.time() < deadline:
        msg = bus.recv(0.0)
        if not msg:
            return True
        if runtime.inspect_external(msg, phase):
            return False
    return True


def wait_for_bus_idle(bus, runtime: LiveRuntime, phase: str) -> bool:
    if runtime.bus_idle_before_clear_dtc <= 0:
        return True

    log(
        f"  Waiting for diagnostic bus idle before {phase} "
        f"({runtime.bus_idle_before_clear_dtc:.1f}s)..."
    )
    idle_start = time.time()
    deadline = time.time() + runtime.bus_idle_max_wait
    saw_external = False

    while time.time() < deadline:
        msg = bus.recv(0.05)
        if not msg:
            if time.time() - idle_start >= runtime.bus_idle_before_clear_dtc:
                return True
            continue

        if runtime.inspect_external(msg, phase):
            return False
        if msg.arbitration_id in runtime.external_request_ids and not runtime.is_own_echo(msg):
            saw_external = True
            idle_start = time.time()

    if saw_external:
        log(f"  WARNING: Bus did not become idle before {phase}.")
    return not runtime.fail_on_external


def is_critical_request(send_data: list[int]) -> bool:
    payload = decode_single_frame_payload(send_data)
    if payload:
        return payload[0] in {0x10, 0x11, 0x14, 0x27, 0x31, 0x34, 0x36, 0x37, 0x83}
    pci = send_data[0] >> 4
    if pci == 0x1 and len(send_data) >= 3:
        return send_data[2] in {0x27, 0x31, 0x34, 0x36, 0x37, 0x83}
    return False


def read_did_live(
    bus,
    runtime: LiveRuntime,
    tx_can_id: int,
    rx_can_id: int,
    did_hex: str,
    pad_byte: int,
    operation_timeout: float,
    label: str,
    decode_mode: str = "ascii",
    value_length: int = 0,
    accepted_dids: set[bytes] | None = None,
) -> str | None:
    did = bytes.fromhex(did_hex)
    accepted_dids = accepted_dids or {did}
    request_data = build_did_request(did, pad_byte)
    msg = can.Message(
        arbitration_id=tx_can_id,
        data=list(request_data),
        is_extended_id=False,
    )

    if runtime.drain_before_critical:
        if not drain_bus(bus, runtime, f"before DID {did_hex.upper()} read"):
            return None

    log(f"Reading ECU DID {did_hex.upper()}")
    send_live(bus, msg, runtime)
    log(f"  Tx: {' '.join(f'{b:02X}' for b in request_data)}")

    expected = bytes([0x01, 0x62]) + bytes([pad_byte] * 6)
    rx_msg = wait_for_response(
        bus,
        rx_can_id,
        expected,
        runtime,
        operation_timeout=operation_timeout,
        tx_can_id=tx_can_id,
    )

    if not rx_msg:
        log(f"  WARN: No response for DID {did_hex.upper()}")
        return None

    log(f"  Rx: {' '.join(f'{b:02X}' for b in rx_msg.msg.data)}")
    negative_response = describe_negative_response(rx_msg.payload)
    if negative_response:
        log(f"  WARN: DID {did_hex.upper()} negative response: {negative_response}")
        return None

    if len(rx_msg.payload) < 3 or rx_msg.payload[0] != 0x62:
        actual = rx_msg.payload[:3].hex(" ").upper() if len(rx_msg.payload) >= 3 else rx_msg.payload.hex(" ").upper()
        log(
            f"  WARN: Ignoring DID {did_hex.upper()} response with unexpected payload prefix: "
            f"{actual}"
        )
        return None

    response_did = rx_msg.payload[1:3]
    if response_did not in accepted_dids:
        log(
            f"  WARN: Ignoring DID {response_did.hex().upper()} response while reading "
            f"DID {did_hex.upper()}; not in configured version DID list."
        )
        return None

    value_bytes = did_value_bytes(rx_msg.payload, response_did)
    if value_length:
        raw_value_bytes = did_value_bytes_from_raw_frames(rx_msg.raw_frames, response_did, value_length)
        if len(raw_value_bytes) > len(value_bytes):
            value_bytes = raw_value_bytes

    if value_length and len(value_bytes) < value_length:
        log(
            f"  WARN: DID {response_did.hex().upper()} returned only {len(value_bytes)} "
            f"byte(s), expected {value_length}; trying next DID."
        )
        return None

    value = decode_did_value(value_bytes, decode_mode) if value_bytes else ""
    if value:
        log(f"  {label} DID {response_did.hex().upper()}: {value}")
        return value

    raw_value = value_bytes.hex(" ").upper() if value_bytes else rx_msg.payload.hex(" ").upper()
    log(f"  {label} DID {response_did.hex().upper()} raw: {raw_value}")
    return raw_value


def read_current_ecu_version(
    bus,
    runtime: LiveRuntime,
    profile: dict,
    ctx,
    tx_can_id: int,
    rx_can_id: int,
    label: str = "Current ECU version",
) -> bool:
    read_cfg = profile.get("read_after_flash", {})
    if not read_cfg.get("enabled", False):
        return True

    dids = read_cfg.get("dids", [])
    if not dids:
        log("  WARN: read_after_flash is enabled, but no DIDs are configured.")
        return False

    operation_timeout = int(read_cfg.get("operation_timeout_ms", 5000)) / 1000.0
    decode_mode = read_cfg.get("decode", "ascii")
    value_length = int(read_cfg.get("value_length", 0))
    accepted_dids = {bytes.fromhex(str(did)) for did in dids}
    for did in dids:
        value = read_did_live(
            bus,
            runtime,
            tx_can_id,
            rx_can_id,
            str(did),
            ctx.pad_byte,
            operation_timeout,
            label,
            decode_mode,
            value_length,
            accepted_dids,
        )
        if value:
            return True

    log("  WARN: No configured ECU version DID returned a usable value.")
    return False


def resolve_security_dll_path(dll_path: str) -> str:
    if os.path.isabs(dll_path):
        return dll_path
    search_paths = [
        os.path.join(ROOT_DIR, dll_path),
        os.path.join(PROFILE_DIR, dll_path),
        os.path.join(PLUGIN_DIR, dll_path),
    ]
    return next((path for path in search_paths if os.path.isfile(path)), search_paths[0])


def validate_live_security_config(profile: dict) -> bool:
    security_cfg = profile.get("security", {})
    if security_cfg.get("enabled") is not True:
        return True

    algorithm = security_cfg.get("algorithm", {})
    if algorithm.get("type", "").lower() != "dll":
        return True

    dll_path = algorithm.get("dll_path", "")
    dll_function = algorithm.get("dll_function", "")
    if not dll_path or not dll_function:
        log("FAILED security preflight: Level 3 DLL configuration is incomplete.")
        log("Set security.algorithm.dll_path and security.algorithm.dll_function in the profile.")
        return False

    resolved_path = resolve_security_dll_path(dll_path)
    if not os.path.isfile(resolved_path):
        log(f"FAILED security preflight: Level 3 DLL not found: {resolved_path}")
        log("Place the DLL in the project folder or set an absolute security.algorithm.dll_path.")
        return False

    return True


def wait_for_flow_control(bus, expected_rx_id: int, runtime: LiveRuntime, timeout: float = 1.0):
    """Wait for a Flow Control (30 xx xx) frame from the ECU."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        msg = bus.recv(0.1)
        if not msg:
            continue
        if runtime.inspect_external(msg, "waiting for FlowControl"):
            return None
        if msg.arbitration_id == expected_rx_id:
            if msg.data and (msg.data[0] >> 4) == 0x3:  # Flow Control NIbble
                return msg
    return None


def wait_for_response(
    bus,
    expected_rx_id: int,
    expected_data: bytes,
    runtime: LiveRuntime,
    operation_timeout: float,
    tx_can_id: int = None,
):
    """Wait for the ECU's response, handling multi-frame ISO-TP and 7F xx 78 (Response Pending)."""
    start_time = time.time()
    absolute_deadline = start_time + operation_timeout
    p2_deadline = start_time + runtime.p2_timeout
    p2_warning_logged = False
    expected_prefix = expected_payload_prefix(expected_data)

    while time.time() < absolute_deadline:
        msg = bus.recv(min(0.1, max(0.0, absolute_deadline - time.time())))
        if not msg:
            if not p2_warning_logged and time.time() >= p2_deadline:
                log(
                    "  WARN: No response inside P2 "
                    f"({runtime.p2_timeout * 1000:.0f}ms); continuing until "
                    f"{operation_timeout:.1f}s operation timeout."
                )
                p2_warning_logged = True
            continue

        if runtime.inspect_external(msg, "waiting for response"):
            return None

        if getattr(msg, "is_error_frame", False):
            log("  WARN: CAN bus error while waiting for ECU response.")
            continue

        if msg.arbitration_id == expected_rx_id:
            pci_nibble = msg.data[0] >> 4
            sf_payload = decode_single_frame_payload(msg.data)

            # Check for ResponsePending (7F xx 78)
            if sf_payload and len(sf_payload) >= 3 and sf_payload[0] == 0x7F and sf_payload[2] == 0x78:
                log("    [ECU indicates Response Pending (78) - Delaying timeout]")
                absolute_deadline = max(
                    absolute_deadline,
                    min(time.time() + runtime.p2_star_timeout, start_time + operation_timeout),
                )
                continue

            # Stop on any other negative response instead of silently advancing.
            if sf_payload and len(sf_payload) >= 3 and sf_payload[0] == 0x7F:
                return ReceivedResponse(msg=msg, payload=sf_payload, raw_frames=[bytes(msg.data)])

            # --- Multi-frame response (First Frame from ECU) ---
            if pci_nibble == 0x1 and tx_can_id is not None:
                total_length = ((msg.data[0] & 0x0F) << 8) | msg.data[1]
                reassembled = bytearray(msg.data[2:8])  # first 6 bytes of payload
                raw_frames = [bytes(msg.data)]

                # Send Flow Control to ECU
                fc_frame = can.Message(
                    arbitration_id=tx_can_id,
                    data=[0x30, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
                    is_extended_id=False
                )
                send_live(bus, fc_frame, runtime)
                log(f"  Tx FC: 30 00 00 00 00 00 00 00")

                # Collect Consecutive Frames
                expected_seq = 1
                cf_timeout = min(time.time() + runtime.p2_star_timeout, absolute_deadline)
                while len(reassembled) < total_length and time.time() < cf_timeout:
                    cf_msg = bus.recv(0.5)
                    if not cf_msg:
                        continue
                    if runtime.inspect_external(cf_msg, "receiving multi-frame response"):
                        return None
                    if cf_msg.arbitration_id == expected_rx_id:
                        cf_pci = cf_msg.data[0] >> 4
                        cf_seq = cf_msg.data[0] & 0x0F
                        if cf_pci == 0x2 and cf_seq == (expected_seq & 0x0F):
                            raw_frames.append(bytes(cf_msg.data))
                            remaining = total_length - len(reassembled)
                            bytes_to_take = min(7, remaining)
                            reassembled.extend(cf_msg.data[1:1 + bytes_to_take])
                            log(f"  Rx CF{expected_seq}: {' '.join(f'{b:02X}' for b in cf_msg.data)}")
                            expected_seq += 1

                full_data = bytes(reassembled[:total_length])
                if expected_prefix and not full_data.startswith(expected_prefix):
                    continue
                return ReceivedResponse(msg=msg, payload=full_data, raw_frames=raw_frames)

            # --- Single Frame response ---
            if sf_payload is None:
                continue
            if expected_prefix and not sf_payload.startswith(expected_prefix):
                continue
            return ReceivedResponse(msg=msg, payload=sf_payload, raw_frames=[bytes(msg.data)])

    return None


def process_live_flash(profile_path: str):
    baudrate = 500000
    profile = load_profile(profile_path)
    ctx = build_runtime_context(profile)
    if not validate_live_security_config(profile):
        return 1
    runtime = build_live_runtime(profile, ctx)

    hex_files = sorted(name for name in os.listdir(FIRMWARE_DIR) if name.lower().endswith(".hex"))
    if not hex_files:
        log(f"[WARN] No .hex files found in: {FIRMWARE_DIR}")
        return 1

    # Initialize PCAN
    try:
        log(f"Initializing PCAN interface at {baudrate} bps...")
        bus = can.interface.Bus(interface='pcan', channel='PCAN_USBBUS1', bitrate=baudrate)
    except Exception as e:
        log(f"FAILED to initialize PCAN: {e}")
        log("Please ensure the PEAK driver is installed and the tool is plugged in.")
        return 1

    expected_rx_id = int(ctx.response_id, 16)
    tx_can_id_int = int(ctx.request_id, 16)

    log("\n--- Reading initial ECU version before flash selection ---")
    if not read_current_ecu_version(bus, runtime, profile, ctx, tx_can_id_int, expected_rx_id, "Initial ECU version"):
        log("ECU not detected. Connect the ECU and retry.")
        bus.shutdown()
        return 1

    flash_counts = {}
    for name in hex_files:
        flash_counts[name] = prompt_flash_count(name)

    if all(count == 0 for count in flash_counts.values()):
        log("No files selected for flashing.")
        bus.shutdown()
        return 0

    for name in hex_files:
        flash_count = flash_counts.get(name, 1)
        if flash_count == 0:
            log(f"\n--- Skipping {name} ---")
            continue

        hex_path = os.path.join(FIRMWARE_DIR, name)
        log(f"\n--- Starting LIVE Flash for {name} ({flash_count} time(s)) ---")

        parsed_segments = parse_intel_hex_segments(hex_path)
        selected_segments = select_flash_segments(parsed_segments, ctx)

        # We reuse hex_parsing's generation! No changes to templates or hex_parsing.
        trace = build_flash_sequence(selected_segments, ctx)

        frames_per_flash = len(trace)
        total_frames = frames_per_flash * flash_count
        log(f"Executing sequence of {frames_per_flash} frames x {flash_count} = {total_frames} frames...")

        # Dynamic seed-key: stores real ISO-TP frames for send_key
        real_send_key_frames = []
        last_tx_msg = None

        for i, frame in enumerate(frame for _ in range(flash_count) for frame in trace):
            try:
                # ── TRANSMIT ──
                if frame.direction == 'Tx':
                    if frame.comment:
                        log(f"\nStep {i+1}/{total_frames}: {frame.comment}")

                    # Replace send_key frames with real computed key
                    send_data = list(frame.data)
                    if real_send_key_frames and 'send key' in (frame.comment or '').lower():
                        send_data = real_send_key_frames.pop(0)
                    elif real_send_key_frames and (frame.data[0] >> 4) == 0x2:
                        # Consecutive frame of send_key (no comment but is a CF)
                        send_data = real_send_key_frames.pop(0)

                    if runtime.drain_before_critical and is_critical_request(send_data):
                        if not drain_bus(bus, runtime, f"before {frame.comment or 'request'}"):
                            bus.shutdown()
                            return 1

                    msg = can.Message(
                        arbitration_id=int(frame.can_id, 16),
                        data=send_data,
                        is_extended_id=False
                    )

                    if is_clear_dtc_request(msg):
                        if not wait_for_bus_idle(bus, runtime, "ClearDTC"):
                            bus.shutdown()
                            return 1

                    send_live(bus, msg, runtime)
                    last_tx_msg = msg
                    log(f"  Tx: {' '.join(f'{b:02X}' for b in send_data)}")

                    if is_control_dtc_setting_enable_request(msg):
                        read_current_ecu_version(
                            bus,
                            runtime,
                            profile,
                            ctx,
                            tx_can_id_int,
                            expected_rx_id,
                            "Post-flash ECU version",
                        )

                    # Handle ISO-TP First Frame Flow Control automatically
                    pci_nibble = send_data[0] >> 4
                    if pci_nibble == 0x1:  # First Frame
                        # We must halt and wait for the ECU to send 30 xx xx
                        fc_msg = wait_for_flow_control(bus, expected_rx_id, runtime, timeout=1.0)
                        if not fc_msg:
                            log(f"  FAIL: Timeout waiting for FlowControl from ECU.")
                            bus.shutdown()
                            return 1
                        log(f"  Rx FC: {' '.join(f'{b:02X}' for b in fc_msg.data)}")
                        # (A full stack would read STmin here and sleep, but we proceed for now)

                # ── RECEIVE ──
                elif frame.direction == 'Rx':
                    if frame.comment:
                        log(f"\nStep {i+1}/{total_frames}: {frame.comment}")

                    # Skip Consecutive Frames and Flow Control frames - already handled
                    pci = frame.data[0] >> 4
                    if pci == 0x2 or pci == 0x3:
                        continue
                    if is_response_pending_frame(frame.data):
                        log("  Trace ResponsePending row skipped; handled while waiting for final response.")
                        continue

                    timeout = response_timeout_for(frame)
                    rx_msg = wait_for_response(
                        bus,
                        expected_rx_id,
                        frame.data,
                        runtime,
                        operation_timeout=timeout,
                        tx_can_id=tx_can_id_int,
                    )
                    if not rx_msg:
                        if should_retry_response(frame) and last_tx_msg is not None:
                            for attempt in range(1, runtime.clear_dtc_retries + 1):
                                log(
                                    "  WARN: No response; "
                                    f"waiting {runtime.clear_dtc_retry_delay:.1f}s "
                                    f"and retrying request ({attempt}/{runtime.clear_dtc_retries})."
                                )
                                time.sleep(runtime.clear_dtc_retry_delay)
                                if is_clear_dtc_request(last_tx_msg):
                                    if not wait_for_bus_idle(bus, runtime, "ClearDTC retry"):
                                        bus.shutdown()
                                        return 1
                                send_live(bus, last_tx_msg, runtime)
                                log(f"  Tx retry: {' '.join(f'{b:02X}' for b in last_tx_msg.data)}")
                                rx_msg = wait_for_response(
                                    bus,
                                    expected_rx_id,
                                    frame.data,
                                    runtime,
                                    operation_timeout=timeout,
                                    tx_can_id=tx_can_id_int,
                                )
                                if rx_msg:
                                    break
                            if not rx_msg:
                                log(f"  FAIL: Timeout waiting for expected ECU response after retry.")
                                log(f"  Expected: {' '.join(f'{b:02X}' for b in frame.data)}")
                                bus.shutdown()
                                return 1
                        else:
                            log(f"  FAIL: Timeout waiting for expected ECU response.")
                            log(f"  Expected: {' '.join(f'{b:02X}' for b in frame.data)}")
                            bus.shutdown()
                            return 1

                    log(f"  Rx: {' '.join(f'{b:02X}' for b in rx_msg.msg.data)}")

                    negative_response = describe_negative_response(rx_msg.payload)
                    if negative_response:
                        log(f"  FAIL: ECU negative response: {negative_response}")
                        bus.shutdown()
                        return 1

                    # --- Detect SecurityAccess seed response and compute real key ---
                    payload = rx_msg.payload

                    if payload and len(payload) >= 3 and payload[0] == 0x67:
                        seed = payload[2:]  # Skip 67 and subfunction byte
                        log(f"  REAL SEED: {' '.join(f'{b:02X}' for b in seed)}")
                        real_key = build_security_key(ctx, seed)
                        log(f"  COMPUTED KEY: {' '.join(f'{b:02X}' for b in real_key)}")
                        # Build real send_key ISO-TP frames
                        sf_byte = int(profile['security']['send_key']['subfunction'], 16)
                        send_key_payload = bytes([0x27, sf_byte]) + real_key
                        real_send_key_frames = isotp_encode(send_key_payload, ctx.pad_byte)
                        # Delay before sending key — ECU needs time to process seed internally
                        security_key_delay = int(profile.get("timing", {}).get("security_key_delay_ms", 50)) / 1000.0
                        if security_key_delay > 0:
                            log(f"  Waiting {security_key_delay*1000:.0f}ms before sending key...")
                            time.sleep(security_key_delay)
                    elif payload and len(payload) >= 2 and payload[0] == 0x51:
                        if runtime.post_reset_cleanup_delay > 0:
                            log(
                                "  ECU reset acknowledged; waiting "
                                f"{runtime.post_reset_cleanup_delay:.1f}s before cleanup."
                            )
                            time.sleep(runtime.post_reset_cleanup_delay)

            except Exception as e:
                log(f"EXECUTION ERROR at frame {i}: {e}")
                bus.shutdown()
                return 1

    log("\n--- Live Flashing Sequence Completed Successfully ---")
    bus.shutdown()
    return 0


def parse_args():
    parser = argparse.ArgumentParser(description="Live PCAN Flashing execution using pre-built trace payloads.")
    parser.add_argument(
        "--profile",
        default=DEFAULT_PROFILE,
        help="Path to OEM profile JSON file.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    sys.exit(process_live_flash(os.path.abspath(args.profile)))
