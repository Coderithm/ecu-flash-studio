
import threading
import time
import base64
import random

flash_session = {
    "running": False,
    "current_op": 0,
    "total_ops": 0,
    "progress": 0.0,
    "elapsedMs": 0,
    "total_progress": 0.0,
    "eta_seconds": -1,
    "flashCount": 0,
    "sessionLog": [],
    "swFile": "\u2014",
    "master_start": 0,
    "force_stop": False
}

interruption_tests = [
    { "id": 1, "name": "Power Loss during UDS 0x36 Data Transfer", "status": "idle" },
    { "id": 2, "name": "CAN bus disconnect during 0x31 RoutineControl", "status": "idle" },
    { "id": 3, "name": "Voltage drop < 9V during 0x34 RequestDownload", "status": "idle" },
    { "id": 4, "name": "Security Access 0x27 Seed/Key timeout", "status": "idle" }
]
last_interruption_result = None

can_trace_log = []

# Per-file traces: keyed by log entry id -> list of trace frames
flash_traces = {}
_current_file_trace = []
_current_file_trace_id = None

def push_trace(dir, canId, data, note=""):
    entry = {
        "id": time.time(),
        "ts": time.strftime("%H:%M:%S.") + f"{int((time.time() % 1) * 1000):03d}",
        "dir": dir,
        "canId": canId,
        "data": data,
        "note": note
    }
    can_trace_log.append(entry)
    # Also append to per-file trace if capture is active
    if _current_file_trace_id is not None:
        _current_file_trace.append(entry)

def clear_trace():
    global can_trace_log
    can_trace_log = []

nvm_memory = {
    "F190": [0x00, 0x00]
}

NVM_DATA_MAP = [
  { "address": "0x0000", "label": "Odometer",          "value": "0x00123456", "raw": "18 00 01 23 45 67" },
  { "address": "0x0010", "label": "VIN Lock",           "value": "0x01",       "raw": "01" },
  { "address": "0x0020", "label": "ECU Serial No.",     "value": "0xABCD1234", "raw": "AB CD 12 34" },
  { "address": "0x0030", "label": "Flash Cycle Count",  "value": "0x0000",     "raw": "00 00" },
  { "address": "0x0040", "label": "Last Error Code",    "value": "0x0000",     "raw": "00 00" },
  { "address": "0x0050", "label": "Boot SW Version",    "value": "0x0102",     "raw": "01 02" },
  { "address": "0x0060", "label": "Calib. Checksum",    "value": "0xF3A1",     "raw": "F3 A1" },
  { "address": "0x0070", "label": "Diag Session",       "value": "0x03",       "raw": "03" },
]

