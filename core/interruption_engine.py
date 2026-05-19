"""
interruption_engine.py — Erase Phase Interruption Test Engine

Follows the EXACT same UDS flashing protocol as multiflash (process_live_flash),
but monitors for the erase phase (RoutineControl 0x31 0x01) and forces an
interruption when the ECU sends NRC ResponsePending (0x78) during erase.

Preconditions checked:
  1. Vbatt ON (implicit - ECU responds)
  2. Ignition ON (implicit - ECU responds)
  3. ECU connected (verified via TesterPresent)
  4. CAN communication established (PCAN init + TesterPresent positive response)
  5. SW version before flashing (read and stored)

Actions:
  1. Start flashing the selected hex file (same protocol as multiflash)
  2. After erase phase request (0x31 0x01), force stop on 0x78 NRC
  3. Wait 1-3 seconds for ECU recovery
  4. CCM check (TesterPresent 0x3E)
  5. Session check (DiagSessionControl 0x10 0x01)
  6. SW version check (must match pre-flash version)

Expected Results:
  1. Positive response from TesterPresent
  2. Positive response for session check
  3. SW version matches pre-flash version
"""

import os
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
    FIRMWARE_DIR,
)

from core.can_live_flasher import (
    ReceivedResponse,
    build_live_runtime,
    validate_live_security_config,
    read_current_ecu_version,
    read_did_live,
    send_live,
    drain_bus,
    wait_for_bus_idle,
    wait_for_flow_control,
    wait_for_response,
    is_critical_request,
    is_clear_dtc_request,
    is_control_dtc_setting_enable_request,
    is_ecu_reset_response,
    is_response_pending_frame,
    response_timeout_for,
    should_retry_response,
    describe_negative_response,
    decode_single_frame_payload,
    build_did_request,
)

import core.api_routes as api


def _read_sw_version_string(bus, runtime, profile, ctx, tx_can_id, rx_can_id):
    """Read the ECU SW version and return it as a string (or None)."""
    read_cfg = profile.get("read_after_flash", {})
    if not read_cfg.get("enabled", False):
        return None
    dids = read_cfg.get("dids", [])
    if not dids:
        return None
    operation_timeout = int(read_cfg.get("operation_timeout_ms", 5000)) / 1000.0
    decode_mode = read_cfg.get("decode", "ascii")
    value_length = int(read_cfg.get("value_length", 0))
    accepted_dids = {bytes.fromhex(str(did)) for did in dids}
    for did in dids:
        value = read_did_live(
            bus, runtime, tx_can_id, rx_can_id,
            str(did), ctx.pad_byte, operation_timeout,
            "SW Version", decode_mode, value_length, accepted_dids,
        )
        if value:
            return value
    return None


def _check_tester_present(bus, runtime, tx_can_id, rx_can_id):
    """Send TesterPresent (0x3E 0x80) and check for positive response."""
    tp_data = [0x02, 0x3E, 0x80, 0x00, 0x00, 0x00, 0x00, 0x00]
    tp_msg = can.Message(arbitration_id=tx_can_id, data=tp_data, is_extended_id=False)
    send_live(bus, tp_msg, runtime)
    data_hex = ' '.join(f'{b:02X}' for b in tp_data)
    api.push_trace("TX", hex(tx_can_id)[2:].upper(), data_hex, "TesterPresent (0x3E)")

    rx = wait_for_response(
        bus, rx_can_id, [0x02, 0x7E, 0x00], runtime,
        operation_timeout=2.0, tx_can_id=tx_can_id,
    )
    if rx:
        rx_hex = ' '.join(f'{b:02X}' for b in rx.msg.data)
        api.push_trace("RX", hex(rx.msg.arbitration_id)[2:].upper(), rx_hex, "✅ Positive Response (0x7E)")
        return True
    else:
        api.push_trace("EVT", "—", "—", "❌ FAILED: No TesterPresent response")
        return False


def _check_default_session(bus, runtime, tx_can_id, rx_can_id):
    """Send DiagSessionControl Default (0x10 0x01) and check for positive response."""
    dsc_data = [0x02, 0x10, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00]
    dsc_msg = can.Message(arbitration_id=tx_can_id, data=dsc_data, is_extended_id=False)
    send_live(bus, dsc_msg, runtime)
    data_hex = ' '.join(f'{b:02X}' for b in dsc_data)
    api.push_trace("TX", hex(tx_can_id)[2:].upper(), data_hex, "DiagSessionControl Default (0x10 0x01)")

    rx = wait_for_response(
        bus, rx_can_id, [0x06, 0x50, 0x01], runtime,
        operation_timeout=2.0, tx_can_id=tx_can_id,
    )
    if rx:
        rx_hex = ' '.join(f'{b:02X}' for b in rx.msg.data)
        api.push_trace("RX", hex(rx.msg.arbitration_id)[2:].upper(), rx_hex, "✅ Positive Response (0x50)")
        return True
    else:
        api.push_trace("EVT", "—", "—", "❌ FAILED: No Session Control response")
        return False


