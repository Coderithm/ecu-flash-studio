import argparse
import csv
import os
import sys

try:
    from core.hex_parsing import (
        parse_intel_hex_segments,
        select_flash_segments,
        build_runtime_context,
        build_flash_sequence,
        load_profile,
        DEFAULT_PROFILE,
        FIRMWARE_DIR
    )
except ImportError:
    from hex_parsing import (
        parse_intel_hex_segments,
        select_flash_segments,
        build_runtime_context,
        build_flash_sequence,
        load_profile,
        DEFAULT_PROFILE,
        FIRMWARE_DIR
    )

def process_to_csv(profile_path: str):
    profile = load_profile(profile_path)
    ctx = build_runtime_context(profile)

    hex_files = sorted(name for name in os.listdir(FIRMWARE_DIR) if name.lower().endswith(".hex"))
    if not hex_files:
        print(f"[WARN] No .hex files found in: {FIRMWARE_DIR}")
        return 1

    for name in hex_files:
        hex_path = os.path.join(FIRMWARE_DIR, name)
        
        parsed_segments = parse_intel_hex_segments(hex_path)
        selected_segments = select_flash_segments(parsed_segments, ctx)
        trace = build_flash_sequence(selected_segments, ctx)

        base_name = os.path.splitext(name)[0]
        output_csv = f"{base_name}_transfer_frames.csv"
        
        print(f"Writing CSV: {output_csv} ...")
        with open(output_csv, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            # CSV Header
            writer.writerow([
                "Timestamp",
                "Direction",
                "CAN_ID",
                "DLC",
                "Data",
                "Description"
            ])
            
            for frame in trace:
                hex_bytes = " ".join(f"{value:02X}" for value in frame.data)
                writer.writerow([
                    f"{frame.timestamp:.6f}",
                    frame.direction,
                    frame.can_id.upper(),
                    len(frame.data),
                    hex_bytes,
                    frame.comment or ""
                ])
                
        print(f"  Frames exported: {len(trace)}")
    
    return 0


def parse_args():
    parser = argparse.ArgumentParser(description="Generate CSV of UDS transfer frames from Intel HEX files.")
    parser.add_argument(
        "--profile",
        default=DEFAULT_PROFILE,
        help="Path to OEM profile JSON file. Defaults to profiles/mahindra_template.json",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    sys.exit(process_to_csv(os.path.abspath(args.profile)))
