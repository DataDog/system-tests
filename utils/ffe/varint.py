"""Delta varint encoding/decoding utilities for feature flag serial IDs.

Feature flag event enrichment encodes serial IDs using delta varint encoding:
1. Serial IDs are sorted
2. Deltas from previous value are computed (first delta = first value)
3. Each delta is encoded as a varint (7 bits per byte, MSB=continuation)
4. Result is base64 encoded for wire transmission

Example: [100, 108, 128, 130] -> deltas [100, 8, 20, 2] -> varint bytes -> base64
"""

import base64


def decode_varint(data: bytes, offset: int = 0) -> tuple[int, int]:
    """Decode a single varint from bytes.

    Args:
        data: Byte array containing varint data
        offset: Starting position in the byte array

    Returns:
        Tuple of (decoded value, number of bytes consumed)
    """
    result = 0
    shift = 0
    bytes_consumed = 0

    while offset < len(data):
        byte = data[offset]
        result |= (byte & 0x7F) << shift
        bytes_consumed += 1
        offset += 1

        if (byte & 0x80) == 0:
            break
        shift += 7

    return result, bytes_consumed


def decode_delta_varint(encoded_base64: str) -> list[int]:
    """Decode a delta-varint encoded base64 string to list of serial IDs.

    Args:
        encoded_base64: Base64 encoded delta-varint data

    Returns:
        List of decoded serial IDs (sorted)

    Example:
        >>> decode_delta_varint("ZAgUAg==")
        [100, 108, 128, 130]
    """
    if not encoded_base64:
        return []

    data = base64.b64decode(encoded_base64)
    serial_ids = []
    offset = 0
    current_value = 0

    while offset < len(data):
        delta, consumed = decode_varint(data, offset)
        current_value += delta
        serial_ids.append(current_value)
        offset += consumed

    return serial_ids


def encode_delta_varint(serial_ids: list[int]) -> str:
    """Encode a list of serial IDs to delta-varint base64 string.

    Args:
        serial_ids: List of serial IDs to encode

    Returns:
        Base64 encoded delta-varint string

    Example:
        >>> encode_delta_varint([100, 108, 128, 130])
        'ZAgUAg=='
    """
    if not serial_ids:
        return ""

    sorted_ids = sorted(serial_ids)
    result = bytearray()
    prev_value = 0

    for serial_id in sorted_ids:
        delta = serial_id - prev_value
        prev_value = serial_id

        # Encode delta as varint
        while delta >= 0x80:
            result.append((delta & 0x7F) | 0x80)
            delta >>= 7
        result.append(delta)

    return base64.b64encode(bytes(result)).decode("ascii")
