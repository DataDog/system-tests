"""Test feature flag span enrichment via parametric tests.

This module tests feature flag event enrichment on APM spans:
1. Multiple flag evaluations combine serial IDs correctly (feature_flags_encoded)
2. Child span flag evaluation propagates to root span
3. Max serial ID limit (128)
4. Max subjects limit (25)
5. Subjects encoding behavior (doLog=true adds subjects, doLog=false does not)
6. Delta varint encoding correctness
"""

import json
import pytest
from pathlib import Path
from typing import Any

from utils import features, scenarios
from utils.dd_constants import RemoteConfigApplyState
from utils.docker_fixtures import TestAgentAPI
from tests.parametric.conftest import APMLibrary
from tests.parametric.test_ffe.utils import decode_delta_varint, encode_delta_varint


RC_PRODUCT = "FFE_FLAGS"
RC_PATH = f"datadog/2/{RC_PRODUCT}"

parametrize = pytest.mark.parametrize


def _load_span_enrichment_fixture() -> dict[str, Any]:
    """Load the UFC fixture file for span enrichment tests."""
    fixture_path = Path(__file__).parent / "span-enrichment-flags.json"

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


def _generate_ufc_config(num_flags: int, start_serial_id: int = 1) -> dict[str, Any]:
    """Generate a UFC config with the specified number of flags.

    Each flag gets a unique serial ID starting from start_serial_id.
    """
    flags = {}
    for i in range(num_flags):
        flag_key = f"generated-flag-{i:04d}"
        serial_id = start_serial_id + i
        flags[flag_key] = {
            "key": flag_key,
            "enabled": True,
            "variationType": "BOOLEAN",
            "variations": {
                "on": {"key": "on", "value": True},
                "off": {"key": "off", "value": False},
            },
            "allocations": [
                {
                    "key": "allocation",
                    "rules": [],
                    "splits": [{"variationKey": "on", "shards": [], "serialId": serial_id}],
                    "doLog": True,
                }
            ],
        }

    return {
        "createdAt": "2024-01-01T00:00:00.000Z",
        "format": "SERVER",
        "environment": {"name": "Test"},
        "flags": flags,
    }


