"""Shared utilities and UFC fixtures for Feature Flagging tests.

Feature flag event enrichment encodes serial IDs using delta varint encoding:
1. Serial IDs are sorted
2. Deltas from previous value are computed (first delta = first value)
3. Each delta is encoded as a varint (7 bits per byte, MSB=continuation)
4. Result is base64 encoded for wire transmission

Example: [100, 108, 128, 130] -> deltas [100, 8, 20, 2] -> varint bytes -> base64
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from tests.parametric.conftest import APMLibrary

# Varint encoding constants
VARINT_DATA_BITS = 0x7F  # Lower 7 bits contain data
VARINT_CONTINUATION_BIT = 0x80  # MSB indicates more bytes follow


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


FFE_READY_RETRY_ATTEMPTS = 10
FFE_READY_RETRY_INTERVAL_SECONDS = 0.2

FIXTURE_DIRECTORY = Path(__file__).parent
UFC_FIXTURE_PATH = FIXTURE_DIRECTORY / "flags-v1.json"
MALFORMED_UFC_BYTES = b'{"flags": ['


def load_ufc_fixture() -> dict[str, Any]:
    """Load the canonical UFC configuration shared by every delivery source."""
    if not UFC_FIXTURE_PATH.exists():
        pytest.skip(f"Fixture file not found: {UFC_FIXTURE_PATH}")

    with UFC_FIXTURE_PATH.open() as fixture:
        return json.load(fixture)


def get_test_case_files() -> list[str]:
    """Return the canonical UFC evaluation fixture files."""
    excluded = {UFC_FIXTURE_PATH.name, "span-enrichment-flags.json"}
    return sorted(
        fixture.name
        for fixture in FIXTURE_DIRECTORY.iterdir()
        if fixture.suffix == ".json" and fixture.name not in excluded
    )


UFC_FIXTURE_DATA = load_ufc_fixture()
UFC_FIXTURE_BYTES = UFC_FIXTURE_PATH.read_bytes()
ALL_TEST_CASE_FILES = get_test_case_files()


def is_ffe_waiting_for_configuration(result: dict[str, Any]) -> bool:
    """Return whether an evaluation is still waiting for its initial UFC payload."""
    provider_state = result.get("providerState")
    return result.get("errorCode") == "PROVIDER_NOT_READY" or (
        isinstance(provider_state, dict) and provider_state.get("hasConfig") is False
    )


def evaluate_with_configuration_retry(
    test_library: APMLibrary,
    *,
    flag: str,
    variation_type: str,
    default_value: bool | str | float | dict[str, Any],
    targeting_key: str,
    attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate after allowing an asynchronous configuration source to become ready."""
    result = test_library.ffe_evaluate(
        flag=flag,
        variation_type=variation_type,
        default_value=default_value,
        targeting_key=targeting_key,
        attributes=attributes,
    )
    for _ in range(FFE_READY_RETRY_ATTEMPTS - 1):
        if not is_ffe_waiting_for_configuration(result):
            return result
        time.sleep(FFE_READY_RETRY_INTERVAL_SECONDS)
        result = test_library.ffe_evaluate(
            flag=flag,
            variation_type=variation_type,
            default_value=default_value,
            targeting_key=targeting_key,
            attributes=attributes,
        )

    return result


def assert_evaluation_cases(test_library: APMLibrary, test_case_file: str) -> None:
    """Run one canonical evaluation fixture against an initialized provider."""
    test_case_path = FIXTURE_DIRECTORY / test_case_file
    if not test_case_path.exists():
        pytest.skip(f"Test case file not found: {test_case_path}")

    with test_case_path.open() as fixture:
        test_cases: list[dict[str, Any]] = json.load(fixture)

    for index, test_case in enumerate(test_cases):
        result = evaluate_with_configuration_retry(
            test_library,
            flag=test_case["flag"],
            variation_type=test_case["variationType"],
            default_value=test_case["defaultValue"],
            targeting_key=test_case["targetingKey"],
            attributes=test_case.get("attributes", {}),
        )
        assert not is_ffe_waiting_for_configuration(result), (
            f"Test case {index} in {test_case_file} failed: FFE provider did not load UFC data after "
            f"{FFE_READY_RETRY_ATTEMPTS} attempts; result={result}"
        )

        expected_value = test_case["result"]["value"]
        actual_value = result.get("value")
        assert actual_value == expected_value, (
            f"Test case {index} in {test_case_file} failed: "
            f"flag='{test_case['flag']}', targetingKey='{test_case['targetingKey']}', "
            f"expected={expected_value}, actual={actual_value}"
        )
