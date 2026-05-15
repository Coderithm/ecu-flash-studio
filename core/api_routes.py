
import threading
import time
import base64
import random
from collections import deque

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
    "force_stop": False,
    "failedFlashes": []
}

interruption_tests = [
    { "id": 1, "name": "Erase Phase Interruption", "status": "idle" }
]
last_interruption_result = None

can_trace_log = []
TRACE_LOG_MAX = 50000
TRACE_API_DEFAULT_LIMIT = 1500
CAN_BITRATE_BPS = 500000
BUS_LOAD_WINDOW_SECONDS = 1.0
_trace_lock = threading.RLock()
_bus_load_samples = deque()

# Per-file traces: keyed by log entry id -> list of trace frames
flash_traces = {}
_current_file_trace = []
_current_file_trace_id = None

def _trace_data_len(data):
    count = 0
    for part in str(data or "").split():
        try:
            value = int(part, 16)
        except ValueError:
            continue
        if 0 <= value <= 0xFF:
            count += 1
    return min(count, 8)

def _is_extended_can_id(can_id):
    try:
        return int(str(can_id).replace("0x", "").replace("0X", ""), 16) > 0x7FF
    except ValueError:
        return False

def _estimate_classic_can_bits(can_id, data):
    dlc = _trace_data_len(data)
    base_bits = 75 if _is_extended_can_id(can_id) else 55
    # Include a conservative stuffing/inter-frame margin so the load is useful
    # for live monitoring without needing a full CAN controller bit counter.
    return int((base_bits + (dlc * 8)) * 1.2)

def _prune_bus_load_samples(now):
    cutoff = now - BUS_LOAD_WINDOW_SECONDS
    while _bus_load_samples and _bus_load_samples[0][0] < cutoff:
        _bus_load_samples.popleft()

def _current_bus_load_locked(now=None):
    now = time.time() if now is None else now
    _prune_bus_load_samples(now)
    bits = sum(sample_bits for _, sample_bits in _bus_load_samples)
    frames = len(_bus_load_samples)
    percent = (bits / (CAN_BITRATE_BPS * BUS_LOAD_WINDOW_SECONDS)) * 100.0
    return {
        "percent": round(max(0.0, min(100.0, percent)), 2),
        "bits_per_second": int(bits / BUS_LOAD_WINDOW_SECONDS),
        "frames_per_second": round(frames / BUS_LOAD_WINDOW_SECONDS, 1),
        "window_ms": int(BUS_LOAD_WINDOW_SECONDS * 1000),
        "bitrate": CAN_BITRATE_BPS,
    }

def reset_flash_session(total_ops=0, clear_log=True, clear_trace_log=True):
    global _current_file_trace_id
    flash_count = flash_session.get("flashCount", 0)
    flash_session.update({
        "running": True,
        "current_op": 0,
        "total_ops": max(0, int(total_ops or 0)),
        "progress": 0.0,
        "elapsedMs": 0,
        "total_progress": 0.0,
        "eta_seconds": -1,
        "flashCount": flash_count,
        "swFile": "\u2014",
        "master_start": time.time(),
        "force_stop": False,
        "failedFlashes": [],
    })
    if clear_log:
        flash_session["sessionLog"] = []
    with _trace_lock:
        _current_file_trace.clear()
        _current_file_trace_id = None
        flash_traces.clear()
        _bus_load_samples.clear()
        if clear_trace_log:
            can_trace_log.clear()

def finish_flash_session(completed=True):
    total_ops = max(1, int(flash_session.get("total_ops") or 1))
    current_op = max(0, int(flash_session.get("current_op") or 0))
    if completed:
        flash_session["progress"] = 100.0
        flash_session["total_progress"] = 100.0
        flash_session["eta_seconds"] = 0
    else:
        flash_session["total_progress"] = min(100.0, (current_op / total_ops) * 100.0)
        flash_session["eta_seconds"] = 0
    flash_session["running"] = False

def start_file_trace():
    global _current_file_trace_id
    with _trace_lock:
        _current_file_trace.clear()
        _current_file_trace_id = True

def finish_file_trace(log_id):
    global _current_file_trace_id
    with _trace_lock:
        entries = list(_current_file_trace)
        if entries:
            flash_traces[log_id] = entries
        _current_file_trace.clear()
        _current_file_trace_id = None
    return bool(entries)

def abort_file_trace():
    global _current_file_trace_id
    with _trace_lock:
        _current_file_trace_id = None