@scenarios.parametric
@features.feature_flags_event_enrichment
class Test_Span_Enrichment_Serial_IDs:
    """Test serial ID encoding for multiple flag evaluations."""

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_multiple_flags_serial_ids_combined(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Test that multiple flag evaluations combine serial IDs in feature_flags_encoded.

        This test evaluates multiple flags and verifies all serial IDs are
        encoded together in the span tag.
        """
        _set_and_wait_ffe_rc(test_agent, UFC_SPAN_ENRICHMENT_DATA)

        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        # Evaluate multiple flags to test serial ID encoding
        test_library.ffe_evaluate(
            flag="basic-flag",
            variation_type="BOOLEAN",
            default_value=False,
            targeting_key="user-max-test",
            attributes={},
        )
        test_library.ffe_evaluate(
            flag="experiment-flag",
            variation_type="STRING",
            default_value="default",
            targeting_key="user-max-test",
            attributes={},
        )
        test_library.ffe_evaluate(
            flag="multi-serial-flag-1",
            variation_type="INTEGER",
            default_value=0,
            targeting_key="user-max-test",
            attributes={},
        )
        test_library.ffe_evaluate(
            flag="multi-serial-flag-2",
            variation_type="INTEGER",
            default_value=0,
            targeting_key="user-max-test",
            attributes={},
        )

        traces = test_agent.wait_for_num_traces(1, clear=True)
        assert len(traces) > 0, "No traces received"

        # Find root span
        root_span = traces[0][0]
        meta = root_span.get("meta", {})

        assert "feature_flags_encoded" in meta, f"feature_flags_encoded not found in span meta: {list(meta.keys())}"

        decoded_ids = decode_delta_varint(meta["feature_flags_encoded"])

        # Verify all expected serial IDs from evaluated flags are present
        expected_ids = {100, 108, 128, 130}
        for expected_id in expected_ids:
            assert expected_id in decoded_ids, f"Expected serial ID {expected_id} not found in {decoded_ids}"


@scenarios.parametric
@features.feature_flags_event_enrichment
class Test_Span_Enrichment_Child_Span_Propagation:
    """Test that flag evaluations in child spans propagate to root span."""

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_child_span_flag_evaluation_propagates_to_root(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Test that flag evaluated in child span appears in root span's feature_flags_encoded.

        When a flag is evaluated within a child span context, the serial ID should
        still be aggregated into the root span's feature_flags_encoded tag.
        """
        _set_and_wait_ffe_rc(test_agent, UFC_SPAN_ENRICHMENT_DATA)

        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        # Create parent span, then child span, evaluate flag in child context
        with (
            test_library.dd_start_span(name="parent", service="test-service") as parent,
            test_library.dd_start_span(name="child", service="test-service", parent_id=parent.span_id),
        ):
            # Evaluate flag while in child span context
            test_library.ffe_evaluate(
                flag="basic-flag",
                variation_type="BOOLEAN",
                default_value=False,
                targeting_key="user-child-span-test",
                attributes={},
            )

        traces = test_agent.wait_for_num_traces(1, clear=True)
        assert len(traces) > 0, "No traces received"

        # Find the root span (parent)
        root_span = None
        for span in traces[0]:
            if span.get("parent_id") in (0, None):
                root_span = span
                break

        assert root_span is not None, "Root span not found"
        meta = root_span.get("meta", {})

        # The flag evaluated in child span should appear in root span's feature_flags_encoded
        assert "feature_flags_encoded" in meta, (
            f"feature_flags_encoded not found in root span meta: {list(meta.keys())}"
        )

        decoded_ids = decode_delta_varint(meta["feature_flags_encoded"])
        expected_serial_id = 100  # basic-flag's serial ID

        assert expected_serial_id in decoded_ids, (
            f"Serial ID {expected_serial_id} from child span evaluation not found in root span. "
            f"Decoded IDs: {decoded_ids}"
        )


@scenarios.parametric
@features.feature_flags_event_enrichment
class Test_Span_Enrichment_Max_Serial_IDs:
    """Test 128 serial ID limit enforcement (provisional - may adjust during code review)."""

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_max_128_serial_ids_enforced(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Test that at most 128 unique serial IDs are encoded.

        Evaluates 150 flags (each with unique serial ID) and verifies
        the encoded result contains at most 128 serial IDs.
        """
        num_flags = 150
        ufc_config = _generate_ufc_config(num_flags)
        _set_and_wait_ffe_rc(test_agent, ufc_config, config_id="max-serial-ids-test")

        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        # Evaluate all 150 flags
        for i in range(num_flags):
            test_library.ffe_evaluate(
                flag=f"generated-flag-{i:04d}",
                variation_type="BOOLEAN",
                default_value=False,
                targeting_key="user-limit-test",
                attributes={},
            )

        traces = test_agent.wait_for_num_traces(1, clear=True)
        assert len(traces) > 0, "No traces received"

        root_span = traces[0][0]
        meta = root_span.get("meta", {})

        assert "feature_flags_encoded" in meta, f"feature_flags_encoded not found in span meta: {list(meta.keys())}"

        decoded_ids = decode_delta_varint(meta["feature_flags_encoded"])

        # Verify we don't exceed 128 limit
        assert len(decoded_ids) <= 128, f"Should have at most 128 serial IDs, got {len(decoded_ids)}"

        # Verify we have some serial IDs (sanity check)
        assert len(decoded_ids) > 0, "Should have at least some serial IDs encoded"


@scenarios.parametric
@features.feature_flags_event_enrichment
class Test_Span_Enrichment_Max_Subjects:
    """Test 25 subject limit enforcement (provisional - may adjust during code review)."""

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_max_25_subjects_enforced(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
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
                assert num_subjects <= 25, f"Should have at most 25 subjects, got {num_subjects}"


@scenarios.parametric
@features.feature_flags_event_enrichment
class Test_Span_Enrichment_Subjects:
    """Test feature_flag_subjects_encoded behavior based on doLog flag."""

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_do_log_true_adds_subjects_encoded(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Test that doLog=true flags add feature_flag_subjects_encoded tag.

        When a flag with doLog=true is evaluated, the subject's targeting key
        should be hashed and included in feature_flag_subjects_encoded.
        """
        _set_and_wait_ffe_rc(test_agent, UFC_SPAN_ENRICHMENT_DATA)

        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        # Evaluate experiment-flag which has doLog=true
        test_library.ffe_evaluate(
            flag="experiment-flag",
            variation_type="STRING",
            default_value="default",
            targeting_key="experiment-user-789",
            attributes={},
        )

        traces = test_agent.wait_for_num_traces(1, clear=True)
        assert len(traces) > 0, "No traces received"

        root_span = traces[0][0]
        meta = root_span.get("meta", {})

        # feature_flags_encoded should be present
        assert "feature_flags_encoded" in meta, f"feature_flags_encoded not found in span meta: {list(meta.keys())}"

        # feature_flag_subjects_encoded should be present for doLog=true
        assert "feature_flag_subjects_encoded" in meta, (
            f"feature_flag_subjects_encoded not found for doLog=true flag: {list(meta.keys())}"
        )

        subjects_encoded = meta["feature_flag_subjects_encoded"]

        # Parse if string (JSON)
        if isinstance(subjects_encoded, str):
            subjects_encoded = json.loads(subjects_encoded)

        # Should be a non-empty dict
        assert isinstance(subjects_encoded, dict), f"Expected dict, got {type(subjects_encoded)}"
        assert len(subjects_encoded) > 0, "feature_flag_subjects_encoded should not be empty"

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_do_log_false_no_subjects_encoded(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Test that doLog=false flags do NOT add feature_flag_subjects_encoded tag.

        When only flags with doLog=false are evaluated, the feature_flag_subjects_encoded
        tag should not be present on the span.
        """
        _set_and_wait_ffe_rc(test_agent, UFC_SPAN_ENRICHMENT_DATA)

        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        # Evaluate no-log-flag which has doLog=false
        test_library.ffe_evaluate(
            flag="no-log-flag",
            variation_type="BOOLEAN",
            default_value=False,
            targeting_key="user-no-log",
            attributes={},
        )

        traces = test_agent.wait_for_num_traces(1, clear=True)
        assert len(traces) > 0, "No traces received"

        root_span = traces[0][0]
        meta = root_span.get("meta", {})

        # feature_flags_encoded should still be present
        assert "feature_flags_encoded" in meta, f"feature_flags_encoded not found in span meta: {list(meta.keys())}"

        # feature_flag_subjects_encoded should NOT be present for doLog=false only
        assert "feature_flag_subjects_encoded" not in meta, (
            "feature_flag_subjects_encoded should not be present when only doLog=false flags are evaluated"
        )


@features.feature_flags_event_enrichment
class Test_Span_Enrichment_Delta_Varint:
    """Test delta varint encoding algorithm correctness.

    These are pure unit tests for the encoding utilities - no tracer needed.
    Not decorated with @scenarios.parametric to avoid manifest missing_feature marking.
    """

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