def simulate_flash_sequence(files_data, times):
    global flash_session, _current_file_trace_id
    flash_session['running'] = True
    flash_session['sessionLog'] = []
    flash_session['current_op'] = 0
    flash_session['total_progress'] = 0.0
    flash_session['eta_seconds'] = -1
    flash_session['master_start'] = time.time()
    
    total_files = len(files_data) * times
    flash_session['total_ops'] = total_files
    
    # Try to import the real trace builder
    trace_builder = None
    try:
        from core.hex_parsing import (
            parse_intel_hex_segments, select_flash_segments,
            build_runtime_context, build_flash_sequence,
            load_profile, DEFAULT_PROFILE, FIRMWARE_DIR
        )
        profile = load_profile(DEFAULT_PROFILE)
        ctx = build_runtime_context(profile)
        trace_builder = True
    except Exception as e:
        print(f"[BACKEND] Trace builder unavailable ({e}), using basic simulation.")
        trace_builder = False
    
    print(f"\n[BACKEND] Validated {len(files_data)} unique file(s) assigned via priority sorted payloads.")
    print(f"[BACKEND] Starting modular sequence {times}x (Total flashes: {total_files})...\n")
    
    for t in range(times):
        if flash_session.get('force_stop'): break
        for idx, file_obj in enumerate(files_data):
            if flash_session.get('force_stop'): break
            fname = file_obj['name']
            
            flash_session['current_op'] += 1
            flash_session['swFile'] = fname
            flash_session['progress'] = 0.0
            
            # Start per-file trace capture
            _current_file_trace.clear()
            _current_file_trace_id = True
            
            op_start = int(time.time() * 1000)
            global_completed = (t * len(files_data)) + idx
            
            # Try to build real trace from hex file
            trace_frames = None
            if trace_builder:
                try:
                    import os
                    hex_path = os.path.join(FIRMWARE_DIR, fname)
                    if os.path.exists(hex_path):
                        segments = parse_intel_hex_segments(hex_path)
                        selected = select_flash_segments(segments, ctx)
                        trace_frames = build_flash_sequence(selected, ctx)
                        print(f"[BACKEND] Built real trace for {fname}: {len(trace_frames)} frames")
                except Exception as e:
                    print(f"[BACKEND] Trace build failed for {fname}: {e}")
                    trace_frames = None
            
            if trace_frames:
                # Replay REAL trace frames
                total_steps = len(trace_frames)
                push_trace("EVT", "—", "—", f"Replaying {total_steps} frames from {fname}")
                
                for step, frame in enumerate(trace_frames):
                    # Pace the simulation (fast but visible)
                    if step % 50 == 0:
                        time.sleep(0.01)
                    
                    dir_label = "TX" if frame.direction == "Tx" else "RX"
                    data_hex = ' '.join(f'{b:02X}' for b in frame.data)
                    push_trace(dir_label, frame.can_id.upper(), data_hex, frame.comment)
                    
                    # Update progress
                    p = (step / total_steps) * 100.0
                    flash_session['progress'] = p
                    flash_session['elapsedMs'] = int(time.time() * 1000) - op_start
                    
                    current_fraction = (global_completed + (step / total_steps)) / total_files
                    flash_session['total_progress'] = current_fraction * 100.0
                    
                    elapsed_total = time.time() - flash_session['master_start']
                    if current_fraction > 0:
                        total_expected = elapsed_total / current_fraction
                        flash_session['eta_seconds'] = int(total_expected - elapsed_total)
            else:
                # Fallback: basic 20-step simulation
                steps = 20
                push_trace("EVT", "—", "—", f"Basic simulation for {fname} (hex file not in firmware/)")
                for step in range(steps):
                    time.sleep(0.12)
                    bsc = ((step + 1) % 256)
                    push_trace("TX", "740", f"36 {bsc:02X} AA BB CC DD EE FF", f"TransferData (0x36) - Block {step+1}")
                    if step % 2 == 0:
                         push_trace("RX", "748", f"02 76 {bsc:02X} 00 00 00 00 00", "TransferData positive response (0x76)")
                    
                    p = (step / steps) * 100.0
                    flash_session['progress'] = p
                    flash_session['elapsedMs'] = int(time.time() * 1000) - op_start
                    current_fraction = (global_completed + (step / steps)) / total_files
                    flash_session['total_progress'] = current_fraction * 100.0
                    elapsed_total = time.time() - flash_session['master_start']
                    if current_fraction > 0:
                        total_expected = elapsed_total / current_fraction
                        flash_session['eta_seconds'] = int(total_expected - elapsed_total)
            
            flash_session['progress'] = 100.0
            flash_session['flashCount'] += 1
            
            # Sync to mock NVM F190
            fc = flash_session['flashCount']
            nvm_memory["F190"] = [(fc >> 8) & 0xFF, fc & 0xFF]
            
            log_id = int(time.time() * 1000)
            elapsed_ms = flash_session['elapsedMs']
            log_entry = {
                "id": log_id,
                "swFile": fname,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "duration": f"{elapsed_ms // 1000}.{(elapsed_ms % 1000)//100}s",
                "duration_ms": elapsed_ms,
                "status": "success",
                "has_trace": True
            }
            flash_session['sessionLog'].insert(0, log_entry)
            
            # Save per-file trace snapshot
            flash_traces[log_id] = list(_current_file_trace)
            _current_file_trace.clear()
            _current_file_trace_id = None

    flash_session['total_progress'] = 100.0
    flash_session['eta_seconds'] = 0
    flash_session['running'] = False
    print("\n[BACKEND] Multi-flash sequence complete!")

