"""
Mahindra Seed-Key Algorithm Plugin (Level 1 & Level 3)
Based on MAHLE BSW Workshop Seed-Key Algorithm Specification (pg. 25).

Level 1: 4-byte seed -> XOR with mask table -> rotate -> 4-byte key
Level 3: 8-byte seed -> split L/R -> L1 on each half -> merge -> iterative rotate -> 8-byte key

IMPORTANT: The MASK_TABLE below contains placeholder values.
           Replace with the actual OEM mask table from the
           "Mahindra Security Key Requirements" document.
"""


# --- Mask Lookup Table (16 entries, indexed by lower nibble of Seed[3]) ---
# Replace these placeholder values with the actual OEM mask values.
MASK_TABLE = [
    bytes([0xA5, 0x3C, 0x96, 0x5A]),  # Index 0x0
    bytes([0x5A, 0xC3, 0x69, 0xA5]),  # Index 0x1
    bytes([0x96, 0x5A, 0xA5, 0x3C]),  # Index 0x2
    bytes([0x3C, 0x69, 0x5A, 0xC3]),  # Index 0x3
    bytes([0xC3, 0xA5, 0x3C, 0x69]),  # Index 0x4
    bytes([0x69, 0x96, 0xC3, 0x5A]),  # Index 0x5
    bytes([0xA5, 0x69, 0x96, 0xC3]),  # Index 0x6
    bytes([0xC3, 0x3C, 0x69, 0x96]),  # Index 0x7
    bytes([0x5A, 0xA5, 0xC3, 0x3C]),  # Index 0x8
    bytes([0x96, 0xC3, 0x5A, 0xA5]),  # Index 0x9
    bytes([0x3C, 0x96, 0xA5, 0x69]),  # Index 0xA
    bytes([0x69, 0x5A, 0x3C, 0x96]),  # Index 0xB
    bytes([0xA5, 0xC3, 0x69, 0x5A]),  # Index 0xC
    bytes([0x3C, 0xA5, 0x96, 0x69]),  # Index 0xD
    bytes([0x69, 0x3C, 0xC3, 0xA5]),  # Index 0xE
    bytes([0x96, 0x69, 0x5A, 0x3C]),  # Index 0xF
]


# ---------------------------------------------------------------------------
# Bit rotation helpers (32-bit for L1, 64-bit for L3 merge)
# ---------------------------------------------------------------------------

def _rotate_left_32(data: bytes, count: int) -> bytes:
    """Rotate a 4-byte value left by 'count' bits."""
    val = int.from_bytes(data, byteorder="big")
    count = count % 32
    val = ((val << count) | (val >> (32 - count))) & 0xFFFFFFFF
    return val.to_bytes(4, byteorder="big")


def _rotate_right_32(data: bytes, count: int) -> bytes:
    """Rotate a 4-byte value right by 'count' bits."""
    val = int.from_bytes(data, byteorder="big")
    count = count % 32
    val = ((val >> count) | (val << (32 - count))) & 0xFFFFFFFF
    return val.to_bytes(4, byteorder="big")


# ---------------------------------------------------------------------------
# Level 1 algorithm (4-byte seed -> 4-byte key)
# ---------------------------------------------------------------------------

def _level1_compute(seed: bytes) -> bytes:
    """
    Level 1 Seed-Key computation.

    Flowchart steps:
      1. If seed == 00 00 00 00 -> already unlocked
      2. Extract lower nibble of Seed[3] -> table index
      3. Lookup Data Mask from MASK_TABLE[index]
      4. XOR Seed with Data Mask -> Result[4]
      5. Extract lower nibble of Result[1] -> Rotate Count
      6. Check MSB of Result[0] -> Rotation Direction (1=left, 0=right)
      7. Rotate Result by Rotate Count bits
      8. Final Key = Rotated Result
    """
    # Step 1: zero seed = already unlocked
    if seed == b"\x00\x00\x00\x00":
        return b"\x00\x00\x00\x00"

    # Step 2: lower nibble of Seed[3] -> table index
    table_index = seed[3] & 0x0F

    # Step 3: lookup mask
    mask = MASK_TABLE[table_index]

    # Step 4: XOR seed with mask
    result = bytes(s ^ m for s, m in zip(seed, mask))

    # Step 5: lower nibble of Result[1] -> rotate count
    rotate_count = result[1] & 0x0F

    # Step 6: MSB of Result[0] -> direction (1 = left, 0 = right)
    rotate_left = (result[0] & 0x80) != 0

    # Step 7: rotate
    if rotate_left:
        key = _rotate_left_32(result, rotate_count)
    else:
        key = _rotate_right_32(result, rotate_count)

    return key


# ---------------------------------------------------------------------------
# Level 3 algorithm (8-byte seed -> 8-byte key)
# ---------------------------------------------------------------------------

def _level3_compute(seed: bytes) -> bytes:
    """
    Level 3 Seed-Key computation.

    Flowchart steps:
      1. Split 8-byte seed into SeedL[4] and SeedR[4]
      2. Assign bytes based on largest byte bits (swap so larger goes to L)
      3. Ensure both halves are 4 bytes
      4. Apply L1-like key handling to SeedL and SeedR independently
      5. Merge SeedL and SeedR results into 8 bytes
      6. Iterative rotation and countsum-based processing
      7. Final Key = 8 bytes
    """
    # Step 1: split into left and right halves
    seed_l = bytearray(seed[:4])
    seed_r = bytearray(seed[4:])

    # Step 2: assign bytes based on largest byte bits
    # For each position, the larger byte goes to SeedL
    for i in range(4):
        if seed_r[i] > seed_l[i]:
            seed_l[i], seed_r[i] = seed_r[i], seed_l[i]

    # Step 3: both halves are guaranteed 4 bytes (already ensured by split)

    # Step 4: apply L1-like key handling to each half
    key_l = _level1_compute(bytes(seed_l))
    key_r = _level1_compute(bytes(seed_r))

    # Step 5: merge results
    merged = bytearray(key_l) + bytearray(key_r)

    # Step 6: iterative rotation and countsum-based processing
    countsum = sum(merged) & 0xFF
    rotate_count = countsum & 0x0F

    val = int.from_bytes(merged, byteorder="big")
    for i in range(rotate_count):
        # Rotate left by 1 bit per iteration
        val = ((val << 1) | (val >> 63)) & 0xFFFFFFFFFFFFFFFF
        # XOR with shifted countsum for diffusion
        val ^= (countsum << (i % 8)) & 0xFFFFFFFFFFFFFFFF

    return val.to_bytes(8, byteorder="big")


# ---------------------------------------------------------------------------
# Public entry point (called by hex_parsing.py engine)
# ---------------------------------------------------------------------------

def compute_key(seed: bytes) -> bytes:
    """
    Compute the security key for a given seed.

    Automatically selects Level 1 (4-byte) or Level 3 (8-byte)
    based on the seed length.

    Args:
        seed: Raw seed bytes from the ECU (4 or 8 bytes).

    Returns:
        Computed key bytes (same length as seed).
    """
    if len(seed) == 4:
        return _level1_compute(seed)
    elif len(seed) == 8:
        return _level3_compute(seed)
    else:
        raise ValueError(
            f"Unsupported seed length: {len(seed)} bytes (expected 4 or 8)"
        )
