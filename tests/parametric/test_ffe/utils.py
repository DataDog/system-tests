"""Delta varint encoding/decoding utilities for feature flag serial IDs.

Feature flag event enrichment encodes serial IDs using delta varint encoding:
1. Serial IDs are sorted
2. Deltas from previous value are computed (first delta = first value)
3. Each delta is encoded as a varint (7 bits per byte, MSB=continuation)
4. Result is base64 encoded for wire transmission

Example: [100, 108, 128, 130] -> deltas [100, 8, 20, 2] -> varint bytes -> base64
"""

from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
import base64
import gzip
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from utils.dd_constants import Capabilities, RemoteConfigApplyState
from utils.docker_fixtures import ParametricTestClientApi, TestAgentAPI

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


def ffe_events_from_requests(requests: Sequence[Mapping[str, Any]], flag: str) -> dict[str, list[dict[str, Any]]]:
    """Read real EVP payloads recorded by the parametric test agent."""
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
        events[destination].extend(event for event in payload[field] if event.get("flag", {}).get("key") == flag)
    return events


def assert_dependent_flag_capability(requests: list[dict[str, Any]], *, supported: bool) -> None:
    assert requests, "No FFE_FLAGS RC requests observed; absence of traffic is not evidence of compatibility"
    capability = Capabilities.FFE_FLAG_DEPENDENT_FLAG_VARIANT_KEY_V1
    for request in requests:
        client = request["body"]["client"]
        raw = client.get("capabilities", "")
        decoded = bytes(raw) if isinstance(raw, list) else base64.b64decode(raw)
        mask = int.from_bytes(decoded, byteorder="big")
        assert bool(mask & (1 << capability)) is supported, (
            f"FFE RC client {client.get('id')} must advertise bit {capability}={supported}; got {mask:#x}"
        )


RC_PRODUCT = "FFE_FLAGS"


def ffe_requests(test_agent: TestAgentAPI) -> list[dict[str, Any]]:
    return [
        request for request in test_agent.rc_requests() if RC_PRODUCT in request["body"]["client"].get("products", [])
    ]


def observe_polls(test_agent: TestAgentAPI, *, supported: bool, minimum: int = 3) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        requests = ffe_requests(test_agent)
        if requests:
            assert_dependent_flag_capability(requests, supported=supported)
        if len(requests) >= minimum:
            return
        time.sleep(0.1)
    raise AssertionError(f"Expected at least {minimum} FFE_FLAGS RC polls, got {len(requests)}")


def deliver(test_agent: TestAgentAPI, *, config_id: str, payload: dict[str, Any], version: int) -> None:
    path = f"datadog/2/{RC_PRODUCT}/{config_id}/config"
    previous_requests = test_agent.rc_requests()
    previous_target = next(
        (
            target
            for request in reversed(previous_requests)
            for target in (request["body"].get("cached_target_files") or [])
            if target["path"] == path
        ),
        None,
    )
    test_agent.set_remote_config(path=path, payload=payload, version=version)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        # A stale ACK for the same ID must not acknowledge new content. Keep all
        # requests for capability checks, but require a new target and its versioned ACK together.
        for request in test_agent.rc_requests()[len(previous_requests) :]:
            body = request["body"]
            changed = any(
                target["path"] == path and target != previous_target
                for target in (body.get("cached_target_files") or [])
            )
            acknowledged = any(
                state["product"] == RC_PRODUCT
                and state["id"] == config_id
                and state.get("version") == version
                and state["apply_state"] == RemoteConfigApplyState.ACKNOWLEDGED.value
                for state in (body["client"]["state"].get("config_states") or [])
            )
            if changed and acknowledged:
                return
        time.sleep(0.05)
    raise AssertionError(f"The SDK did not acknowledge new configuration content for {config_id}")


def start_and_deliver(
    test_agent: TestAgentAPI,
    test_library: ParametricTestClientApi,
    *,
    config_id: str,
    payload: dict[str, Any],
    version: int,
    supported: bool,
) -> None:
    # .NET waits for configuration inside /ffe/start; Java can return not-ready
    # before delivery. Trigger startup without requiring readiness until after RC.
    with ThreadPoolExecutor(max_workers=1) as executor:
        started = executor.submit(test_library.ffe_start)
        try:
            observe_polls(test_agent, supported=supported)
            deliver(test_agent, config_id=config_id, payload=payload, version=version)
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if started.result(timeout=max(0, deadline - time.monotonic())):
                    return
                time.sleep(0.1)
                started = executor.submit(test_library.ffe_start)
            raise AssertionError("Failed to initialize the provider after RC delivery")
        except BaseException as error:
            # Stop the server before the executor joins its worker: /ffe/start
            # may still be waiting for configuration that will never arrive.
            try:
                test_library.terminate()
            except Exception as cleanup_error:
                error.add_note(f"Failed to terminate the test application: {cleanup_error}")
            raise
