"""
Mahindra Seed-Key Algorithm Plugin.

Implements Level 1 (4-byte seed) and Level 3 (8-byte seed) from the Mahindra
seed/key specification. Input and output bytes are kept in ECU order, MSB first
for Level 3.
"""


LEVEL1_MASKS = [
    bytes.fromhex("F549506A"),
    bytes.fromhex("47152AB0"),
    bytes.fromhex("2E31DA76"),
    bytes.fromhex("53266FE2"),
    bytes.fromhex("874318C0"),
    bytes.fromhex("2FE296BF"),
    bytes.fromhex("CB84F0FE"),
    bytes.fromhex("E806EC53"),
    bytes.fromhex("018F28ED"),
    bytes.fromhex("487E89DE"),
    bytes.fromhex("CDC1B660"),
    bytes.fromhex("FC0829D3"),
    bytes.fromhex("847FCE7C"),
    bytes.fromhex("17E8DD4D"),
    bytes.fromhex("C666FF1C"),
    bytes.fromhex("BDC5DBE9"),
]


LEVEL3_MASKS = [
    bytes.fromhex(value)
    for value in [
        "CDCC44AD", "4709A45C", "FDD05B8C", "A034C50B",
        "4E3F6FD3", "DB31B79B", "E66108D4", "942FDDF0",
        "C0A1E39C", "E856356A", "1F05631B", "908B0944",
        "49357431", "E17D0E7D", "B31B46AF", "2BCF9D65",
        "6F6F215B", "C4E48957", "20E79E63", "ABABF122",
        "B925F0A4", "F0785F02", "4F7AF3F5", "30EC3B29",
        "63E50064", "EB8DDA5E", "D4517D00", "CE063AB9",
        "4CA8EC66", "EE87EF14", "39BBDF5A", "98F41020",
        "E844B324", "66AF03F3", "403FD5CB", "12D73F2D",
        "142DEC9D", "7FF8454B", "18737DF4", "79D8080D",
        "F0D4ED45", "8B19F5B4", "2744C246", "EE6FEBB4",
        "657FA6BB", "35479CE8", "7BBFFBFF", "450BAE91",
        "F13340CA", "A9540109", "F30FD0C5", "6C7BF9B5",
        "CFFFF991", "E9D05EC6", "37F1E734", "2A885C7B",
        "FCAFA810", "E6163386", "9F58376C", "F47724F9",
        "A85946D3", "A6E00B26", "BC0E54CF", "BA6B914F",
        "3445323F", "11822D39", "F5D66C08", "732B39F7",
        "3A33A847", "BFF29266", "97A67FC7", "6076130C",
        "ACAEE3E7", "AD978FDD", "A5F391CA", "C4D793A6",
        "13F8DE67", "E0A14D72", "A432D2C3", "370D8EAB",
        "F1F77D3A", "BB23EBD8", "41AACDCF", "2D668A8C",
        "8A5FD9AC", "123F8795", "A581AA1C", "3F94A12F",
        "71F55259", "4A91A903", "B4AC4257", "1D84ECE1",
        "DC5BCC49", "EC01332F", "7E04E374", "A36EE85C",
        "9A77271B", "1ACA79BB", "B1C5D41A", "3820A25E",
        "DC410F27", "754929A2", "CCB7CDA6", "1051AE06",
        "3266E2BC", "E23E6F3C", "3EEFC769", "8FFCB1B1",
        "3B9D8408", "E7D840BA", "AF965884", "3CB2CFFE",
        "EDD68087", "9B839ABC", "8DC8CE43", "3E316769",
        "4D01AA1B", "FD3E1212", "40A88E30", "57FC2051",
        "97774857", "3BD679DA", "7C3DF001", "4C2B1A62",
        "C0F27F62", "F8B8684D", "56659339", "F9A8DB20",
        "EF32F810", "FF02C6CA", "5526D521", "A71CFE65",
        "CDB66BD3", "D3C8D704", "18ABCAA3", "2516E0BC",
        "B7DFDB23", "F71ECCD4", "D3418485", "34868ECF",
        "EDDEC9AC", "D2B1A352", "573A37EB", "3079BBBA",
        "A3CD3103", "7C1052A1", "5673B92E", "DF70399E",
        "E189392E", "744FFEED", "4954AF94", "A39C7FE3",
        "379AE82A", "9DB0B4A4", "510EB251", "4321FA4F",
        "A439AC3B", "1EDBD29F", "A257A930", "A3A6FECA",
        "5375637D", "1B65AB6D", "62C09DDC", "B14E2101",
        "1278C4C7", "E2D02410", "87350CB8", "BA13721C",
        "FE066302", "24AC1ECD", "826A0050", "CADB40D7",
        "CD20ACF0", "1D448341", "F7BE82C9", "6EB6F577",
        "89ED3E60", "D614E39B", "F656834E", "7BCBB2F0",
        "94EE6403", "7FC614D3", "11904C94", "EF601D04",
        "D217CE8D", "504C286B", "38F022F8", "B0C44C67",
        "B39C9E57", "17E8403C", "DCE7768B", "1F0F69C0",
        "A5F4CB47", "FC5F7A46", "8FB747DA", "AF063DA2",
        "7C9814EA", "24290A8B", "58A88EBB", "B5E54DDB",
        "E6F9A1C9", "703DAA55", "95EF92DF", "595ED44A",
        "16552CC8", "2B747059", "662610D1", "328BE27F",
        "7DD29C36", "A5FF8C98", "38AA86B8", "A7765949",
        "56B5C495", "54A05334", "1B480216", "48339FC6",
        "A6274199", "445171E9", "2736FCC9", "44A468D2",
        "76ED4B20", "65B48559", "1308521A", "C4D27CE7",
        "B8EF54C6", "47CD8908", "A17B2F67", "E4088DA1",
        "C480B792", "AFF5B3EE", "2A6DFD68", "19BB5062",
        "42CB6F28", "7E86811A", "19819940", "3D560926",
        "1B77BD54", "27F673D0", "C00D84D3", "27128926",
        "FAFF6311", "B8B2CD2E", "792226DE", "4BB270D9",
        "EBC71624", "F6E1ED2F", "9432A2BC", "B1DD04AD",
        "B2FDA210", "AE08F7D1", "547BDEDE", "93E5065B",
        "9E06C0C9", "5EDC92AC", "8D771DBD", "A799B197",
    ]
]


