"""
Verify that firmware data in a generated .asc trace matches the source .hex file.

Parses both files independently and compares extracted data byte-by-byte.
Usage: python verify_trace.py firmware/large_firmware.hex large_firmware_mahindra_template_uds.asc
"""

import re
import sys


# -- Intel HEX parser ---------------------------------------------------------

def parse_hex_file(path: str) -> bytes:
    """Parse an Intel HEX file and return contiguous firmware bytes."""
    segments: dict[int, int] = {}  # address -> byte
    base_address = 0

    with open(path, "r") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line.startswith(":"):
                continue
            raw = bytes.fromhex(line[1:])
            byte_count = raw[0]
            offset = (raw[1] << 8) | raw[2]
            rec_type = raw[3]
            data = raw[4 : 4 + byte_count]

            if rec_type == 0x00:  # Data record
                full_addr = base_address + offset
                for i, b in enumerate(data):
                    segments[full_addr + i] = b
            elif rec_type == 0x02:  # Extended Segment Address
                base_address = ((data[0] << 8) | data[1]) << 4
            elif rec_type == 0x04:  # Extended Linear Address
                base_address = ((data[0] << 8) | data[1]) << 16
            elif rec_type == 0x01:  # EOF
                break

    if not segments:
        print(f"ERROR: No data records found in {path}")
        sys.exit(1)

    min_addr = min(segments)
    max_addr = max(segments)
    result = bytearray(max_addr - min_addr + 1)
    for addr, val in segments.items():
        result[addr - min_addr] = val

    print(f"  HEX file       : {path}")
    print(f"  Address range   : 0x{min_addr:08X} - 0x{max_addr:08X}")
    print(f"  Firmware bytes  : {len(result):,}")
    return bytes(result)


# -- ASC trace parser ---------------------------------------------------------

def parse_asc_transfer_data(path: str, silent: bool = False) -> bytes:
    """
    Extract firmware data from TransferData ($36) frames in an .asc trace.

    Reassembles ISO-TP multi-frame messages, strips SID ($36) and block
    sequence counter, and concatenates the raw firmware payload.
    """
    firmware_bytes = bytearray()
    current_block_payload = bytearray()
    in_transfer_block = False
    block_count = 0
    ff_total_len = 0
    ff_payload_collected = 0

    with open(path, "r") as f:
        for line in f:
            # Skip headers/comments
            if not line.strip() or line.startswith("date") or line.startswith("base"):
                continue
            if line.startswith("no ") or line.startswith("version") or line.startswith("//"):
                continue
            if "End TriggerBlock" in line:
                continue

            parts = line.split()
            if len(parts) < 6:
                continue

            # Parse: timestamp channel can_id dir d dlc b0 b1 b2 b3 b4 b5 b6 b7
            try:
                direction = parts[3]
                dlc = int(parts[5])
                data_bytes = [int(b, 16) for b in parts[6 : 6 + dlc]]
            except (ValueError, IndexError):
                continue

            if direction != "Tx" or len(data_bytes) < 1:
                continue

            first_nibble = (data_bytes[0] >> 4) & 0x0F

            # ── First Frame (1X XX) ──
            if first_nibble == 0x1 and len(data_bytes) >= 2:
                ff_total_len = ((data_bytes[0] & 0x0F) << 8) | data_bytes[1]
                payload_in_ff = data_bytes[2:]  # SID + BSC + data

                if len(payload_in_ff) >= 1 and payload_in_ff[0] == 0x36:
                    # This is a TransferData FF
                    in_transfer_block = True
                    current_block_payload = bytearray(payload_in_ff)
                    ff_payload_collected = len(payload_in_ff)
                else:
                    in_transfer_block = False
                continue

            # ── Consecutive Frame (2X) ──
            if first_nibble == 0x2 and in_transfer_block:
                cf_data = data_bytes[1:]  # skip SN byte
                remaining = ff_total_len - ff_payload_collected
                actual = min(len(cf_data), remaining)
                current_block_payload.extend(cf_data[:actual])
                ff_payload_collected += actual

                if ff_payload_collected >= ff_total_len:
                    # Block complete - strip SID (36) and BSC (1 byte)
                    if len(current_block_payload) >= 2:
                        block_data = current_block_payload[2:]  # skip 36 + BSC
                        firmware_bytes.extend(block_data)
                        block_count += 1
                    in_transfer_block = False
                continue

            # ── Single Frame (0X) ──
            if first_nibble == 0x0 and len(data_bytes) >= 2:
                sf_len = data_bytes[0] & 0x0F
                sf_payload = data_bytes[1 : 1 + sf_len]
                if sf_payload and sf_payload[0] == 0x36:
                    # Single-frame TransferData (very small block)
                    if len(sf_payload) >= 2:
                        firmware_bytes.extend(sf_payload[2:])
                        block_count += 1
                    in_transfer_block = False
                continue

            # Any other Tx frame resets transfer tracking
            if first_nibble not in (0x1, 0x2, 0x3):
                in_transfer_block = False

    if not silent:
        print(f"  ASC file        : {path}")
        print(f"  Blocks found    : {block_count}")
        print(f"  Extracted bytes : {len(firmware_bytes):,}")
    return bytes(firmware_bytes)