def get_flash_status():
    st = dict(flash_session)
    st["cycle"] = st.get("current_op", 0)
    st["total"] = st.get("total_ops", 0)
    st["interruption_tests"] = interruption_tests
    st["last_interruption_result"] = last_interruption_result
    return st

def _run_flash_engine(files, times):
    try:
        import core.live_flasher as flasher
        # Try physical PCAN flash
        success = flasher.process_live_flash(flasher.DEFAULT_PROFILE, files, times)
        if not success:
            # Check if live flasher partially ran (some flashes already completed)
            if flash_session.get('current_op', 0) > 0 and len(flash_session.get('sessionLog', [])) > 0:
                # Live flasher failed mid-sequence — do NOT restart as simulation
                # Mark session as stopped with a failure entry
                print(f"[BACKEND] Live flasher failed after {len(flash_session['sessionLog'])} flash(es). NOT falling back to simulation.")
                push_trace("EVT", "\u2014", "\u2014", "PCAN hardware error — flashing stopped. Remaining flashes aborted.")
                log_entry = {
                    "id": int(time.time() * 1000),
                    "swFile": flash_session.get('swFile', '\u2014'),
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "duration": "0.0s",
                    "duration_ms": 0,
                    "status": "failed",
                    "has_trace": False
                }
                flash_session['sessionLog'].insert(0, log_entry)
                flash_session['total_progress'] = 100.0
                flash_session['eta_seconds'] = 0
                flash_session['running'] = False
            else:
                # Live flasher failed before any flashes started (e.g. PCAN init failed)
                # Safe to fall back to full simulation
                print(f"[BACKEND] Live flasher failed at init, falling back to simulation.")
                simulate_flash_sequence(files, times)
    except (ImportError, SystemExit, Exception) as e:
        print(f"[BACKEND] Live flasher unavailable ({e}), falling back to simulation.")
        simulate_flash_sequence(files, times)

def start_multiflash(files, times):
    if not flash_session['running'] and len(files) > 0:
        # Save uploaded base64 files to FIRMWARE_DIR so live flasher can find them
        try:
            import os
            from core.hex_parsing import FIRMWARE_DIR
            os.makedirs(FIRMWARE_DIR, exist_ok=True)
            for f in files:
                name = f.get('name')
                data_b64 = f.get('data_b64')
                if name and data_b64:
                    filepath = os.path.join(FIRMWARE_DIR, name)
                    with open(filepath, "wb") as out_file:
                        out_file.write(base64.b64decode(data_b64))
        except Exception as e:
            print(f"[BACKEND] Error saving uploaded files: {e}")

        flash_session['running'] = True
        flash_session['force_stop'] = False
        t = threading.Thread(target=_run_flash_engine, args=(files, times))
        t.daemon = True
        t.start()
        return True
    return False

def stop_multiflash():
    if flash_session['running']:
        flash_session['force_stop'] = True
    return {"status": "stopping"}

def read_nvm(did):
    did_clean = str(did).replace(" ", "").upper()
    data = nvm_memory.get(did_clean, [0x00, 0x00])
    return {
        "status": "success",
        "did": did_clean,
        "data": data
    }

def write_nvm(did, data):
    did_clean = str(did).replace(" ", "").upper()
    if not isinstance(data, list):
        data = []
    nvm_memory[did_clean] = data
    if did_clean == "F190" and len(data) >= 2:
        flash_session['flashCount'] = (data[0] << 8) | data[1]
    return {
        "status": "success"
    }

def get_nvm_map():
    fc = flash_session['flashCount']
    hex_fc = f"0x{fc:04X}"
    raw_fc = f"{(fc >> 8) & 0xFF:02X} {fc & 0xFF:02X}"
    for row in NVM_DATA_MAP:
        if row["address"] == "0x0030":
            row["value"] = hex_fc
            row["raw"] = raw_fc
            break
    return NVM_DATA_MAP

