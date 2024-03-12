CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


def polymod(values):
    """Internal polynomial modulus operation for checksum calculation."""
    # bech32/bech32m polynomial constants
    generator = [0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3]
    checksum = 1
    for value in values:
        top = checksum >> 25
        checksum = ((checksum & 0x1FFFFFF) << 5) ^ value
        for i in range(5):
            if top & (1 << i):
                checksum ^= generator[i]
    return checksum


def bech32_hrp_expand(hrp):
    """Expands the human-readable part for checksum calculation."""
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def bech32m_encode(hrp, data):
    """Encode data to bech32m format."""
    data5 = convert_bits(data, 8, 5)
    if data5 is None:
        raise ValueError("Data conversion failed.")
    return bech32_encode(hrp, data5)


def bech32_encode(hrp, data):
    """Assuming data is already in 5-bit groups for bech32m checksum calculation."""
    combined = bech32_hrp_expand(hrp) + data
    checksum = polymod(combined + [0, 0, 0, 0, 0, 0]) ^ 0x2bc830a3  # bech32m checksum constant
    return hrp + '1' + ''.join([CHARSET[d] for d in data + [checksum >> 25 & 31, checksum >> 20 & 31, checksum >> 15 & 31, checksum >> 10 & 31, checksum >> 5 & 31, checksum & 31]])


def convert_bits(data, from_bits, to_bits, pad=True):
    """Converts data between different bit lengths."""
    acc = 0
    bits = 0
    ret = []
    maxv = (1 << to_bits) - 1
    for value in data:
        if value < 0 or (value >> from_bits):
            return None
        acc = (acc << from_bits) | value
        bits += from_bits
        while bits >= to_bits:
            bits -= to_bits
            ret.append((acc >> bits) & maxv)
    if pad:
        if bits:
            ret.append((acc << (to_bits - bits)) & maxv)
    elif not pad and (bits >= from_bits or ((acc << (to_bits - bits)) & maxv)):
        return None
    return ret


def bech32_decode(bechstr):
    """Decode a bech32m string."""
    if ((any(ord(x) < 33 or ord(x) > 126 for x in bechstr)) or
            (bechstr.lower() != bechstr and bechstr.upper() != bechstr)):
        return None, None
    bechstr = bechstr.lower()
    pos = bechstr.rfind('1')
    if pos < 1 or pos + 7 > len(bechstr) or len(bechstr) > 90:
        return None, None
    if not all(x in CHARSET for x in bechstr[pos+1:]):
        return None, None
    hrp = bechstr[:pos]
    data = [CHARSET.find(x) for x in bechstr[pos+1:]]
    if polymod(bech32_hrp_expand(hrp) + data) ^ 0x2bc830a3 != 0:
        return None, None
    # Convert from 5-bit groups to 8-bit groups, ensuring no padding in the final byte array.
    decoded_data = convert_bits(data[:-6], 5, 8, False)
    if decoded_data is None:
        return None, None
    return hrp, decoded_data