def _is_erase_routine_request(send_data):
    """Check if this TX frame is a RoutineControl StartRoutine (0x31 0x01) — the erase request."""
    payload = decode_single_frame_payload(send_data)
    if payload and len(payload) >= 2 and payload[0] == 0x31 and payload[1] == 0x01:
        return True
    # Multi-frame: check byte index 2 for 0x31 and 3 for 0x01
    pci = send_data[0] >> 4
    if pci == 0x1 and len(send_data) >= 4 and send_data[2] == 0x31 and send_data[3] == 0x01:
        return True
    return False


def run_erase_interruption(profile, test_id, file_obj):
    """
    Execute Erase Phase Interruption Test.
    
    Uses the EXACT same flashing protocol as multiflash but monitors
    for the erase phase and interrupts when 0x78 NRC is received.
    """
    if can is None:
        api.push_trace("EVT", "—", "—", "FAILED: python-can not installed")
        return False

    baudrate = 500000
    ctx = build_runtime_context(profile)

    if not validate_live_security_config(profile):
        api.push_trace("EVT", "—", "—", "FAILED: Security configuration validation failed")
        return False

    runtime = build_live_runtime(profile, ctx)

    fname = "Interruption_Test"
    if file_obj and file_obj.get("name"):
        fname = file_obj["name"]

    hex_path = os.path.join(FIRMWARE_DIR, fname)
    if not os.path.exists(hex_path):
        api.push_trace("EVT", "—", "—", f"FAILED: File not found: {fname}")
        return False

    # --- Initialize PCAN ---
    try:
        api.push_trace("EVT", "—", "—", f"Initializing PCAN at {baudrate} bps...")
        bus = can.interface.Bus(interface='pcan', channel='PCAN_USBBUS1', bitrate=baudrate)
    except Exception as e:
        api.push_trace("EVT", "—", "—", f"FAILED: PCAN init failed: {e}")
        return False

    expected_rx_id = int(ctx.response_id, 16)
    tx_can_id_int = int(ctx.request_id, 16)

    api.interruption_session['swFile'] = fname
    api.interruption_session['progress'] = 0.0
    api.interruption_session['total_progress'] = 0.0
    api.interruption_session['elapsedMs'] = 0
    api.interruption_session['running'] = True
    op_start = int(time.time() * 1000)

    api.start_file_trace()

    interrupted = False
    pre_flash_version = None
    post_flash_version = None
    ccm_pass = False
    session_pass = False
    version_match = False

    try:
        # ============================================================
        # PRECONDITION CHECKS
        # ============================================================
        api.push_trace("EVT", "—", "—", "═══ PRECONDITION CHECKS ═══")

        # 1-2. Vbatt + Ignition (verified by ECU responding to TesterPresent)
        # 3-4. ECU connected + CAN communication
        api.push_trace("EVT", "—", "—", "Checking ECU connectivity (TesterPresent)...")
        if not _check_tester_present(bus, runtime, tx_can_id_int, expected_rx_id):
            raise RuntimeError("Precondition FAILED: ECU not responding. Check Vbatt, Ignition, CAN connection.")

        api.push_trace("EVT", "—", "—", "✅ Vbatt=ON, Ignition=ON, ECU Connected, CAN OK")

        # 5. Read SW version before flashing
        api.push_trace("EVT", "—", "—", "Reading SW version before flashing...")
        pre_flash_version = _read_sw_version_string(bus, runtime, profile, ctx, tx_can_id_int, expected_rx_id)
        if pre_flash_version:
            api.push_trace("EVT", "—", "—", f"✅ Pre-flash SW Version: {pre_flash_version}")
        else:
            api.push_trace("EVT", "—", "—", "⚠ Could not read SW version (DID not configured or no response)")

        api.push_trace("EVT", "—", "—", "═══ ALL PRECONDITIONS PASSED ═══")

        # ============================================================
        # ACTION: Start flashing (same protocol as multiflash)
        # ============================================================
        api.push_trace("EVT", "—", "—", "═══ STARTING FLASH SEQUENCE (Erase Phase Interruption) ═══")

        parsed_segments = parse_intel_hex_segments(hex_path)
        selected_segments = select_flash_segments(parsed_segments, ctx)
        trace = build_flash_sequence(selected_segments, ctx)
        total_frames = len(trace)

        api.push_trace("EVT", "—", "—", f"Executing {total_frames} frames for {fname}")

        real_send_key_frames = []
        last_tx_msg = None
        in_erase_phase = False

        for i, frame in enumerate(trace):
            if api.interruption_session.get('force_stop'):
                api.push_trace("EVT", "—", "—", "Force stop requested by operator")
                break

            p = (i / total_frames) * 100.0
            api.interruption_session['progress'] = p
            api.interruption_session['total_progress'] = p
            api.interruption_session['elapsedMs'] = int(time.time() * 1000) - op_start

            # ── TRANSMIT (mirrors multiflash exactly) ──
            if frame.direction == 'Tx':
                if frame.comment:
                    api.push_trace("EVT", "—", "—", f"Step {i+1}/{total_frames}: {frame.comment}")

                send_data = list(frame.data)
                if real_send_key_frames and 'send key' in (frame.comment or '').lower():
                    send_data = real_send_key_frames.pop(0)
                elif real_send_key_frames and (frame.data[0] >> 4) == 0x2:
                    send_data = real_send_key_frames.pop(0)

                if runtime.drain_before_critical and is_critical_request(send_data):
                    if not drain_bus(bus, runtime, f"before {frame.comment or 'request'}"):
                        raise RuntimeError("External tester traffic detected")

                msg = can.Message(
                    arbitration_id=int(frame.can_id, 16),
                    data=send_data,
                    is_extended_id=False
                )

                if is_clear_dtc_request(msg):
                    if not wait_for_bus_idle(bus, runtime, "ClearDTC"):
                        raise RuntimeError("Bus not idle before ClearDTC")

                # Detect erase phase
                if _is_erase_routine_request(send_data):
                    in_erase_phase = True
                    api.push_trace("EVT", "—", "—", "⚡ ERASE PHASE DETECTED — Monitoring for 0x78 NRC...")

                send_live(bus, msg, runtime)
                last_tx_msg = msg

                data_hex = ' '.join(f'{b:02X}' for b in send_data)
                api.push_trace("TX", hex(msg.arbitration_id)[2:].upper(), data_hex, frame.comment)

                # Handle ISO-TP First Frame Flow Control
                pci_nibble = send_data[0] >> 4
                if pci_nibble == 0x1:
                    fc_msg = wait_for_flow_control(bus, expected_rx_id, runtime, timeout=1.0)
                    if not fc_msg:
                        raise RuntimeError("Timeout waiting for FlowControl from ECU")
                    fc_hex = ' '.join(f'{b:02X}' for b in fc_msg.data)
                    api.push_trace("RX", hex(fc_msg.arbitration_id)[2:].upper(), fc_hex, "FlowControl")

            # ── RECEIVE (mirrors multiflash, but with erase interrupt) ──
            elif frame.direction == 'Rx':
                pci = frame.data[0] >> 4
                if pci == 0x2 or pci == 0x3:
                    continue
                if is_response_pending_frame(frame.data):
                    continue

                timeout = response_timeout_for(frame)

                # If in erase phase, use custom wait that catches 0x78
                if in_erase_phase:
                    rx_msg = _wait_for_response_with_interrupt(
                        bus, expected_rx_id, frame.data, runtime,
                        timeout, tx_can_id_int
                    )
                    if rx_msg == "INTERRUPTED":
                        interrupted = True
                        break
                    in_erase_phase = False  # Past erase phase now
                else:
                    rx_msg = wait_for_response(
                        bus, expected_rx_id, frame.data, runtime,
                        operation_timeout=timeout, tx_can_id=tx_can_id_int,
                    )

                if not rx_msg:
                    if is_ecu_reset_response(frame):
                        api.push_trace("EVT", "—", "—", "No ECUReset response (ECU rebooting — normal)")
                        if runtime.post_reset_cleanup_delay > 0:
                            time.sleep(runtime.post_reset_cleanup_delay)
                        continue
                    elif should_retry_response(frame) and last_tx_msg is not None:
                        for attempt in range(1, runtime.clear_dtc_retries + 1):
                            api.push_trace("EVT", "—", "—", f"No response; retrying ({attempt}/{runtime.clear_dtc_retries})...")
                            time.sleep(runtime.clear_dtc_retry_delay)
                            send_live(bus, last_tx_msg, runtime)
                            rx_msg = wait_for_response(
                                bus, expected_rx_id, frame.data, runtime,
                                operation_timeout=timeout, tx_can_id=tx_can_id_int,
                            )
                            if rx_msg:
                                break
                        if not rx_msg:
                            expected_hex = ' '.join(f'{b:02X}' for b in frame.data)
                            raise RuntimeError(f"Timeout after retry. Expected: {expected_hex}")
                    else:
                        expected_hex = ' '.join(f'{b:02X}' for b in frame.data)
                        raise RuntimeError(f"Timeout waiting for ECU response: {expected_hex}")

                rx_hex = ' '.join(f'{b:02X}' for b in rx_msg.msg.data)
                api.push_trace("RX", hex(rx_msg.msg.arbitration_id)[2:].upper(), rx_hex, frame.comment)

                negative_response = describe_negative_response(rx_msg.payload)
                if negative_response:
                    raise RuntimeError(f"ECU negative response: {negative_response}")

                # Detect SecurityAccess seed and compute real key
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
                    security_key_delay = int(profile.get("timing", {}).get("security_key_delay_ms", 50)) / 1000.0
                    if security_key_delay > 0:
                        time.sleep(security_key_delay)
                elif payload and len(payload) >= 2 and payload[0] == 0x51:
                    if runtime.post_reset_cleanup_delay > 0:
                        time.sleep(runtime.post_reset_cleanup_delay)

    except Exception as e:
        api.push_trace("EVT", "—", "—", f"Sequence aborted: {e}")

    # ============================================================
    # POST-INTERRUPTION VERIFICATION
    # ============================================================
    if interrupted:
        api.interruption_session['progress'] = 60.0
        api.interruption_session['total_progress'] = 60.0

        recovery_wait = 2.0
        api.push_trace("EVT", "—", "—", f"═══ INTERRUPTION TRIGGERED — Waiting {recovery_wait}s for ECU recovery ═══")
        time.sleep(recovery_wait)

        api.push_trace("EVT", "—", "—", "═══ POST-INTERRUPTION CHECKS ═══")

        # Check 1: CCM (TesterPresent)
        api.push_trace("EVT", "—", "—", "CHECK 1: CCM Communication (TesterPresent)...")
        ccm_pass = _check_tester_present(bus, runtime, tx_can_id_int, expected_rx_id)
        api.interruption_session['progress'] = 70.0

        # Check 2: Session Check
        api.push_trace("EVT", "—", "—", "CHECK 2: Session Check (Default Session)...")
        session_pass = _check_default_session(bus, runtime, tx_can_id_int, expected_rx_id)
        api.interruption_session['progress'] = 80.0

        # Check 3: SW Version Check
        api.push_trace("EVT", "—", "—", "CHECK 3: Software Version Check...")
        post_flash_version = _read_sw_version_string(bus, runtime, profile, ctx, tx_can_id_int, expected_rx_id)
        if post_flash_version:
            api.push_trace("EVT", "—", "—", f"Post-Interruption SW Version: {post_flash_version}")
            if pre_flash_version and post_flash_version == pre_flash_version:
                version_match = True
                api.push_trace("EVT", "—", "—", f"✅ SW Version MATCH: {post_flash_version} == {pre_flash_version}")
            elif pre_flash_version:
                api.push_trace("EVT", "—", "—", f"❌ SW Version MISMATCH: {post_flash_version} != {pre_flash_version}")
            else:
                api.push_trace("EVT", "—", "—", "⚠ Cannot compare — pre-flash version was not available")
        else:
            api.push_trace("EVT", "—", "—", "❌ FAILED: Could not read post-interruption SW version")
        api.interruption_session['progress'] = 90.0

        # Summary
        api.push_trace("EVT", "—", "—", "═══ TEST RESULTS ═══")
        api.push_trace("EVT", "—", "—", f"  CCM (TesterPresent): {'✅ PASS' if ccm_pass else '❌ FAIL'}")
        api.push_trace("EVT", "—", "—", f"  Session Check:       {'✅ PASS' if session_pass else '❌ FAIL'}")
        api.push_trace("EVT", "—", "—", f"  SW Version Match:    {'✅ PASS' if version_match else '❌ FAIL'}")

        all_pass = ccm_pass and session_pass and version_match
        if all_pass:
            api.push_trace("EVT", "—", "—", "═══ ✅ ERASE PHASE INTERRUPTION TEST: PASSED ═══")
        else:
            api.push_trace("EVT", "—", "—", "═══ ❌ ERASE PHASE INTERRUPTION TEST: FAILED ═══")

    # ============================================================
    # RECORD RESULT
    # ============================================================
    api.interruption_session['elapsedMs'] = int(time.time() * 1000) - op_start
    elapsed_ms = api.interruption_session['elapsedMs']
    log_id = int(time.time() * 1000)

    if interrupted:
        all_pass = ccm_pass and session_pass and version_match
        result_status = "passed" if all_pass else "failed"
    else:
        result_status = "failed"

    api.last_interruption_result = {
        "testId": test_id,
        "result": result_status,
        "interrupted": interrupted,
        "ccm_pass": ccm_pass,
        "session_pass": session_pass,
        "version_match": version_match,
        "pre_version": pre_flash_version,
        "post_version": post_flash_version,
    }

    test_obj = next((t for t in api.interruption_tests if t["id"] == test_id), None)
    if test_obj:
        test_obj["status"] = result_status

    api.interruption_session['progress'] = 100.0
    api.interruption_session['total_progress'] = 100.0

    log_entry = {
        "id": log_id,
        "swFile": fname,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "duration": f"{elapsed_ms // 1000}.{(elapsed_ms % 1000)//100}s",
        "duration_ms": elapsed_ms,
        "status": result_status,
        "has_trace": api.finish_file_trace(log_id)
    }
    api.interruption_session['sessionLog'].insert(0, log_entry)

    time.sleep(0.1)
    api.interruption_session['running'] = False
    bus.shutdown()
    return True