def update_nvm_map(addr, val):
    import re
    val_clean = val.replace("0x", "").replace("0X", "")
    # Add leading zero if odd length to make full bytes
    if len(val_clean) % 2 != 0:
        val_clean = "0" + val_clean
    raw_str = " ".join(re.findall('.{1,2}', val_clean)).upper()
    
    for row in NVM_DATA_MAP:
        if row["address"].lower() == addr.lower():
            row["value"] = val
            row["raw"] = raw_str
            if row["address"] == "0x0030":
                try:
                    flash_session['flashCount'] = int(val_clean, 16)
                except ValueError:
                    pass
            break
    return {"status": "success"}

def simulate_interruption(test_id):
    global flash_session, last_interruption_result
    
    test_obj = next((t for t in interruption_tests if t["id"] == test_id), None)
    if not test_obj:
        return
        
    test_name = test_obj["name"]
    test_obj["status"] = "running"
    
    flash_session['running'] = True
    flash_session['current_op'] = 1
    flash_session['total_ops'] = 1
    flash_session['progress'] = 0.0
    flash_session['total_progress'] = 0.0
    flash_session['swFile'] = f"{test_name} (Interruption)"
    flash_session['master_start'] = time.time()
    
    op_start = int(time.time() * 1000)
    
    push_trace("TX", "18DA10F1", "02 10 03 00 00 00 00 00", "DiagSessionControl (0x10) - Extended")
    push_trace("RX", "18DAF110", "06 50 03 00 32 01 F4 00", "Positive Response (0x50)")
    push_trace("EVT", "—", "—", f"Test Started: {test_name}")
    
    for step in range(20):
        time.sleep(0.06)
        
        push_trace("TX", "18DA10F1", "36 01 AA BB CC DD EE FF", f"TransferData (0x36) - Block {step+1}")
        
        p = (step / 20) * 95.0
        flash_session['progress'] = p
        flash_session['total_progress'] = p
        flash_session['elapsedMs'] = int(time.time() * 1000) - op_start
        
    interrupted = random.random() > 0.4
    result_status = "interrupted" if interrupted else "failed"
    
    if interrupted:
        push_trace("RX", "18DAF110", "03 7F 36 70 00 00 00 00", "NRC (0x7F) - UploadDownloadNotAccepted (0x70)")
        push_trace("EVT", "—", "—", "Interruption Detected & Handled safely")
    else:
        push_trace("EVT", "—", "—", "FATAL: ECU stopped responding to CAN requests")
    
    test_obj["status"] = result_status
    last_interruption_result = {
        "testId": test_id,
        "result": result_status,
        "interrupted": interrupted
    }
    
    flash_session['flashCount'] += 1
    fc = flash_session['flashCount']
    nvm_memory["F190"] = [(fc >> 8) & 0xFF, fc & 0xFF]
    
    log_entry = {
        "id": int(time.time() * 1000),
        "swFile": flash_session['swFile'],
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "duration": f"{flash_session['elapsedMs'] // 1000}.{(flash_session['elapsedMs'] % 1000)//100}s",
        "status": result_status
    }
    flash_session['sessionLog'].insert(0, log_entry)
    
    flash_session['progress'] = 100.0
    flash_session['total_progress'] = 100.0
    time.sleep(0.1)
    flash_session['running'] = False

def start_interruption_test(test_id):
    if not flash_session['running']:
        t = threading.Thread(target=simulate_interruption, args=(test_id,))
        t.daemon = True
        t.start()
        return True
    return False


