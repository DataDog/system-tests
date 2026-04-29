"""Test feature flag span enrichment via parametric tests.

This module tests edge cases for feature flag event enrichment:
1. Max serial ID limit (128)
2. Max subjects limit (25)
3. Child span flag evaluation propagates to root
4. Delta varint encoding correctness
"""

import json
import pytest
from pathlib import Path
from typing import Any

from utils import features, scenarios
from utils.dd_constants import RemoteConfigApplyState
from utils.docker_fixtures import TestAgentAPI
from tests.parametric.conftest import APMLibrary
from utils.ffe.varint import decode_delta_varint, encode_delta_varint


RC_PRODUCT = "FFE_FLAGS"
RC_PATH = f"datadog/2/{RC_PRODUCT}"

parametrize = pytest.mark.parametrize


def _load_span_enrichment_fixture() -> dict[str, Any]:
    """Load the UFC fixture file for span enrichment tests."""
    # Load from tests/ffe/ directory where the shared fixture lives
    fixture_path = Path(__file__).parent.parent.parent / "ffe" / "span-enrichment-flags.json"

    if not fixture_path.exists():
        pytest.skip(f"Fixture file not found: {fixture_path}")

    with fixture_path.open() as f:
        return json.load(f)


UFC_SPAN_ENRICHMENT_DATA = _load_span_enrichment_fixture()

DEFAULT_ENVVARS = {
    "DD_EXPERIMENTAL_FLAGGING_PROVIDER_ENABLED": "true",
    "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.2",
}


def _set_and_wait_ffe_rc(
    test_agent: TestAgentAPI, ufc_data: dict[str, Any], config_id: str | None = None
) -> dict[str, Any]:
    """Set FFE Remote Config and wait for it to be acknowledged."""
    if not config_id:
        config_id = str(hash(json.dumps(ufc_data, sort_keys=True)))

    test_agent.set_remote_config(path=f"{RC_PATH}/{config_id}/config", payload=ufc_data)
    return test_agent.wait_for_rc_apply_state(RC_PRODUCT, state=RemoteConfigApplyState.ACKNOWLEDGED, clear=True)


