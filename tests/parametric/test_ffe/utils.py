"""Delta varint encoding/decoding utilities for feature flag serial IDs.

Feature flag event enrichment encodes serial IDs using delta varint encoding:
1. Serial IDs are sorted
2. Deltas from previous value are computed (first delta = first value)
3. Each delta is encoded as a varint (7 bits per byte, MSB=continuation)
4. Result is base64 encoded for wire transmission

Example: [100, 108, 128, 130] -> deltas [100, 8, 20, 2] -> varint bytes -> base64
"""

# ruff: noqa: UP007, UP045 - Repository guidance requires explicit Optional annotations.

from collections.abc import Mapping, Sequence
import base64
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any, Optional, Union

# Varint encoding constants
VARINT_DATA_BITS = 0x7F  # Lower 7 bits contain data
VARINT_CONTINUATION_BIT = 0x80  # MSB indicates more bytes follow


def load_ufc_fixture_for_cases(case_filename: str) -> dict[str, Any]:
    """Load the canonical flag definitions used by a specific integration suite."""
    fixture_root = Path(__file__).parent / "ffe-system-test-data"
    config = json.loads((fixture_root / "ufc-config.json").read_text())
    cases = json.loads((fixture_root / "evaluation-cases" / case_filename).read_text())
    # Keep unrelated evaluator edge cases out of transport/span integration tests.
    flag_keys = dict.fromkeys(case["flag"] for case in cases)
    config["flags"] = {key: config["flags"][key] for key in flag_keys}
    return config


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
        result |= (byte & VARINT_DATA_BITS) << shift
        bytes_consumed += 1
        offset += 1

        if (byte & VARINT_CONTINUATION_BIT) == 0:
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
        while delta >= VARINT_CONTINUATION_BIT:
            result.append((delta & VARINT_DATA_BITS) | VARINT_CONTINUATION_BIT)
            delta >>= 7
        result.append(delta)

    return base64.b64encode(bytes(result)).decode("ascii")


def hash_targeting_key(targeting_key: str) -> str:
    """Hash a targeting key using SHA256.

    Args:
        targeting_key: The targeting key to hash

    Returns:
        64-character lowercase hex digest of the SHA256 hash

    Example:
        >>> hash_targeting_key("user-123")
        'fcdec6df4d44dbc637c7c5b58efface52a7f8a88535423430255be0bb89bedd8'

    """
    return hashlib.sha256(targeting_key.encode("utf-8")).hexdigest()


def assert_feature_map(actual: object, expected: dict[str, Any], destination: str) -> None:
    """Compare exact scalar feature maps without equating false with zero."""
    assert isinstance(actual, dict), f"{destination}: missing feature map: {actual!r}"
    assert actual.keys() == expected.keys(), f"{destination}: expected {expected!r}, got {actual!r}"
    for key, expected_value in expected.items():
        actual_value = actual[key]
        if type(expected_value) in (int, float):
            valid_type = type(actual_value) in (int, float)
        else:
            valid_type = type(actual_value) is type(expected_value)
        assert valid_type, f"{destination}.{key}: expected type {type(expected_value)}, got {type(actual_value)}"
        assert actual_value == expected_value, f"{destination}.{key}: expected {expected_value!r}, got {actual_value!r}"


class _TargetingKeyUnset:
    pass


TARGETING_KEY_UNSET = _TargetingKeyUnset()


def _targeting_key_matches(actual: object, expected: Optional[str]) -> bool:
    if expected is None:
        return actual is None
    hashed = f"sha256_{hashlib.sha256(expected.encode()).hexdigest()}"
    return actual in (expected, hashed)


def ffe_events_from_requests(
    requests: Sequence[Mapping[str, Any]],
    flag: Optional[str] = None,
    targeting_key: Optional[Union[str, _TargetingKeyUnset]] = TARGETING_KEY_UNSET,
) -> dict[str, list[dict[str, Any]]]:
    """Read matching EVP payloads recorded by the parametric test agent."""
    events: dict[str, list[dict[str, Any]]] = {"EXPOSURE": [], "EVALUATION": []}
    for request in requests:
        path = request["url"].split("?", 1)[0]
        if path.endswith("/api/v2/exposures"):
            destination, field = "EXPOSURE", "exposures"
        elif path.endswith("/api/v2/flagevaluation"):
            destination, field = "EVALUATION", "flagEvaluations"
        else:
            continue
        body = base64.b64decode(request["body"])
        # The agent may already have decompressed a request while retaining its headers.
        if body.startswith(b"\x1f\x8b"):
            body = gzip.decompress(body)
        payload = json.loads(body)
        for event in payload[field]:
            if flag is not None and event.get("flag", {}).get("key") != flag:
                continue
            if not isinstance(targeting_key, _TargetingKeyUnset):
                if destination == "EXPOSURE":
                    subject = event.get("subject")
                    actual_targeting_key = subject.get("id") if isinstance(subject, dict) else None
                    if not _targeting_key_matches(actual_targeting_key, targeting_key):
                        continue
                elif not _targeting_key_matches(event.get("targeting_key"), targeting_key):
                    continue
            events[destination].append(event)
    return events


def ffe_events_for_target(
    events: Mapping[str, Sequence[dict[str, Any]]], targeting_key: Optional[str]
) -> dict[str, list[dict[str, Any]]]:
    """Filter already decoded FFE events for one raw or hashed targeting key."""
    result: dict[str, list[dict[str, Any]]] = {"EXPOSURE": [], "EVALUATION": []}
    for destination, destination_events in events.items():
        for event in destination_events:
            if destination == "EXPOSURE":
                subject = event.get("subject")
                actual_targeting_key = subject.get("id") if isinstance(subject, dict) else None
            else:
                actual_targeting_key = event.get("targeting_key")
            if _targeting_key_matches(actual_targeting_key, targeting_key):
                result[destination].append(event)
    return result


def ffe_event_matches(event: dict[str, Any], matcher: dict[str, Any]) -> bool:
    """Match a canonical corpus expectation against an EVP event."""
    nested_key_fields = {
        "allocation": "allocation",
        "errorCode": "error",
        "flag": "flag",
        "variant": "variant",
    }

    def event_field(field: str) -> object:
        if field in nested_key_fields:
            value = event.get(nested_key_fields[field])
            if not isinstance(value, dict):
                return None
            return value.get("message" if field == "errorCode" else "key")
        if field == "runtimeDefaultUsed":
            return event.get("runtime_default_used", False)
        return event.get(field)

    fields_match = all(
        event_field(field) == expected for field, expected in matcher.items() if not field.startswith("_")
    )
    expected_error_code = matcher.get("errorCode")
    return fields_match and (expected_error_code is None or event.get("runtime_default_used") is True)


def events_match(actual: list[dict[str, Any]], expected: list[dict[str, Any]], *, exact: bool) -> bool:
    """Consume each expected matcher from a distinct emitted event."""
    unmatched = actual.copy()
    for matcher in expected:
        matching_index = next(
            (index for index, event in enumerate(unmatched) if ffe_event_matches(event, matcher)), None
        )
        if matching_index is None:
            return False
        unmatched.pop(matching_index)
    return not exact or not unmatched