def get_ecu_config():
    """Read CAN IDs from the active profile."""
    try:
        from core.hex_parsing import load_profile, DEFAULT_PROFILE
        profile = load_profile(DEFAULT_PROFILE)
        can_cfg = profile.get("can", {})
        return {
            "can_tx": can_cfg.get("request_id", "—").upper(),
            "can_rx": can_cfg.get("response_id", "—").upper(),
            "functional_id": can_cfg.get("functional_id", "—").upper(),
            "protocol": profile.get("meta", {}).get("protocol", "UDS_on_CAN"),
            "oem": profile.get("meta", {}).get("oem", "Unknown"),
            "profile_name": profile.get("meta", {}).get("name", "Unknown"),
        }
    except Exception as e:
        return {"can_tx": "—", "can_rx": "—", "error": str(e)}


def read_sw_version():
    """Attempt to read SW version from a live ECU. Returns error if no ECU connected."""
    try:
        from core.hex_parsing import load_profile, DEFAULT_PROFILE, build_runtime_context
        from core.can_live_flasher import build_live_runtime, read_did_live
        import can as can_lib
        
        profile = load_profile(DEFAULT_PROFILE)
        ctx = build_runtime_context(profile)
        runtime = build_live_runtime(profile, ctx)
        
        bus = can_lib.interface.Bus(interface='pcan', channel='PCAN_USBBUS1', bitrate=500000)
        expected_rx_id = int(ctx.response_id, 16)
        tx_can_id_int = int(ctx.request_id, 16)
        
        read_cfg = profile.get("read_after_flash", {})
        dids = read_cfg.get("dids", ["f180"])
        operation_timeout = int(read_cfg.get("operation_timeout_ms", 5000)) / 1000.0
        decode_mode = read_cfg.get("decode", "ascii")
        value_length = int(read_cfg.get("value_length", 0))
        accepted_dids = {bytes.fromhex(str(did)) for did in dids}
        
        version = None
        for did in dids:
            value = read_did_live(
                bus, runtime, tx_can_id_int, expected_rx_id,
                str(did), ctx.pad_byte, operation_timeout, "SW Version",
                decode_mode, value_length, accepted_dids
            )
            if value:
                version = value
                break
                
        bus.shutdown()
        if version:
            return {"status": "ok", "version": version}
        return {"status": "error", "error": "No valid response from ECU", "version": None}
    except ImportError:
        return {"status": "error", "error": "No ECU connected (python-can not installed)", "version": None}
    except Exception as e:
        return {"status": "error", "error": f"No ECU connected: {e}", "version": None}


def _build_trc_from_entries(entries):
    """Build PEAK .trc format (version 1.1) from a list of trace entries."""
    if not entries:
        return None

    lines = []
    lines.append(";$FILEVERSION=1.1")
    lines.append(f";$STARTTIME={time.strftime('%Y-%m-%dT%H:%M:%S')}")
    lines.append(";")
    lines.append(";   Message Number) Time ID Flags DLC Data")
    lines.append(";")

    msg_num = 1
    start_time = entries[0]["id"] if entries else time.time()

    for entry in entries:
        if entry.get("dir") == "EVT":
            lines.append(f";   {entry.get('note', '')}")
            continue

        relative_ms = (entry["id"] - start_time) * 1000.0
        can_id = entry.get("canId", "000").replace("\u2014", "000")
        direction = "Rx" if entry.get("dir") == "RX" else "Tx"

        data_str = entry.get("data", "").replace("\u2014", "")
        data_bytes = data_str.split() if data_str.strip() else []
        dlc = len(data_bytes)
        data_field = " ".join(data_bytes) if data_bytes else ""

        line = f"  {msg_num:>6})  {relative_ms:>12.1f}  {can_id:>8}  {direction}   {dlc}  {data_field}"
        if entry.get("note"):
            line += f"   ; {entry['note']}"
        lines.append(line)
        msg_num += 1

    return "\r\n".join(lines) + "\r\n"

def export_trc():
    """Export the full CAN trace log as PEAK .trc format."""
    return _build_trc_from_entries(can_trace_log)

def export_trc_for_file(log_id):
    """Export the CAN trace for a specific flash operation by its log ID."""
    entries = flash_traces.get(log_id)
    if not entries:
        return None
    return _build_trc_from_entries(entries)