# -- Comparison ---------------------------------------------------------------

def compare(hex_data: bytes, asc_data: bytes):
    """Compare firmware bytes from HEX and ASC, report mismatches."""
    print()
    print("=" * 60)
    print("  COMPARISON RESULTS")
    print("=" * 60)

    if len(hex_data) != len(asc_data):
        print(f"  WARNING: Length mismatch!")
        print(f"      HEX : {len(hex_data):,} bytes")
        print(f"      ASC : {len(asc_data):,} bytes")
        min_len = min(len(hex_data), len(asc_data))
        if min_len == 0:
            print("  FAIL: Cannot compare - one source has no data.")
            return
    else:
        min_len = len(hex_data)
        print(f"  OK: Length match: {min_len:,} bytes")

    mismatches = []
    for i in range(min_len):
        if hex_data[i] != asc_data[i]:
            mismatches.append(i)
            if len(mismatches) >= 20:
                break

    if not mismatches:
        print(f"  PASS: All {min_len:,} bytes match perfectly!")
        print()
        print("  First 16 bytes (HEX) :", " ".join(f"{b:02x}" for b in hex_data[:16]))
        print("  First 16 bytes (ASC) :", " ".join(f"{b:02x}" for b in asc_data[:16]))
        print("  Last  16 bytes (HEX) :", " ".join(f"{b:02x}" for b in hex_data[-16:]))
        print("  Last  16 bytes (ASC) :", " ".join(f"{b:02x}" for b in asc_data[-16:]))
    else:
        print(f"  FAIL: Found {len(mismatches)}+ mismatches!")
        print()
        print(f"  {'Offset':<12} {'HEX':<8} {'ASC':<8}")
        print(f"  {'------':<12} {'---':<8} {'---':<8}")
        for offset in mismatches:
            print(f"  0x{offset:08X}   0x{hex_data[offset]:02X}     0x{asc_data[offset]:02X}")

    print("=" * 60)


# -- Main ---------------------------------------------------------------------

def main():
    if len(sys.argv) != 3:
        print("Usage: python verify_trace.py <firmware.hex> <trace.asc>")
        print("Example: python verify_trace.py firmware/large_firmware.hex large_firmware_mahindra_template_uds.asc")
        sys.exit(1)

    hex_path = sys.argv[1]
    asc_path = sys.argv[2]

    print()
    print("-" * 60)
    print("  Trace Data Verification Tool")
    print("-" * 60)

    hex_data = parse_hex_file(hex_path)
    print()
    asc_data = parse_asc_transfer_data(asc_path)

    compare(hex_data, asc_data)


if __name__ == "__main__":
    main()