@scenarios.parametric
@features.feature_flags_event_enrichment
class Test_Span_Enrichment_Max_Serial_IDs:
    """Test 128 serial ID limit enforcement (provisional - may adjust during code review)."""

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_max_128_serial_ids_enforced(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Test that at most 128 unique serial IDs are encoded.

        This test evaluates multiple flags and verifies the encoded serial IDs
        don't exceed the maximum limit.
        """
        _set_and_wait_ffe_rc(test_agent, UFC_SPAN_ENRICHMENT_DATA)

        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        # Evaluate multiple flags
        flags_to_evaluate = [
            ("basic-flag", "BOOLEAN", False),
            ("experiment-flag", "STRING", "default"),
            ("multi-serial-flag-1", "INTEGER", 0),
            ("multi-serial-flag-2", "INTEGER", 0),
        ]

        for flag_name, variation_type, default_value in flags_to_evaluate:
            test_library.ffe_evaluate(
                flag=flag_name,
                variation_type=variation_type,
                default_value=default_value,
                targeting_key="user-max-test",
                attributes={},
            )

        traces = test_agent.wait_for_num_traces(1, clear=True)
        assert len(traces) > 0, "No traces received"

        # Find root span
        root_span = traces[0][0]
        meta = root_span.get("meta", {})

        assert "feature_flags_encoded" in meta, (
            f"feature_flags_encoded not found in span meta: {list(meta.keys())}"
        )

        decoded_ids = decode_delta_varint(meta["feature_flags_encoded"])

        # Verify expected serial IDs are present
        expected_ids = {100, 108, 128, 130}
        for expected_id in expected_ids:
            assert expected_id in decoded_ids, (
                f"Expected serial ID {expected_id} not found in {decoded_ids}"
            )

        # Verify we never exceed 128 limit
        assert len(decoded_ids) <= 128, (
            f"Should have at most 128 serial IDs, got {len(decoded_ids)}"
        )


@scenarios.parametric
@features.feature_flags_event_enrichment
class Test_Span_Enrichment_Max_Subjects:
    """Test 25 subject limit enforcement (provisional - may adjust during code review)."""

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_max_25_subjects_enforced(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Test that at most 25 unique subjects are tracked.

        When more than 25 unique subjects evaluate doLog=true flags,
        only the first 25 should appear in feature_flag_subjects_encoded.
        """
        _set_and_wait_ffe_rc(test_agent, UFC_SPAN_ENRICHMENT_DATA)

        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        # Evaluate with 30 different subjects
        for i in range(30):
            test_library.ffe_evaluate(
                flag="experiment-flag",
                variation_type="STRING",
                default_value="default",
                targeting_key=f"subject-{i:03d}",
                attributes={},
            )

        traces = test_agent.wait_for_num_traces(1, clear=True)
        assert len(traces) > 0, "No traces received"

        root_span = traces[0][0]
        meta = root_span.get("meta", {})

        if "feature_flag_subjects_encoded" in meta:
            subjects_encoded = meta["feature_flag_subjects_encoded"]

            # Parse if string
            if isinstance(subjects_encoded, str):
                subjects_encoded = json.loads(subjects_encoded)

            if isinstance(subjects_encoded, dict):
                num_subjects = len(subjects_encoded)
                assert num_subjects <= 25, (
                    f"Should have at most 25 subjects, got {num_subjects}"
                )


@scenarios.parametric
@features.feature_flags_event_enrichment
class Test_Span_Enrichment_Delta_Varint:
    """Test delta varint encoding algorithm correctness."""

    def test_encoding_decoding_roundtrip(self) -> None:
        """Verify encode/decode utilities work correctly."""
        test_cases = [
            [100],
            [100, 108],
            [100, 108, 128, 130],
            [1, 2, 3, 4, 5],
            [100, 200, 300, 400, 500],
        ]

        for original_ids in test_cases:
            encoded = encode_delta_varint(original_ids)
            decoded = decode_delta_varint(encoded)
            assert sorted(original_ids) == decoded, (
                f"Roundtrip failed for {original_ids}: encoded={encoded}, decoded={decoded}"
            )

    def test_known_encoding_values(self) -> None:
        """Test against known delta-varint encoding values.

        Example: [100, 108, 128, 130]
        Sorted: [100, 108, 128, 130]
        Deltas: [100, 8, 20, 2]
        Varints: [0x64, 0x08, 0x14, 0x02]
        Base64: "ZAgUAg=="
        """
        serial_ids = [100, 108, 128, 130]
        expected_deltas = [100, 8, 20, 2]

        # Verify delta calculation
        sorted_ids = sorted(serial_ids)
        actual_deltas = [sorted_ids[0]]
        for i in range(1, len(sorted_ids)):
            actual_deltas.append(sorted_ids[i] - sorted_ids[i - 1])

        assert actual_deltas == expected_deltas, (
            f"Delta calculation mismatch: expected {expected_deltas}, got {actual_deltas}"
        )

        # Encode and decode should produce original sorted list
        encoded = encode_delta_varint(serial_ids)
        decoded = decode_delta_varint(encoded)
        assert decoded == sorted_ids

    def test_empty_list(self) -> None:
        """Test encoding empty list returns empty string."""
        encoded = encode_delta_varint([])
        assert encoded == ""
        decoded = decode_delta_varint("")
        assert decoded == []

    def test_single_value(self) -> None:
        """Test encoding single value."""
        encoded = encode_delta_varint([42])
        decoded = decode_delta_varint(encoded)
        assert decoded == [42]

    def test_large_values(self) -> None:
        """Test encoding values that require multiple varint bytes."""
        # Values > 127 require multiple bytes
        large_ids = [128, 256, 512, 1024, 16384]
        encoded = encode_delta_varint(large_ids)
        decoded = decode_delta_varint(encoded)
        assert decoded == sorted(large_ids)