def _rotate_left(data: bytes, count: int) -> bytes:
    width = len(data) * 8
    count %= width
    if count == 0:
        return bytes(data)
    value = int.from_bytes(data, byteorder="big")
    mask = (1 << width) - 1
    value = ((value << count) | (value >> (width - count))) & mask
    return value.to_bytes(len(data), byteorder="big")


def _rotate_right(data: bytes, count: int) -> bytes:
    width = len(data) * 8
    count %= width
    if count == 0:
        return bytes(data)
    value = int.from_bytes(data, byteorder="big")
    mask = (1 << width) - 1
    value = ((value >> count) | (value << (width - count))) & mask
    return value.to_bytes(len(data), byteorder="big")


def _rotate(data: bytes, count: int, rotate_right: bool) -> bytes:
    if rotate_right:
        return _rotate_right(data, count)
    return _rotate_left(data, count)


def _xor(left: bytes, right: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(left, right))


def _or(left: bytes, right: bytes) -> bytes:
    return bytes(a | b for a, b in zip(left, right))


def _nand(left: bytes, right: bytes) -> bytes:
    return bytes((~(a & b)) & 0xFF for a, b in zip(left, right))


def _xor_or_nand(left: bytes, right: bytes) -> bytes:
    result = _xor(left, right)
    if all(byte == 0x00 for byte in result):
        return _nand(left, right)
    return result


def _add_to_64bit(data: bytes, value: int) -> bytes:
    result = (int.from_bytes(data, byteorder="big") + value) & 0xFFFFFFFFFFFFFFFF
    return result.to_bytes(8, byteorder="big")


def _level1_compute(seed: bytes) -> bytes:
    if len(seed) != 4:
        raise ValueError("Level 1 seed must be exactly 4 bytes")
    if seed == b"\x00\x00\x00\x00":
        return b"\x00\x00\x00\x00"

    # Level 1 specifies byte 0 as the least-significant byte.
    mask = LEVEL1_MASKS[seed[0] & 0x0F]
    xored = _xor(seed, mask)
    rotate_count = xored[1] & 0x0F
    rotate_right = (xored[3] & 0x80) != 0
    return _rotate(xored, rotate_count, rotate_right)


def _split_level3_seed(seed: bytes) -> tuple[bytes, bytes]:
    largest = max(seed)
    seed_l = bytearray()
    seed_r = bytearray()

    for index, value in enumerate(seed):
        if len(seed_l) == 4:
            seed_r.append(value)
        elif len(seed_r) == 4:
            seed_l.append(value)
        elif (largest >> index) & 0x01:
            seed_l.append(value)
        else:
            seed_r.append(value)

    if len(seed_l) != 4 or len(seed_r) != 4:
        raise ValueError("Level 3 seed split did not produce two 4-byte seeds")
    return bytes(seed_l), bytes(seed_r)


def _level3_compute(seed: bytes) -> bytes:
    if len(seed) != 8:
        raise ValueError("Level 3 seed must be exactly 8 bytes")
    if seed == b"\x00" * 8:
        return b"\x00" * 8

    seed_l, seed_r = _split_level3_seed(seed)

    seed_l_shifted = _rotate(
        seed_l,
        seed_l[3] & 0x0F,
        rotate_right=(seed_l[2] & 0x80) != 0,
    )
    seed_r_shifted = _rotate(
        seed_r,
        seed_r[0] & 0x0F,
        rotate_right=(seed_r[1] & 0x80) != 0,
    )

    seed_final = bytes(seed)
    for index in range(8):
        control = seed_final[index]
        seed_final = _rotate(
            seed_final,
            control & 0x0F,
            rotate_right=(control & 0x80) != 0,
        )

    seed_xored = _xor_or_nand(seed_l_shifted, seed_r_shifted)
    mask_x = LEVEL3_MASKS[seed_xored[0]]
    mask_x_shifted = _rotate(
        mask_x,
        mask_x[0] & 0x0F,
        rotate_right=(mask_x[3] & 0x80) != 0,
    )

    shift_reg = seed_xored + mask_x_shifted
    key_input = _xor_or_nand(seed_final, shift_reg)
    count = _or(seed_final, shift_reg)
    countsum = sum(count) // len(count)

    key = key_input
    for j in range(countsum):
        rotate_count = key[0] & 0x0F
        key = _rotate(key, rotate_count, rotate_right=(j % 2) == 1)
        key = _add_to_64bit(key, j)

    return key


def compute_key(seed: bytes) -> bytes:
    """Compute the Mahindra security key for a 4-byte or 8-byte ECU seed."""
    seed = bytes(seed)
    if len(seed) == 4:
        return _level1_compute(seed)
    if len(seed) == 8:
        return _level3_compute(seed)
    raise ValueError(f"Unsupported seed length: {len(seed)} bytes")
