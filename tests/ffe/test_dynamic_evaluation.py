"""Test feature flags dynamic evaluation via Remote Config."""

import json
from http import HTTPStatus

from utils import (
    weblog,
    interfaces,
    scenarios,
    features,
    remote_config as rc,
)
from tests.ffe.utils import get_ffe_rc_state, get_rc_config_path, mock_rc_unavailable, restore_rc


RC_PRODUCT = "FFE_FLAGS"
RC_PATH = f"datadog/2/{RC_PRODUCT}"


# Simple UFC fixture for testing with doLog: true
UFC_FIXTURE_DATA = {
    "createdAt": "2024-04-17T19:40:53.716Z",
    "format": "SERVER",
    "environment": {"name": "Test"},
    "flags": {
        "test-flag": {
            "key": "test-flag",
            "enabled": True,
            "variationType": "STRING",
            "variations": {"on": {"key": "on", "value": "on"}, "off": {"key": "off", "value": "off"}},
            "allocations": [
                {
                    "key": "default-allocation",
                    "rules": [],
                    "splits": [{"variationKey": "on", "shards": []}],
                    "doLog": True,
                }
            ],
        }
    },
}


@scenarios.feature_flagging_and_experimentation
@scenarios.feature_flagging_and_experimentation_backend
@features.feature_flags_dynamic_evaluation
class Test_FFE_RC_Unavailable:
    """Test FFE SDK resilience when the Remote Configuration service becomes unavailable.

    This test validates that the local flag configuration cache inside the tracer
    can continue to perform evaluations even when RC returns errors.
    """

    def setup_ffe_rc_unavailable_graceful_degradation(self):
        """Set up FFE with valid config, then simulate RC unavailability and verify cached config still works."""
        self.config_request_data = None
        rc_path = get_rc_config_path()

        def wait_for_config_503(data: dict) -> bool:
            if data["path"] == rc_path and data["response"]["status_code"] == HTTPStatus.SERVICE_UNAVAILABLE:
                self.config_request_data = data
                return True
            return False

        get_ffe_rc_state().reset().apply()

        self.flag_key = "test-flag"  # From UFC_FIXTURE_DATA, returns "on"
        self.not_delivered_flag_key = "test-flag-not-delivered"
        self.default_value = "default_fallback"

        self.config_state = get_ffe_rc_state().set_config(f"{RC_PATH}/ffe-test/config", UFC_FIXTURE_DATA).apply()

        # Baseline: evaluate flag with RC working
        self.baseline_eval = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": self.default_value,
                "targetingKey": "user-1",
                "attributes": {},
            },
        )

        # Simulate RC unavailability by returning 503 errors
        mock_rc_unavailable()

        # Wait for tracer to receive 503 from RC before evaluating flag
        interfaces.library.wait_for(wait_for_config_503, timeout=60)

        # Evaluate cached flag while RC is unavailable
        self.cached_eval = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": self.default_value,
                "targetingKey": "user-2",
                "attributes": {},
            },
        )

        # Evaluate a flag that was not delivered via RC
        self.not_delivered_eval = weblog.post(
            "/ffe",
            json={
                "flag": self.not_delivered_flag_key,
                "variationType": "STRING",
                "defaultValue": self.default_value,
                "targetingKey": "user-3",
                "attributes": {},
            },
        )

        # Restore normal RC behavior
        restore_rc()

    def test_ffe_rc_unavailable_graceful_degradation(self):
        """Test that cached flag configs continue working when RC is unavailable."""
        # Verify tracer received 503 from RC
        assert self.config_request_data is not None, "No /v0.7/config request was captured"
        assert self.config_request_data["response"]["status_code"] == HTTPStatus.SERVICE_UNAVAILABLE, (
            f"Expected 503, got {self.config_request_data['response']['status_code']}"
        )

        expected_value = "on"

        assert self.baseline_eval.status_code == 200, f"Baseline request failed: {self.baseline_eval.text}"
        assert self.cached_eval.status_code == 200, f"Cached eval request failed: {self.cached_eval.text}"
        assert self.not_delivered_eval.status_code == 200, f"Not delivered eval failed: {self.not_delivered_eval.text}"

        baseline_result = json.loads(self.baseline_eval.text)
        assert baseline_result["value"] == expected_value, (
            f"Baseline: expected '{expected_value}', got '{baseline_result['value']}'"
        )

        cached_result = json.loads(self.cached_eval.text)
        assert cached_result["value"] == expected_value, (
            f"Cached eval during RC outage: expected '{expected_value}' from cache, got '{cached_result['value']}'"
        )

        not_delivered_result = json.loads(self.not_delivered_eval.text)
        assert not_delivered_result["value"] == self.default_value, (
            f"Not delivered flag: expected default '{self.default_value}', got '{not_delivered_result['value']}'"
        )


@scenarios.feature_flagging_and_experimentation
@scenarios.feature_flagging_and_experimentation_backend
@features.feature_flags_dynamic_evaluation
class Test_FFE_RC_Down_From_Start:
    """Test FFE behavior when RC is unavailable from application start."""

    def setup_ffe_rc_down_from_start(self):
        """Simulate RC being down from the start - no config ever delivered."""
        self.config_request_data = None
        rc_path = get_rc_config_path()

        def wait_for_config_503(data: dict) -> bool:
            if data["path"] == rc_path and data["response"]["status_code"] == HTTPStatus.SERVICE_UNAVAILABLE:
                self.config_request_data = data
                return True
            return False

        mock_rc_unavailable()

        # Wait for tracer to receive 503 from RC before evaluating flag
        interfaces.library.wait_for(wait_for_config_503, timeout=60)

        self.flag_key = "test-flag-never-delivered"
        self.default_value = "my-default-value"

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": self.default_value,
                "targetingKey": "user-rc-down",
                "attributes": {},
            },
        )

        restore_rc()

    def test_ffe_rc_down_from_start(self):
        """Test that default value is returned when RC is down from start."""
        # Verify tracer received 503 from RC
        assert self.config_request_data is not None, "No /v0.7/config request was captured"
        assert self.config_request_data["response"]["status_code"] == HTTPStatus.SERVICE_UNAVAILABLE, (
            f"Expected 503, got {self.config_request_data['response']['status_code']}"
        )

        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        result = json.loads(self.r.text)
        assert result["value"] == self.default_value, (
            f"Expected default '{self.default_value}', got '{result['value']}'"
        )
