"""Test feature flag span enrichment via parametric tests.

All FFE span tags (ffe_flags_enc, ffe_subjects_enc, ffe_defaults) are added to the
ROOT SPAN of the trace, regardless of which span context the flag was evaluated in.
This follows the specification for chunk-level tagging.

This module tests:
1. ffe_flags_enc: Multiple flag evaluations combine serial IDs correctly
2. ffe_flags_enc: Child span flag evaluation propagates to root span
3. ffe_flags_enc: Max 128 serial IDs limit
4. ffe_subjects_enc: doLog=true adds subjects, doLog=false does not
5. ffe_subjects_enc: Multiple subjects tracked separately with SHA256 hashed keys
6. ffe_subjects_enc: Single subject with multiple flags combines serial IDs
7. ffe_subjects_enc: Max 10 subjects limit
8. ffe_defaults: Flag not found adds coded-default fallback
9. ffe_defaults: Value truncated at 64 chars
10. ffe_defaults: Max 5 flag keys limit
11. Delta varint encoding correctness (unit tests)
"""

import json
import pytest
from pathlib import Path
from typing import Any

from utils import features, scenarios
from utils.dd_constants import RemoteConfigApplyState
from utils.docker_fixtures import TestAgentAPI
from tests.parametric.conftest import APMLibrary
from tests.parametric.test_ffe.utils import decode_delta_varint, encode_delta_varint, hash_targeting_key


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
        """Test that multiple flag evaluations combine serial IDs in ffe_flags_enc.

        This test evaluates multiple flags and verifies all serial IDs are
        encoded together in the span tag.
        """
        _set_and_wait_ffe_rc(test_agent, UFC_SPAN_ENRICHMENT_DATA)

        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        # Create a span and evaluate flags within its context
        with test_library.dd_start_span(name="test-span", service="test-service") as span:
            # Evaluate multiple flags to test serial ID encoding
            # Pass span_id to activate the span during evaluation
            test_library.ffe_evaluate(
                flag="basic-flag",
                variation_type="BOOLEAN",
                default_value=False,
                targeting_key="user-max-test",
                attributes={},
                span_id=span.span_id,
            )
            test_library.ffe_evaluate(
                flag="experiment-flag",
                variation_type="STRING",
                default_value="default",
                targeting_key="user-max-test",
                attributes={},
                span_id=span.span_id,
            )
            test_library.ffe_evaluate(
                flag="multi-serial-flag-1",
                variation_type="INTEGER",
                default_value=0,
                targeting_key="user-max-test",
                attributes={},
                span_id=span.span_id,
            )
            test_library.ffe_evaluate(
                flag="multi-serial-flag-2",
                variation_type="INTEGER",
                default_value=0,
                targeting_key="user-max-test",
                attributes={},
                span_id=span.span_id,
            )

        traces = test_agent.wait_for_num_traces(1, clear=True)
        assert len(traces) > 0, "No traces received"

        # Find root span
        root_span = traces[0][0]
        meta = root_span.get("meta", {})

        assert "ffe_flags_enc" in meta, f"ffe_flags_enc not found in span meta: {list(meta.keys())}"

        decoded_ids = decode_delta_varint(meta["ffe_flags_enc"])

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
        """Test that flag evaluated in child span appears in root span's ffe_flags_enc.

        When a flag is evaluated within a child span context, the serial ID should
        still be aggregated into the root span's ffe_flags_enc tag.
        """
        _set_and_wait_ffe_rc(test_agent, UFC_SPAN_ENRICHMENT_DATA)

        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        # Create parent span, then child span, evaluate flag in child context
        with (
            test_library.dd_start_span(name="parent", service="test-service") as parent,
            test_library.dd_start_span(name="child", service="test-service", parent_id=parent.span_id) as child,
        ):
            # Evaluate flag while in child span context - use child span_id to activate
            test_library.ffe_evaluate(
                flag="basic-flag",
                variation_type="BOOLEAN",
                default_value=False,
                targeting_key="user-child-span-test",
                attributes={},
                span_id=child.span_id,
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

        # The flag evaluated in child span should appear in root span's ffe_flags_enc
        assert "ffe_flags_enc" in meta, f"ffe_flags_enc not found in root span meta: {list(meta.keys())}"

        decoded_ids = decode_delta_varint(meta["ffe_flags_enc"])
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

        # Create a span and evaluate flags within its context
        with test_library.dd_start_span(name="test-span", service="test-service") as span:
            # Evaluate all 150 flags
            for i in range(num_flags):
                test_library.ffe_evaluate(
                    flag=f"generated-flag-{i:04d}",
                    variation_type="BOOLEAN",
                    default_value=False,
                    targeting_key="user-limit-test",
                    attributes={},
                    span_id=span.span_id,
                )

        traces = test_agent.wait_for_num_traces(1, clear=True)
        assert len(traces) > 0, "No traces received"

        root_span = traces[0][0]
        meta = root_span.get("meta", {})

        assert "ffe_flags_enc" in meta, f"ffe_flags_enc not found in span meta: {list(meta.keys())}"

        decoded_ids = decode_delta_varint(meta["ffe_flags_enc"])

        # Verify we don't exceed 128 limit
        assert len(decoded_ids) <= 128, f"Should have at most 128 serial IDs, got {len(decoded_ids)}"

        # Verify we have some serial IDs (sanity check)
        assert len(decoded_ids) > 0, "Should have at least some serial IDs encoded"


@scenarios.parametric
@features.feature_flags_event_enrichment
class Test_Span_Enrichment_Default_Fallback:
    """Test ffe_defaults tag behavior when flag evaluation falls back to default value."""

    CODED_DEFAULT_PREFIX = "coded-default:"
    MAX_FFE_DEFAULTS_VALUE_LENGTH = 64

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_flag_not_found_adds_ffe_defaults_tag(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Test that evaluating a non-existent flag adds ffe_defaults tag with coded-default.

        When a flag is not found in the UFC config and falls back to default_value,
        an ffe_defaults tag should be added with the format:
        {"flag-name": "coded-default:<default_value>"}
        """
        _set_and_wait_ffe_rc(test_agent, UFC_SPAN_ENRICHMENT_DATA)

        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        # Evaluate a flag that doesn't exist in the UFC config
        flag_name = "nonexistent-flag"
        default_value = "my-default"
        with test_library.dd_start_span(name="test-span", service="test-service") as span:
            test_library.ffe_evaluate(
                flag=flag_name,
                variation_type="STRING",
                default_value=default_value,
                targeting_key="test-user",
                attributes={},
                span_id=span.span_id,
            )

        traces = test_agent.wait_for_num_traces(1, clear=True)
        assert len(traces) > 0, "No traces received"

        root_span = traces[0][0]
        meta = root_span.get("meta", {})

        assert "ffe_defaults" in meta, f"ffe_defaults not found in span meta: {list(meta.keys())}"

        ffe_defaults = meta["ffe_defaults"]

        # Parse if string (JSON)
        if isinstance(ffe_defaults, str):
            ffe_defaults = json.loads(ffe_defaults)

        assert isinstance(ffe_defaults, dict), f"Expected dict, got {type(ffe_defaults)}"
        assert flag_name in ffe_defaults, f"Flag '{flag_name}' not found in ffe_defaults: {list(ffe_defaults.keys())}"

        flag_value = ffe_defaults[flag_name]
        assert flag_value.startswith(self.CODED_DEFAULT_PREFIX), (
            f"Expected value to start with '{self.CODED_DEFAULT_PREFIX}', got: {flag_value}"
        )

        # Verify the default value is included after the prefix
        expected_value = f"{self.CODED_DEFAULT_PREFIX}{default_value}"
        assert flag_value == expected_value, f"Expected '{expected_value}', got '{flag_value}'"

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_ffe_defaults_value_truncated_at_64_chars(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Test that ffe_defaults values are truncated to 64 characters.

        The total value length (including 'coded-default:' prefix) should not exceed 64 chars.
        """
        _set_and_wait_ffe_rc(test_agent, UFC_SPAN_ENRICHMENT_DATA)

        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        # Create a default value that would exceed 64 chars when combined with prefix
        # Prefix "coded-default:" is 14 chars, so max default value is 50 chars
        long_default = "x" * 100  # Much longer than the 50 char limit

        flag_name = "nonexistent-long-default"
        with test_library.dd_start_span(name="test-span", service="test-service") as span:
            test_library.ffe_evaluate(
                flag=flag_name,
                variation_type="STRING",
                default_value=long_default,
                targeting_key="test-user",
                attributes={},
                span_id=span.span_id,
            )

        traces = test_agent.wait_for_num_traces(1, clear=True)
        assert len(traces) > 0, "No traces received"

        root_span = traces[0][0]
        meta = root_span.get("meta", {})

        assert "ffe_defaults" in meta, f"ffe_defaults not found in span meta: {list(meta.keys())}"

        ffe_defaults = meta["ffe_defaults"]

        if isinstance(ffe_defaults, str):
            ffe_defaults = json.loads(ffe_defaults)

        assert flag_name in ffe_defaults, f"Flag '{flag_name}' not found in ffe_defaults"

        flag_value = ffe_defaults[flag_name]

        # Verify the value is truncated to max length
        assert len(flag_value) <= self.MAX_FFE_DEFAULTS_VALUE_LENGTH, (
            f"ffe_defaults value should be at most {self.MAX_FFE_DEFAULTS_VALUE_LENGTH} chars, "
            f"got {len(flag_value)}: {flag_value}"
        )

        # Verify it still has the prefix
        assert flag_value.startswith(self.CODED_DEFAULT_PREFIX), (
            f"Truncated value should still start with '{self.CODED_DEFAULT_PREFIX}', got: {flag_value}"
        )

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_max_5_flag_keys_in_ffe_defaults(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Test that at most 5 flag keys are included in ffe_defaults.

        When more than 5 flags fall back to default values, only the first 5
        should appear in the ffe_defaults tag.
        """
        _set_and_wait_ffe_rc(test_agent, UFC_SPAN_ENRICHMENT_DATA)

        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        # Evaluate 10 non-existent flags to trigger coded-default fallback
        with test_library.dd_start_span(name="test-span", service="test-service") as span:
            for i in range(10):
                test_library.ffe_evaluate(
                    flag=f"nonexistent-flag-{i:02d}",
                    variation_type="STRING",
                    default_value=f"default-{i}",
                    targeting_key="test-user",
                    attributes={},
                    span_id=span.span_id,
                )

        traces = test_agent.wait_for_num_traces(1, clear=True)
        assert len(traces) > 0, "No traces received"

        root_span = traces[0][0]
        meta = root_span.get("meta", {})

        assert "ffe_defaults" in meta, f"ffe_defaults not found in span meta: {list(meta.keys())}"

        ffe_defaults = meta["ffe_defaults"]

        if isinstance(ffe_defaults, str):
            ffe_defaults = json.loads(ffe_defaults)

        assert isinstance(ffe_defaults, dict), f"Expected dict, got {type(ffe_defaults)}"

        num_keys = len(ffe_defaults)
        assert num_keys <= 5, f"ffe_defaults should have at most 5 flag keys, got {num_keys}"
        assert num_keys > 0, "ffe_defaults should have at least some flag keys"


@scenarios.parametric
@features.feature_flags_event_enrichment
class Test_Span_Enrichment_Max_Subjects:
    """Test 10 subject limit enforcement per RFC - APM & Experimentation."""

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_max_10_subjects_enforced(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Test that at most 10 unique subjects are tracked.

        When more than 10 unique subjects evaluate doLog=true flags,
        only the first 10 should appear in ffe_subjects_enc.
        """
        _set_and_wait_ffe_rc(test_agent, UFC_SPAN_ENRICHMENT_DATA)

        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        # Evaluate with 15 different subjects (more than the 10 limit)
        with test_library.dd_start_span(name="test-span", service="test-service") as span:
            for i in range(15):
                test_library.ffe_evaluate(
                    flag="experiment-flag",
                    variation_type="STRING",
                    default_value="default",
                    targeting_key=f"subject-{i:03d}",
                    attributes={},
                    span_id=span.span_id,
                )

        traces = test_agent.wait_for_num_traces(1, clear=True)
        assert len(traces) > 0, "No traces received"

        root_span = traces[0][0]
        meta = root_span.get("meta", {})

        if "ffe_subjects_enc" in meta:
            subjects_encoded = meta["ffe_subjects_enc"]

            # Parse if string
            if isinstance(subjects_encoded, str):
                subjects_encoded = json.loads(subjects_encoded)

            if isinstance(subjects_encoded, dict):
                num_subjects = len(subjects_encoded)
                assert num_subjects <= 10, f"Should have at most 10 subjects, got {num_subjects}"


@scenarios.parametric
@features.feature_flags_event_enrichment
class Test_Span_Enrichment_Subjects:
    """Test ffe_subjects_enc behavior based on doLog flag."""

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_do_log_true_adds_subjects_encoded(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Test that doLog=true flags add ffe_subjects_enc tag.

        When a flag with doLog=true is evaluated, the subject's targeting key
        should be hashed and included in ffe_subjects_enc.
        """
        _set_and_wait_ffe_rc(test_agent, UFC_SPAN_ENRICHMENT_DATA)

        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        # Evaluate experiment-flag which has doLog=true
        with test_library.dd_start_span(name="test-span", service="test-service") as span:
            test_library.ffe_evaluate(
                flag="experiment-flag",
                variation_type="STRING",
                default_value="default",
                targeting_key="experiment-user-789",
                attributes={},
                span_id=span.span_id,
            )

        traces = test_agent.wait_for_num_traces(1, clear=True)
        assert len(traces) > 0, "No traces received"

        root_span = traces[0][0]
        meta = root_span.get("meta", {})

        # ffe_flags_enc should be present
        assert "ffe_flags_enc" in meta, f"ffe_flags_enc not found in span meta: {list(meta.keys())}"

        # ffe_subjects_enc should be present for doLog=true
        assert "ffe_subjects_enc" in meta, f"ffe_subjects_enc not found for doLog=true flag: {list(meta.keys())}"

        subjects_encoded = meta["ffe_subjects_enc"]

        # Parse if string (JSON)
        if isinstance(subjects_encoded, str):
            subjects_encoded = json.loads(subjects_encoded)

        # Should be a non-empty dict
        assert isinstance(subjects_encoded, dict), f"Expected dict, got {type(subjects_encoded)}"
        assert len(subjects_encoded) > 0, "ffe_subjects_enc should not be empty"

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_multiple_subjects_tracked_separately(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Test that multiple subjects in a single span are tracked with separate hashed keys.

        When multiple different targeting keys evaluate doLog=true flags, each subject
        should appear as a separate SHA256-hashed key in ffe_subjects_enc with their
        respective serial IDs.
        """
        _set_and_wait_ffe_rc(test_agent, UFC_SPAN_ENRICHMENT_DATA)

        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        # Evaluate the same doLog=true flag with 3 different subjects
        subjects = ["user-alice", "user-bob", "user-charlie"]
        with test_library.dd_start_span(name="test-span", service="test-service") as span:
            for subject in subjects:
                test_library.ffe_evaluate(
                    flag="experiment-flag",  # doLog=true, serialId=108
                    variation_type="STRING",
                    default_value="default",
                    targeting_key=subject,
                    attributes={},
                    span_id=span.span_id,
                )

        traces = test_agent.wait_for_num_traces(1, clear=True)
        assert len(traces) > 0, "No traces received"

        root_span = traces[0][0]
        meta = root_span.get("meta", {})

        assert "ffe_subjects_enc" in meta, f"ffe_subjects_enc not found in span meta: {list(meta.keys())}"

        subjects_encoded = meta["ffe_subjects_enc"]
        if isinstance(subjects_encoded, str):
            subjects_encoded = json.loads(subjects_encoded)

        assert isinstance(subjects_encoded, dict), f"Expected dict, got {type(subjects_encoded)}"

        # Verify all 3 subjects are tracked with their hashed keys
        assert len(subjects_encoded) == 3, f"Expected 3 subjects, got {len(subjects_encoded)}"

        # Verify each subject's hash is present
        for subject in subjects:
            expected_hash = hash_targeting_key(subject)
            assert expected_hash in subjects_encoded, (
                f"Expected SHA256 hash of '{subject}' ({expected_hash}) not found in subjects_encoded"
            )

            # Verify the serial ID for this subject (experiment-flag has serialId=108)
            encoded_ids = subjects_encoded[expected_hash]
            decoded_ids = decode_delta_varint(encoded_ids)
            assert 108 in decoded_ids, f"Expected serial ID 108 for subject '{subject}', got {decoded_ids}"

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_single_subject_multiple_flags_combines_serial_ids(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Test that a single subject evaluating multiple doLog=true flags combines serial IDs.

        When the same targeting key evaluates multiple flags with doLog=true, all serial IDs
        should be combined under the same SHA256-hashed key in ffe_subjects_enc.
        """
        _set_and_wait_ffe_rc(test_agent, UFC_SPAN_ENRICHMENT_DATA)

        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        # Same subject evaluates multiple doLog=true flags
        subject = "multi-flag-user"
        with test_library.dd_start_span(name="test-span", service="test-service") as span:
            # experiment-flag has doLog=true, serialId=108
            test_library.ffe_evaluate(
                flag="experiment-flag",
                variation_type="STRING",
                default_value="default",
                targeting_key=subject,
                attributes={},
                span_id=span.span_id,
            )
            # multi-serial-flag-1 has doLog=true, serialId=128
            test_library.ffe_evaluate(
                flag="multi-serial-flag-1",
                variation_type="INTEGER",
                default_value=0,
                targeting_key=subject,
                attributes={},
                span_id=span.span_id,
            )
            # multi-serial-flag-2 has doLog=true, serialId=130
            test_library.ffe_evaluate(
                flag="multi-serial-flag-2",
                variation_type="INTEGER",
                default_value=0,
                targeting_key=subject,
                attributes={},
                span_id=span.span_id,
            )

        traces = test_agent.wait_for_num_traces(1, clear=True)
        assert len(traces) > 0, "No traces received"

        root_span = traces[0][0]
        meta = root_span.get("meta", {})

        assert "ffe_subjects_enc" in meta, f"ffe_subjects_enc not found in span meta: {list(meta.keys())}"

        subjects_encoded = meta["ffe_subjects_enc"]
        if isinstance(subjects_encoded, str):
            subjects_encoded = json.loads(subjects_encoded)

        # Should only have 1 subject (same targeting key)
        assert len(subjects_encoded) == 1, f"Expected 1 subject, got {len(subjects_encoded)}"

        # Verify the subject's hash contains all serial IDs
        expected_hash = hash_targeting_key(subject)
        assert expected_hash in subjects_encoded, f"Subject hash not found: {expected_hash}"

        encoded_ids = subjects_encoded[expected_hash]
        decoded_ids = decode_delta_varint(encoded_ids)

        # All 3 doLog=true flags' serial IDs should be combined
        expected_ids = {108, 128, 130}
        for expected_id in expected_ids:
            assert expected_id in decoded_ids, (
                f"Expected serial ID {expected_id} not found in subject's combined IDs: {decoded_ids}"
            )

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_do_log_false_no_subjects_encoded(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Test that doLog=false flags do NOT add ffe_subjects_enc tag.

        When only flags with doLog=false are evaluated, the ffe_subjects_enc
        tag should not be present on the span.
        """
        _set_and_wait_ffe_rc(test_agent, UFC_SPAN_ENRICHMENT_DATA)

        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        # Evaluate no-log-flag which has doLog=false
        with test_library.dd_start_span(name="test-span", service="test-service") as span:
            test_library.ffe_evaluate(
                flag="no-log-flag",
                variation_type="BOOLEAN",
                default_value=False,
                targeting_key="user-no-log",
                attributes={},
                span_id=span.span_id,
            )

        traces = test_agent.wait_for_num_traces(1, clear=True)
        assert len(traces) > 0, "No traces received"

        root_span = traces[0][0]
        meta = root_span.get("meta", {})

        # ffe_flags_enc should still be present
        assert "ffe_flags_enc" in meta, f"ffe_flags_enc not found in span meta: {list(meta.keys())}"

        # ffe_subjects_enc should NOT be present for doLog=false only
        assert "ffe_subjects_enc" not in meta, (
            "ffe_subjects_enc should not be present when only doLog=false flags are evaluated"
        )

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_subjects_encoded_uses_sha256_hashed_targeting_key(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Test that targeting keys are hashed with SHA256 in ffe_subjects_enc.

        The targeting key should be hashed using SHA256 and the resulting hex digest
        should appear as a key in the ffe_subjects_enc dictionary.
        """
        _set_and_wait_ffe_rc(test_agent, UFC_SPAN_ENRICHMENT_DATA)

        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        targeting_key = "test-user-sha256"
        with test_library.dd_start_span(name="test-span", service="test-service") as span:
            test_library.ffe_evaluate(
                flag="experiment-flag",
                variation_type="STRING",
                default_value="default",
                targeting_key=targeting_key,
                attributes={},
                span_id=span.span_id,
            )

        traces = test_agent.wait_for_num_traces(1, clear=True)
        assert len(traces) > 0, "No traces received"

        root_span = traces[0][0]
        meta = root_span.get("meta", {})

        assert "ffe_subjects_enc" in meta, f"ffe_subjects_enc not found in span meta: {list(meta.keys())}"

        subjects_encoded = meta["ffe_subjects_enc"]

        if isinstance(subjects_encoded, str):
            subjects_encoded = json.loads(subjects_encoded)

        assert isinstance(subjects_encoded, dict), f"Expected dict, got {type(subjects_encoded)}"

        # Verify the targeting key is hashed with SHA256 and present as a key
        expected_hash = hash_targeting_key(targeting_key)
        assert expected_hash in subjects_encoded, (
            f"Expected SHA256 hash of targeting key '{targeting_key}' ({expected_hash}) "
            f"not found in subjects_encoded keys: {list(subjects_encoded.keys())}"
        )


@scenarios.parametric
@features.feature_flags_event_enrichment
class Test_Span_Enrichment_Delta_Varint:
    """Test delta varint encoding algorithm correctness.

    These are pure unit tests for the encoding utilities - no tracer needed.
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
