"""Test feature flag span enrichment in weblog end-to-end scenario.

This module tests that feature flag evaluations properly enrich APM spans with:
1. feature_flags_encoded: delta varint encoded serial IDs for all evaluated flags within a span chunk
2. feature_flag_subjects_encoded: subject hash -> serial IDs mapping (when doLog=true)
"""

import json
from pathlib import Path

from utils import (
    weblog,
    interfaces,
    scenarios,
    features,
    remote_config as rc,
)
from utils.ffe.varint import decode_delta_varint


RC_PRODUCT = "FFE_FLAGS"
RC_PATH = f"datadog/2/{RC_PRODUCT}"


def _load_span_enrichment_fixture() -> dict:
    """Load the UFC fixture file for span enrichment tests."""
    fixture_path = Path(__file__).parent / "span-enrichment-flags.json"
    with fixture_path.open() as f:
        return json.load(f)


UFC_SPAN_ENRICHMENT_DATA = _load_span_enrichment_fixture()


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_event_enrichment
class Test_Span_Enrichment_Basic:
    """Test feature_flags_encoded span tag for basic flag evaluations."""

    def setup_single_flag_evaluation(self):
        """Set up single flag evaluation for span enrichment test."""
        rc.tracer_rc_state.reset().apply()

        config_id = "span-enrichment-config"
        rc.tracer_rc_state.set_config(f"{RC_PATH}/{config_id}/config", UFC_SPAN_ENRICHMENT_DATA).apply()

        self.flag = "basic-flag"
        self.targeting_key = "user-123"
        self.expected_serial_id = 100

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag,
                "variationType": "BOOLEAN",
                "defaultValue": False,
                "targetingKey": self.targeting_key,
                "attributes": {},
            },
        )

    def test_single_flag_evaluation(self):
        """Test that evaluating a single flag adds feature_flags_encoded to span."""
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        def validate_span(span):
            meta = span.get("meta", {})
            if "feature_flags_encoded" not in meta:
                return False

            encoded = meta["feature_flags_encoded"]
            decoded_ids = decode_delta_varint(encoded)
            return self.expected_serial_id in decoded_ids

        interfaces.library.validate_one_span(
            self.r,
            validator=validate_span,
            full_trace=True,
        )

    def setup_multiple_flag_evaluations(self):
        """Set up multiple flag evaluations for combined encoding test."""
        rc.tracer_rc_state.reset().apply()

        config_id = "span-enrichment-config"
        rc.tracer_rc_state.set_config(f"{RC_PATH}/{config_id}/config", UFC_SPAN_ENRICHMENT_DATA).apply()

        self.targeting_key = "user-456"
        self.expected_serial_ids = [100, 108]  # basic-flag and experiment-flag

        # Evaluate basic-flag
        self.r1 = weblog.post(
            "/ffe",
            json={
                "flag": "basic-flag",
                "variationType": "BOOLEAN",
                "defaultValue": False,
                "targetingKey": self.targeting_key,
                "attributes": {},
            },
        )

        # Evaluate experiment-flag
        self.r2 = weblog.post(
            "/ffe",
            json={
                "flag": "experiment-flag",
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": self.targeting_key,
                "attributes": {},
            },
        )

    def test_multiple_flag_evaluations(self):
        """Test that multiple flag evaluations combine serial IDs in one tag."""
        assert self.r1.status_code == 200, f"First flag evaluation failed: {self.r1.text}"
        assert self.r2.status_code == 200, f"Second flag evaluation failed: {self.r2.text}"

        def validate_span(span):
            meta = span.get("meta", {})
            if "feature_flags_encoded" not in meta:
                return False

            encoded = meta["feature_flags_encoded"]
            decoded_ids = decode_delta_varint(encoded)

            # Both serial IDs should be present
            return all(sid in decoded_ids for sid in self.expected_serial_ids)

        # Validate on the last request's span (should contain all evaluations)
        interfaces.library.validate_one_span(
            self.r2,
            validator=validate_span,
            full_trace=True,
        )


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_event_enrichment
class Test_Span_Enrichment_Subjects:
    """Test feature_flag_subjects_encoded span tag for experiment flags."""

    def setup_do_log_true(self):
        """Set up flag evaluation with doLog=true for subjects encoding test."""
        rc.tracer_rc_state.reset().apply()

        config_id = "span-enrichment-config"
        rc.tracer_rc_state.set_config(f"{RC_PATH}/{config_id}/config", UFC_SPAN_ENRICHMENT_DATA).apply()

        self.flag = "experiment-flag"  # has doLog: true
        self.targeting_key = "experiment-user-789"

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": self.targeting_key,
                "attributes": {},
            },
        )

    def test_do_log_true(self):
        """Test that doLog=true flags add feature_flag_subjects_encoded tag."""
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        def validate_span(span):
            meta = span.get("meta", {})

            # feature_flags_encoded should be present
            if "feature_flags_encoded" not in meta:
                return False

            # feature_flag_subjects_encoded should be present for doLog=true
            if "feature_flag_subjects_encoded" not in meta:
                return False

            subjects_encoded = meta["feature_flag_subjects_encoded"]

            # Should be a non-empty dict/object
            if not isinstance(subjects_encoded, (dict, str)):
                return False

            # If it's a string (JSON), parse it
            if isinstance(subjects_encoded, str):
                try:
                    subjects_encoded = json.loads(subjects_encoded)
                except json.JSONDecodeError:
                    return False

            return len(subjects_encoded) > 0

        interfaces.library.validate_one_span(
            self.r,
            validator=validate_span,
            full_trace=True,
        )

    def setup_do_log_false(self):
        """Set up flag evaluation with doLog=false for subjects encoding test."""
        rc.tracer_rc_state.reset().apply()

        config_id = "span-enrichment-config"
        rc.tracer_rc_state.set_config(f"{RC_PATH}/{config_id}/config", UFC_SPAN_ENRICHMENT_DATA).apply()

        self.flag = "no-log-flag"  # has doLog: false
        self.targeting_key = "user-no-log"

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag,
                "variationType": "BOOLEAN",
                "defaultValue": False,
                "targetingKey": self.targeting_key,
                "attributes": {},
            },
        )

    def test_do_log_false(self):
        """Test that doLog=false flags do NOT add feature_flag_subjects_encoded tag."""
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        def validate_span(span):
            meta = span.get("meta", {})

            # feature_flags_encoded should still be present
            if "feature_flags_encoded" not in meta:
                return False

            # feature_flag_subjects_encoded should NOT be present for doLog=false only
            # Note: This check is tricky because if other doLog=true flags were evaluated,
            # subjects_encoded might still exist. This test assumes isolation.
            # For a pure doLog=false evaluation, subjects_encoded should not exist.
            return "feature_flag_subjects_encoded" not in meta

        interfaces.library.validate_one_span(
            self.r,
            validator=validate_span,
            full_trace=True,
        )
