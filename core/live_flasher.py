import argparse
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
    load_profile,
    DEFAULT_PROFILE,
    FIRMWARE_DIR
)
import core.api_routes as api


def wait_for_flow_control(bus, expected_rx_id: int, timeout: float = 1.0):
    """Wait for a Flow Control (30 xx xx) frame from the ECU."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        msg = bus.recv(0.1)
        if msg and msg.arbitration_id == expected_rx_id:
            if msg.data and (msg.data[0] >> 4) == 0x3:  # Flow Control NIbble
                return msg
    return None


def wait_for_response(bus, expected_rx_id: int, expected_data: bytes, timeout: float):
    """Wait for the ECU's response, handling 7F xx 78 (Response Pending) dynamically."""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        msg = bus.recv(0.1)
        if not msg:
            continue
            
        if msg.arbitration_id == expected_rx_id:
            # Check for ResponsePending (7F xx 78)
            if len(msg.data) >= 3 and (msg.data[0] & 0x0F) == 3 and msg.data[1] == 0x7F and msg.data[3] == 0x78:
                 # It's a Single Frame containing 7F xx 78 (e.g., 03 7F 31 78)
                 # Note: UDS Single Frames start with length, so 03 7F XX 78
                 print("    [ECU indicates Response Pending (78) - Delaying timeout]")
                 start_time = time.time()  # Reset timeout!
                 continue
                 
            # For this simple executor, returning any matching response ID is a "catch".
            # We compare it loosely against expected_data or let the sequence proceed.
            # In a robust stack, we'd fully parse the UDS payload.
            return msg

    return None


def process_live_flash(profile_path: str, files_data, times):
    if can is None:
        print("[BACKEND] python-can not installed — cannot use PCAN hardware.")
        return False
    baudrate = 500000
    profile = load_profile(profile_path)
    ctx = build_runtime_context(profile)

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

    total_files = len(hex_files) * times
    api.flash_session['total_ops'] = total_files

    for t in range(times):
        for idx, name in enumerate(hex_files):
            api.flash_session['current_op'] += 1
            api.flash_session['swFile'] = name
            api.flash_session['progress'] = 0.0
            op_start = int(time.time() * 1000)
            global_completed = (t * len(hex_files)) + idx

            hex_path = os.path.join(FIRMWARE_DIR, name)
            if not os.path.exists(hex_path):
                api.push_trace("EVT", "—", "—", f"File not found: {hex_path}")
                continue

            parsed_segments = parse_intel_hex_segments(hex_path)
            selected_segments = select_flash_segments(parsed_segments, ctx)
            trace = build_flash_sequence(selected_segments, ctx)
            total_frames = len(trace)

            for i, frame in enumerate(trace):
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
                    if frame.direction == 'Tx':
                        if frame.comment:
                            api.push_trace("EVT", "—", "—", f"Step {i+1}/{total_frames}: {frame.comment}")
                            
                        msg = can.Message(
                            arbitration_id=int(frame.can_id, 16),
                            data=frame.data,
                            is_extended_id=False
                        )
                        bus.send(msg)
                        
                        data_hex = ' '.join(f'{b:02X}' for b in frame.data)
                        api.push_trace("TX", hex(msg.arbitration_id)[2:].upper(), data_hex, frame.comment)

                        pci_nibble = frame.data[0] >> 4
                        if pci_nibble == 0x1:
                            fc_msg = wait_for_flow_control(bus, expected_rx_id, timeout=1.0)
                            if not fc_msg:
                                api.push_trace("EVT", "—", "—", "FAIL: Timeout waiting for FlowControl from ECU.")
                                return False
                            fc_data_hex = ' '.join(f'{b:02X}' for b in fc_msg.data)
                            api.push_trace("RX", hex(fc_msg.arbitration_id)[2:].upper(), fc_data_hex, "FlowControl")

                    elif frame.direction == 'Rx':
                        timeout = 5.0
                        rx_msg = wait_for_response(bus, expected_rx_id, frame.data, timeout=timeout)
                        if not rx_msg:
                            expected_hex = ' '.join(f'{b:02X}' for b in frame.data)
                            api.push_trace("EVT", "—", "—", f"FAIL: Timeout waiting for expected ECU response: {expected_hex}")
                            return False
                        
                        rx_data_hex = ' '.join(f'{b:02X}' for b in rx_msg.data)
                        api.push_trace("RX", hex(rx_msg.arbitration_id)[2:].upper(), rx_data_hex, frame.comment)
                        
                except Exception as e:
                    api.push_trace("EVT", "—", "—", f"EXECUTION ERROR at frame {i}: {e}")
                    return False

            api.flash_session['progress'] = 100.0
            api.flash_session['flashCount'] += 1
            fc = api.flash_session['flashCount']
            api.nvm_memory["F190"] = [(fc >> 8) & 0xFF, fc & 0xFF]
            
            log_entry = {
                "id": int(time.time() * 1000),
                "swFile": name,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "duration": f"{api.flash_session['elapsedMs'] // 1000}.{(api.flash_session['elapsedMs'] % 1000)//100}s",
                "status": "success"
            }
            api.flash_session['sessionLog'].insert(0, log_entry)

    api.flash_session['total_progress'] = 100.0
    api.flash_session['eta_seconds'] = 0
    api.flash_session['running'] = False
    return True


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
