"""
live_flasher.py — Dashboard-integrated adapter for the CAN live flasher engine.

This module bridges the full-featured CAN live flasher (can_live_flasher.py)
with the FYI Dashboard's API routes for progress reporting and CAN trace logging.

When PCAN hardware is available, it executes the real UDS flash sequence.
When hardware is unavailable, the caller (api_routes.py) falls back to simulation.
"""

import os
import sys
import time

try:
    import can
except ImportError:
    can = None

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
)

from core.can_live_flasher import (
    ReceivedResponse,
    LiveRuntime,
    build_live_runtime,
    validate_live_security_config,
    read_current_ecu_version,
    send_live,
    drain_bus,
    wait_for_bus_idle,
    wait_for_flow_control,
    wait_for_response,
    is_critical_request,
    is_clear_dtc_request,
    is_control_dtc_setting_enable_request,
    is_response_pending_frame,
    response_timeout_for,
    should_retry_response,
    describe_negative_response,
    decode_single_frame_payload,
    log as can_log,
)

import core.api_routes as api


def process_live_flash(profile_path: str, files_data, times):
    """
    Execute a live UDS flash sequence on PCAN hardware, reporting progress
    and CAN trace events to the dashboard's api_routes module.

    Args:
        profile_path: Path to the OEM profile JSON.
        files_data: List of dicts with 'name' key for each hex file.
        times: Number of times to repeat the full sequence.

    Returns:
        True on success, False on failure (caller should fall back to simulation).
    """
    if can is None:
        print("[BACKEND] python-can not installed — cannot use PCAN hardware.")
        return False

    baudrate = 500000
    profile = load_profile(profile_path)
    ctx = build_runtime_context(profile)

    if not validate_live_security_config(profile):
        api.push_trace("EVT", "—", "—", "FAILED: Security configuration validation failed.")
        return False

    runtime = build_live_runtime(profile, ctx)

    hex_files = [f["name"] for f in files_data]
    if not hex_files:
        return False

    # Initialize PCAN
    try:
        api.push_trace("EVT", "—", "—", f"Initializing PCAN at {baudrate} bps...")
        bus = can.interface.Bus(interface='pcan', channel='PCAN_USBBUS1', bitrate=baudrate)
    except Exception as e:
        api.push_trace("EVT", "—", "—", f"PCAN init failed: {e}. Falling back to simulation.")
        return False

    expected_rx_id = int(ctx.response_id, 16)
    tx_can_id_int = int(ctx.request_id, 16)

    # Pre-flash ECU version read
    api.push_trace("EVT", "—", "—", "Reading initial ECU version...")
    read_current_ecu_version(bus, runtime, profile, ctx, tx_can_id_int, expected_rx_id, "Initial ECU version")

    total_files = len(hex_files) * times
    api.flash_session['total_ops'] = total_files
    if not api.flash_session.get('master_start'):
        api.flash_session['master_start'] = time.time()
    inter_file_delay = int(profile.get("live", {}).get("inter_file_delay_ms", 1500)) / 1000.0

    for t in range(times):
        if api.flash_session.get('force_stop'): break
        for idx, name in enumerate(hex_files):
            if api.flash_session.get('force_stop'): break
            global_completed = (t * len(hex_files)) + idx
            if global_completed > 0 and inter_file_delay > 0:
                api.push_trace("EVT", "â€”", "â€”", f"Waiting {inter_file_delay:.1f}s for ECU to settle before next file...")
                time.sleep(inter_file_delay)

            api.flash_session['current_op'] = global_completed + 1
            api.flash_session['swFile'] = name
            api.flash_session['progress'] = 0.0
            api.flash_session['elapsedMs'] = 0
            op_start = int(time.time() * 1000)

            # Start per-file trace capture
            api.start_file_trace()

            hex_path = os.path.join(FIRMWARE_DIR, name)
            if not os.path.exists(hex_path):
                api.push_trace("EVT", "—", "—", f"File not found: {hex_path}")
                api.abort_file_trace()
                return False

            parsed_segments = parse_intel_hex_segments(hex_path)
            selected_segments = select_flash_segments(parsed_segments, ctx)
            trace = build_flash_sequence(selected_segments, ctx)
            total_frames = len(trace)

            api.push_trace("EVT", "—", "—", f"Executing {total_frames} frames for {name}")

            # Dynamic seed-key: stores real ISO-TP frames for send_key
            real_send_key_frames = []
            last_tx_msg = None

            for i, frame in enumerate(trace):
                if api.flash_session.get('force_stop'):
                    api.push_trace("EVT", "—", "—", "Force stop requested. Flash sequence aborted by operator.")
                    api.abort_file_trace()
                    api.finish_flash_session(completed=False)
                    bus.shutdown()
                    return True

                # Update Progress
                p = (i / total_frames) * 100.0
                api.flash_session['progress'] = p
                api.flash_session['elapsedMs'] = int(time.time() * 1000) - op_start
                current_fraction = (global_completed + (i / total_frames)) / total_files
                api.flash_session['total_progress'] = current_fraction * 100.0
                elapsed_total = time.time() - api.flash_session['master_start']
                if current_fraction > 0:
                    api.flash_session['eta_seconds'] = int((elapsed_total / current_fraction) - elapsed_total)

                try:
                    # ── TRANSMIT ──
                    if frame.direction == 'Tx':
                        if frame.comment:
                            api.push_trace("EVT", "—", "—", f"Step {i+1}/{total_frames}: {frame.comment}")

                        # Replace send_key frames with real computed key
                        send_data = list(frame.data)
                        if real_send_key_frames and 'send key' in (frame.comment or '').lower():
                            send_data = real_send_key_frames.pop(0)
                        elif real_send_key_frames and (frame.data[0] >> 4) == 0x2:
                            send_data = real_send_key_frames.pop(0)

                        if runtime.drain_before_critical and is_critical_request(send_data):
                            if not drain_bus(bus, runtime, f"before {frame.comment or 'request'}"):
                                api.push_trace("EVT", "—", "—", "FAIL: External tester traffic detected.")
                                api.abort_file_trace()
                                bus.shutdown()
                                return False

                        msg = can.Message(
                            arbitration_id=int(frame.can_id, 16),
                            data=send_data,
                            is_extended_id=False
                        )

                        if is_clear_dtc_request(msg):
                            if not wait_for_bus_idle(bus, runtime, "ClearDTC"):
                                api.push_trace("EVT", "—", "—", "FAIL: Bus not idle before ClearDTC.")
                                api.abort_file_trace()
                                bus.shutdown()
                                return False

                        send_live(bus, msg, runtime)
                        last_tx_msg = msg

                        data_hex = ' '.join(f'{b:02X}' for b in send_data)
                        api.push_trace("TX", hex(msg.arbitration_id)[2:].upper(), data_hex, frame.comment)

                        if is_control_dtc_setting_enable_request(msg):
                            read_current_ecu_version(
                                bus, runtime, profile, ctx,
                                tx_can_id_int, expected_rx_id,
                                "Post-flash ECU version",
                            )

                        # Handle ISO-TP First Frame Flow Control
                        pci_nibble = send_data[0] >> 4
                        if pci_nibble == 0x1:
                            fc_msg = wait_for_flow_control(bus, expected_rx_id, runtime, timeout=1.0)
                            if not fc_msg:
                                api.push_trace("EVT", "—", "—", "FAIL: Timeout waiting for FlowControl from ECU.")
                                api.abort_file_trace()
                                bus.shutdown()
                                return False
                            fc_data_hex = ' '.join(f'{b:02X}' for b in fc_msg.data)
                            api.push_trace("RX", hex(fc_msg.arbitration_id)[2:].upper(), fc_data_hex, "FlowControl")

                    # ── RECEIVE ──
                    elif frame.direction == 'Rx':
                        # Skip Consecutive Frames and Flow Control frames - already handled
                        pci = frame.data[0] >> 4
                        if pci == 0x2 or pci == 0x3:
                            continue
                        if is_response_pending_frame(frame.data):
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
                                    api.push_trace("EVT", "—", "—",
                                        f"No response; retrying ({attempt}/{runtime.clear_dtc_retries})...")
                                    time.sleep(runtime.clear_dtc_retry_delay)
                                    if is_clear_dtc_request(last_tx_msg):
                                        if not wait_for_bus_idle(bus, runtime, "ClearDTC retry"):
                                            api.abort_file_trace()
                                            bus.shutdown()
                                            return False
                                    send_live(bus, last_tx_msg, runtime)
                                    retry_hex = ' '.join(f'{b:02X}' for b in last_tx_msg.data)
                                    api.push_trace("TX", hex(last_tx_msg.arbitration_id)[2:].upper(), retry_hex, "Retry")
                                    rx_msg = wait_for_response(
                                        bus, expected_rx_id, frame.data, runtime,
                                        operation_timeout=timeout, tx_can_id=tx_can_id_int,
                                    )
                                    if rx_msg:
                                        break
                                if not rx_msg:
                                    expected_hex = ' '.join(f'{b:02X}' for b in frame.data)
                                    api.push_trace("EVT", "—", "—", f"FAIL: Timeout after retry. Expected: {expected_hex}")
                                    api.abort_file_trace()
                                    bus.shutdown()
                                    return False
                            else:
                                expected_hex = ' '.join(f'{b:02X}' for b in frame.data)
                                api.push_trace("EVT", "—", "—", f"FAIL: Timeout waiting for ECU response: {expected_hex}")
                                api.abort_file_trace()
                                bus.shutdown()
                                return False

                        rx_data_hex = ' '.join(f'{b:02X}' for b in rx_msg.msg.data)
                        api.push_trace("RX", hex(rx_msg.msg.arbitration_id)[2:].upper(), rx_data_hex, frame.comment)

                        negative_response = describe_negative_response(rx_msg.payload)
                        if negative_response:
                            api.push_trace("EVT", "—", "—", f"FAIL: ECU negative response: {negative_response}")
                            api.abort_file_trace()
                            bus.shutdown()
                            return False

                        # --- Detect SecurityAccess seed response and compute real key ---
                        payload = rx_msg.payload
                        if payload and len(payload) >= 3 and payload[0] == 0x67:
                            seed = payload[2:]
                            seed_hex = ' '.join(f'{b:02X}' for b in seed)
                            api.push_trace("EVT", "—", "—", f"REAL SEED: {seed_hex}")
                            real_key = build_security_key(ctx, seed)
                            key_hex = ' '.join(f'{b:02X}' for b in real_key)
                            api.push_trace("EVT", "—", "—", f"COMPUTED KEY: {key_hex}")
                            sf_byte = int(profile['security']['send_key']['subfunction'], 16)
                            send_key_payload = bytes([0x27, sf_byte]) + real_key
                            real_send_key_frames = isotp_encode(send_key_payload, ctx.pad_byte)
                        elif payload and len(payload) >= 2 and payload[0] == 0x51:
                            if runtime.post_reset_cleanup_delay > 0:
                                api.push_trace("EVT", "—", "—",
                                    f"ECU reset acknowledged; waiting {runtime.post_reset_cleanup_delay:.1f}s")
                                time.sleep(runtime.post_reset_cleanup_delay)

                except Exception as e:
                    api.push_trace("EVT", "—", "—", f"EXECUTION ERROR at frame {i}: {e}")
                    api.abort_file_trace()
                    bus.shutdown()
                    return False

            api.flash_session['progress'] = 100.0
            api.flash_session['flashCount'] += 1
            fc = api.flash_session['flashCount']
            api.nvm_memory["F190"] = [(fc >> 8) & 0xFF, fc & 0xFF]

            log_id = int(time.time() * 1000)
            elapsed_ms = api.flash_session['elapsedMs']
            log_entry = {
                "id": log_id,
                "swFile": name,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "duration": f"{elapsed_ms // 1000}.{(elapsed_ms % 1000)//100}s",
                "duration_ms": elapsed_ms,
                "status": "success",
                "has_trace": True
            }
            api.flash_session['sessionLog'].insert(0, log_entry)

            # Save per-file trace snapshot
            log_entry["has_trace"] = api.finish_file_trace(log_id)

    api.finish_flash_session(completed=not api.flash_session.get('force_stop'))
    bus.shutdown()
    return True
