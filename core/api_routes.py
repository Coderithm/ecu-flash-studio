
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
    "swFile": "—",
    "master_start": 0
}

interruption_tests = [
    { "id": 1, "name": "Power Loss during UDS 0x36 Data Transfer", "status": "idle" },
    { "id": 2, "name": "CAN bus disconnect during 0x31 RoutineControl", "status": "idle" },
    { "id": 3, "name": "Voltage drop < 9V during 0x34 RequestDownload", "status": "idle" },
    { "id": 4, "name": "Security Access 0x27 Seed/Key timeout", "status": "idle" }
]
last_interruption_result = None

can_trace_log = []

def push_trace(dir, canId, data, note=""):
    can_trace_log.append({
        "id": time.time(),
        "ts": time.strftime("%H:%M:%S.") + f"{int((time.time() % 1) * 1000):03d}",
        "dir": dir,
        "canId": canId,
        "data": data,
        "note": note
    })
    if len(can_trace_log) > 5000:
        can_trace_log.pop(0)

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
    global flash_session
    flash_session['running'] = True
    flash_session['sessionLog'] = []
    flash_session['current_op'] = 0
    flash_session['total_progress'] = 0.0
    flash_session['eta_seconds'] = -1
    flash_session['master_start'] = time.time()
    
    total_files = len(files_data) * times
    flash_session['total_ops'] = total_files
    
    print(f"\n[BACKEND] Validated {len(files_data)} unique file(s) assigned via priority sorted payloads.")
    print(f"[BACKEND] Starting modular sequence {times}x (Total flashes: {total_files})...\n")
    
    for t in range(times):
        for idx, file_obj in enumerate(files_data):
            fname = file_obj['name']
            
            flash_session['current_op'] += 1
            flash_session['swFile'] = fname
            flash_session['progress'] = 0.0
            
            op_start = int(time.time() * 1000)
            global_completed = (t * len(files_data)) + idx
            
            steps = 20
            
            push_trace("TX", "7DF", "02 10 83 00 00 00 00 00", "DiagSessionControl (0x10) - Extended (functional, suppressPosRsp)")
            push_trace("TX", "7DF", "02 85 82 00 00 00 00 00", "ControlDTCSetting (0x85) - OFF (functional, suppressPosRsp)")
            push_trace("TX", "7DF", "03 28 83 03 00 00 00 00", "CommunicationControl (0x28) - OFF (functional, suppressPosRsp)")
            push_trace("TX", "740", "02 27 05 00 00 00 00 00", "SecurityAccess (0x27) - Request Seed L3")
            push_trace("RX", "748", "0A 67 05 12 34 56 78 9A BC DE F0", "SecurityAccess seed response (0x67)")
            push_trace("TX", "740", "10 0A 27 06 AA BB CC DD", "SecurityAccess (0x27) - Send Key FF")
            push_trace("RX", "748", "30 00 00 00 00 00 00 00", "FlowControl")
            push_trace("RX", "748", "02 67 06 00 00 00 00 00", "SecurityAccess unlock response (0x67)")
            push_trace("TX", "740", "02 10 02 00 00 00 00 00", "DiagSessionControl (0x10) - Programming")
            push_trace("RX", "748", "06 50 02 00 32 01 F4 00", "DiagSessionControl positive response (0x50)")
            push_trace("TX", "740", "06 31 01 02 00 01 00 00", "RoutineControl (0x31) - Set Boot Flag")
            push_trace("RX", "748", "04 71 01 02 00 00 00 00", "RoutineControl response (0x71)")
            push_trace("TX", "740", "05 31 01 FF 00 02 00 00", "RoutineControl (0x31) - Erase Memory")
            push_trace("RX", "748", "04 71 01 FF 00 00 00 00", "RoutineControl erase response (0x71)")
            push_trace("TX", "740", "10 0B 34 00 44 00 00 00", "RequestDownload (0x34) FF")
            push_trace("RX", "748", "30 00 00 00 00 00 00 00", "FlowControl")
            push_trace("RX", "748", "04 74 20 10 03 00 00 00", "RequestDownload response (0x74)")
            push_trace("EVT", "—", "—", "UDS Flash Sequence Started")
            
            for step in range(steps):
                time.sleep(0.12)  # Simulate chunk write delays
                
                bsc = ((step + 1) % 256)
                push_trace("TX", "740", f"36 {bsc:02X} AA BB CC DD EE FF", f"TransferData (0x36) - Block {step+1}")
                if step % 2 == 0:
                     push_trace("RX", "748", f"02 76 {bsc:02X} 00 00 00 00 00", "TransferData positive response (0x76)")
                
                p = (step / steps) * 100.0
                flash_session['progress'] = p
                flash_session['elapsedMs'] = int(time.time() * 1000) - op_start
                
                # Master Progress logic
                current_fraction = (global_completed + (step / steps)) / total_files
                flash_session['total_progress'] = current_fraction * 100.0
                
                # ETA calc
                elapsed_total = time.time() - flash_session['master_start']
                if current_fraction > 0:
                    total_expected = elapsed_total / current_fraction
                    flash_session['eta_seconds'] = int(total_expected - elapsed_total)
            
            flash_session['progress'] = 100.0
            flash_session['flashCount'] += 1
            
            # Sync to mock NVM F190
            fc = flash_session['flashCount']
            nvm_memory["F190"] = [(fc >> 8) & 0xFF, fc & 0xFF]
            
            log_entry = {
                "id": int(time.time() * 1000),
                "swFile": fname,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "duration": f"{flash_session['elapsedMs'] // 1000}.{(flash_session['elapsedMs'] % 1000)//100}s",
                "status": "success"
            }
            flash_session['sessionLog'].insert(0, log_entry)

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
            # Fallback to pure software simulation
            simulate_flash_sequence(files, times)
    except (ImportError, SystemExit, Exception) as e:
        print(f"[BACKEND] Live flasher unavailable ({e}), falling back to simulation.")
        simulate_flash_sequence(files, times)

def start_multiflash(files, times):
    if not flash_session['running'] and len(files) > 0:
        flash_session['running'] = True
        t = threading.Thread(target=_run_flash_engine, args=(files, times))
        t.daemon = True
        t.start()
        return True
    return False

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