def push_trace(dir, canId, data, note=""):
    now = time.time()
    entry = {
        "id": now,
        "ts": time.strftime("%H:%M:%S.", time.localtime(now)) + f"{int((now % 1) * 1000):03d}",
        "dir": dir,
        "canId": canId,
        "data": data,
        "note": note
    }
    with _trace_lock:
        can_trace_log.append(entry)
        if len(can_trace_log) > TRACE_LOG_MAX:
            del can_trace_log[:len(can_trace_log) - TRACE_LOG_MAX]
        if str(dir).upper() in {"TX", "RX"}:
            _bus_load_samples.append((now, _estimate_classic_can_bits(canId, data)))
            _prune_bus_load_samples(now)
        # Also append to per-file trace if capture is active
        if _current_file_trace_id is not None:
            _current_file_trace.append(entry)

def clear_trace():
    with _trace_lock:
        can_trace_log.clear()
        _bus_load_samples.clear()

def get_can_trace(limit=TRACE_API_DEFAULT_LIMIT):
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = TRACE_API_DEFAULT_LIMIT

    if limit <= 0:
        limit = TRACE_API_DEFAULT_LIMIT
    limit = min(limit, TRACE_LOG_MAX)

    with _trace_lock:
        total = len(can_trace_log)
        trace = list(can_trace_log[-limit:])
        bus_load = _current_bus_load_locked()

    return {
        "trace": trace,
        "total": total,
        "returned": len(trace),
        "truncated": total > len(trace),
        "limit": limit,
        "bus_load": bus_load,
    }

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
    global flash_session
    total_files = len(files_data) * times
    reset_flash_session(total_files)
    
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
            seq_number = (t * len(files_data)) + idx + 1
            
            flash_session['current_op'] = seq_number
            flash_session['swFile'] = fname
            flash_session['progress'] = 0.0
            
            # Start per-file trace capture
            start_file_trace()
            
            op_start = int(time.time() * 1000)
            global_completed = (t * len(files_data)) + idx
            
            try:
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
                    total_steps = len(trace_frames)
                    push_trace("EVT", "\u2014", "\u2014", f"Replaying {total_steps} frames from {fname}")
                    
                    for step, frame in enumerate(trace_frames):
                        if step % 50 == 0:
                            time.sleep(0.01)
                        
                        dir_label = "TX" if frame.direction == "Tx" else "RX"
                        data_hex = ' '.join(f'{b:02X}' for b in frame.data)
                        push_trace(dir_label, frame.can_id.upper(), data_hex, frame.comment)
                        
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
                    steps = 20
                    push_trace("EVT", "\u2014", "\u2014", f"Basic simulation for {fname} (hex file not in firmware/)")
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
                    "seq": seq_number,
                    "has_trace": True
                }
                flash_session['sessionLog'].insert(0, log_entry)
                log_entry["has_trace"] = finish_file_trace(log_id)

            except Exception as flash_err:
                # Flash failed \u2014 record and continue to next flash
                print(f"[BACKEND] Flash #{seq_number} ({fname}) FAILED: {flash_err}")
                push_trace("EVT", "\u2014", "\u2014", f"Flash #{seq_number} ({fname}) FAILED: {flash_err}")
                
                elapsed_ms = int(time.time() * 1000) - op_start
                log_id = int(time.time() * 1000)
                log_entry = {
                    "id": log_id,
                    "swFile": fname,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "duration": f"{elapsed_ms // 1000}.{(elapsed_ms % 1000)//100}s",
                    "duration_ms": elapsed_ms,
                    "status": "failed",
                    "seq": seq_number,
                    "has_trace": finish_file_trace(log_id)
                }
                flash_session['sessionLog'].insert(0, log_entry)
                flash_session['failedFlashes'].append({
                    "seq": seq_number,
                    "file": fname,
                    "error": str(flash_err),
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                })
                continue

    finish_flash_session(completed=not flash_session.get('force_stop'))
    print("\n[BACKEND] Multi-flash sequence complete!")

def get_flash_status():
    st = dict(flash_session)
    st["cycle"] = st.get("current_op", 0)
    st["total"] = st.get("total_ops", 0)
    st["failedFlashes"] = list(flash_session.get("failedFlashes", []))
    st["interruption_tests"] = interruption_tests
    st["last_interruption_result"] = last_interruption_result
    return st