def _wait_for_response_with_interrupt(bus, expected_rx_id, expected_data, runtime, timeout, tx_can_id):
    """
    Custom wait_for_response that intercepts NRC 0x78 during erase phase.
    Returns "INTERRUPTED" string if 0x78 is caught, otherwise returns ReceivedResponse or None.
    """
    from core.can_live_flasher import expected_payload_prefix

    start_time = time.time()
    absolute_deadline = start_time + timeout
    prefix = expected_payload_prefix(expected_data)

    while time.time() < absolute_deadline:
        msg = bus.recv(min(0.1, max(0.0, absolute_deadline - time.time())))
        if not msg:
            continue

        if getattr(msg, "is_error_frame", False):
            continue

        if msg.arbitration_id == expected_rx_id:
            sf_payload = decode_single_frame_payload(msg.data)

            # Check for ResponsePending 0x78 — THIS IS THE INTERRUPT TRIGGER
            if sf_payload and len(sf_payload) >= 3 and sf_payload[0] == 0x7F and sf_payload[2] == 0x78:
                rx_hex = ' '.join(f'{b:02X}' for b in msg.data)
                api.push_trace("RX", hex(msg.arbitration_id)[2:].upper(), rx_hex, "NRC ResponsePending (0x78)")
                api.push_trace("EVT", "—", "—", "⚡⚡⚡ 0x78 RECEIVED DURING ERASE — FORCING INTERRUPTION ⚡⚡⚡")
                return "INTERRUPTED"

            # Any other negative response
            if sf_payload and len(sf_payload) >= 3 and sf_payload[0] == 0x7F:
                return ReceivedResponse(msg=msg, payload=sf_payload, raw_frames=[bytes(msg.data)])

            # Multi-frame First Frame
            pci_nibble = msg.data[0] >> 4
            if pci_nibble == 0x1 and tx_can_id is not None:
                total_length = ((msg.data[0] & 0x0F) << 8) | msg.data[1]
                reassembled = bytearray(msg.data[2:8])
                raw_frames = [bytes(msg.data)]

                fc_frame = can.Message(
                    arbitration_id=tx_can_id,
                    data=[0x30, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
                    is_extended_id=False
                )
                send_live(bus, fc_frame, runtime)

                expected_seq = 1
                cf_timeout = min(time.time() + runtime.p2_star_timeout, absolute_deadline)
                while len(reassembled) < total_length and time.time() < cf_timeout:
                    cf_msg = bus.recv(0.5)
                    if not cf_msg:
                        continue
                    if cf_msg.arbitration_id == expected_rx_id:
                        cf_pci = cf_msg.data[0] >> 4
                        cf_seq = cf_msg.data[0] & 0x0F
                        if cf_pci == 0x2 and cf_seq == (expected_seq & 0x0F):
                            raw_frames.append(bytes(cf_msg.data))
                            remaining = total_length - len(reassembled)
                            reassembled.extend(cf_msg.data[1:1 + min(7, remaining)])
                            expected_seq += 1

                full_data = bytes(reassembled[:total_length])
                if prefix and not full_data.startswith(prefix):
                    continue
                return ReceivedResponse(msg=msg, payload=full_data, raw_frames=raw_frames)

            # Single Frame
            if sf_payload is None:
                continue
            if prefix and not sf_payload.startswith(prefix):
                continue
            return ReceivedResponse(msg=msg, payload=sf_payload, raw_frames=[bytes(msg.data)])

    return None