def _run_flash_engine(files, times):
    try:
        import core.live_flasher as flasher
        # Try physical PCAN flash
        success = flasher.process_live_flash(flasher.DEFAULT_PROFILE, files, times)
        if not success:
            # If any operation had started, never hide a hardware failure behind simulation.
            if flash_session.get('current_op', 0) > 0:
                # Live flasher failed mid-sequence — do NOT restart as simulation
                # Mark session as stopped with a failure entry
                print(f"[BACKEND] Live flasher failed after {len(flash_session['sessionLog'])} flash(es). NOT falling back to simulation.")
                push_trace("EVT", "\u2014", "\u2014", "PCAN hardware error — flashing stopped. Remaining flashes aborted.")
                elapsed_ms = int(flash_session.get('elapsedMs') or 0)
                log_id = int(time.time() * 1000)
                log_entry = {
                    "id": log_id,
                    "swFile": flash_session.get('swFile', '\u2014'),
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "duration": f"{elapsed_ms // 1000}.{(elapsed_ms % 1000)//100}s",
                    "duration_ms": elapsed_ms,
                    "status": "failed",
                    "has_trace": finish_file_trace(log_id)
                }
                flash_session['sessionLog'].insert(0, log_entry)
                finish_flash_session(completed=False)
            else:
                # Live flasher failed before any flashes started (e.g. PCAN init failed)
                # Safe to fall back to full simulation
                print(f"[BACKEND] Live flasher failed at init, falling back to simulation.")
                simulate_flash_sequence(files, times)
    except (ImportError, SystemExit, Exception) as e:
        if flash_session.get('current_op', 0) > 0:
            print(f"[BACKEND] Live flasher failed after starting hardware flash ({e}). NOT falling back to simulation.")
            push_trace("EVT", "\u2014", "\u2014", f"PCAN hardware error: {e}. Remaining flashes aborted.")
            elapsed_ms = int(flash_session.get('elapsedMs') or 0)
            log_id = int(time.time() * 1000)
            log_entry = {
                "id": log_id,
                "swFile": flash_session.get('swFile', '\u2014'),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "duration": f"{elapsed_ms // 1000}.{(elapsed_ms % 1000)//100}s",
                "duration_ms": elapsed_ms,
                "status": "failed",
                "has_trace": finish_file_trace(log_id)
            }
            flash_session['sessionLog'].insert(0, log_entry)
            finish_flash_session(completed=False)
        else:
            print(f"[BACKEND] Live flasher unavailable ({e}), falling back to simulation.")
            simulate_flash_sequence(files, times)

def start_multiflash(files, times):
    try:
        times = int(times)
    except (TypeError, ValueError):
        times = 1
    times = max(1, min(times, 100000))
    files = [f for f in files if f.get('name')]

    if not flash_session['running'] and len(files) > 0:
        # Save uploaded base64 files to FIRMWARE_DIR so live flasher can find them
        try:
            import os
            from core.hex_parsing import FIRMWARE_DIR
            os.makedirs(FIRMWARE_DIR, exist_ok=True)
            for f in files:
                name = os.path.basename(f.get('name') or '')
                f['name'] = name
                data_b64 = f.get('data_b64')
                if name and data_b64:
                    filepath = os.path.join(FIRMWARE_DIR, name)
                    with open(filepath, "wb") as out_file:
                        out_file.write(base64.b64decode(data_b64))
        except Exception as e:
            print(f"[BACKEND] Error saving uploaded files: {e}")
            return False

        reset_flash_session(len(files) * times)
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

def _run_interruption_engine(test_id, file_obj):
    if file_obj and file_obj.get("data_b64"):
        try:
            import os
            import base64
            from core.hex_parsing import FIRMWARE_DIR
            os.makedirs(FIRMWARE_DIR, exist_ok=True)
            fname = file_obj.get("name", "Interruption_Test")
            filepath = os.path.join(FIRMWARE_DIR, fname)
            with open(filepath, "wb") as out_file:
                out_file.write(base64.b64decode(file_obj["data_b64"]))
        except Exception as e:
            print(f"[BACKEND] Error saving interruption file: {e}")
            return

    try:
        from core.hex_parsing import DEFAULT_PROFILE
        import core.live_flasher as flasher
        success = flasher.process_live_interruption(DEFAULT_PROFILE, test_id, file_obj)
        if not success:
            print("[BACKEND] Live flasher failed to execute.")
    except (ImportError, Exception) as e:
        print(f"[BACKEND] Live flasher unavailable ({e}).")

def start_interruption_test(test_id, file_obj=None):
    if not flash_session['running']:
        t = threading.Thread(target=_run_interruption_engine, args=(test_id, file_obj))
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
    with _trace_lock:
        entries = list(can_trace_log)
    return _build_trc_from_entries(entries)

def export_trc_for_file(log_id):
    """Export the CAN trace for a specific flash operation by its log ID."""
    with _trace_lock:
        entries = list(flash_traces.get(log_id) or [])
    if not entries:
        return None
    return _build_trc_from_entries(entries)
