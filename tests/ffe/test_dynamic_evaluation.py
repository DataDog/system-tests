"""Test feature flags dynamic evaluation via Remote Config."""

import json
import time
from http import HTTPStatus

from utils import (
    weblog,
    interfaces,
    scenarios,
    features,
    remote_config as rc,
)
from utils.proxy.mocked_response import StaticJsonMockedTracerResponse, MockedBackendResponse
from utils.proxy.rc_response_builder import build_rc_configurations_protobuf


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
@features.feature_flags_dynamic_evaluation
class Test_FFE_RC_Unavailable:
    """Test FFE SDK resilience when the Remote Configuration service becomes unavailable.

    This test validates that the local flag configuration cache inside the tracer
    can continue to perform evaluations even when RC returns errors.
    """

    def setup_ffe_rc_unavailable_graceful_degradation(self):
        """Set up FFE with valid config, then simulate RC unavailability and verify cached config still works."""
        self.config_request_data = None

        def wait_for_config_503(data: dict) -> bool:
            if data["path"] == "/v0.7/config" and data["response"]["status_code"] == HTTPStatus.SERVICE_UNAVAILABLE:
                self.config_request_data = data
                return True
            return False

        rc.tracer_rc_state.reset().apply()

        self.flag_key = "test-flag"  # From UFC_FIXTURE_DATA, returns "on"
        self.not_delivered_flag_key = "test-flag-not-delivered"
        self.default_value = "default_fallback"

        self.config_state = rc.tracer_rc_state.set_config(f"{RC_PATH}/ffe-test/config", UFC_FIXTURE_DATA).apply()

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
        StaticJsonMockedTracerResponse(
            path="/v0.7/config", mocked_json={"error": "Service Unavailable"}, status_code=503
        ).send()

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

        # Restore normal RC behavior (empty response)
        StaticJsonMockedTracerResponse(path="/v0.7/config", mocked_json={}).send()

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
@features.feature_flags_dynamic_evaluation
class Test_FFE_RC_Down_From_Start:
    """Test FFE behavior when RC is unavailable from application start."""

    def setup_ffe_rc_down_from_start(self):
        """Simulate RC being down from the start - no config ever delivered."""
        self.config_request_data = None

        def wait_for_config_503(data: dict) -> bool:
            if data["path"] == "/v0.7/config" and data["response"]["status_code"] == HTTPStatus.SERVICE_UNAVAILABLE:
                self.config_request_data = data
                return True
            return False

        StaticJsonMockedTracerResponse(
            path="/v0.7/config", mocked_json={"error": "Service Unavailable"}, status_code=503
        ).send()

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

        StaticJsonMockedTracerResponse(path="/v0.7/config", mocked_json={}).send()

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


@scenarios.feature_flagging_and_experimentation_backend
@features.feature_flags_dynamic_evaluation
class Test_FFE_RC_Delivery_Delay:
    """Demonstrate that FFE_FLAGS is NOT delivered within 5s when the Agent uses a 60s refresh interval.

    This test exercises the real Agent RC path (rc_backend_enabled=True) with a 60s
    background poll interval. It posts an FFE_FLAGS config to the mocked backend, waits
    5 seconds, and asserts the tracer has NOT received it.

    Root cause: the Agent's cache bypass fires on new *clients*, not new *products*.
    The tracer's RC client is already active (started for APM), so when FFE_FLAGS is
    registered, no bypass fires. The Agent only discovers FFE_FLAGS on its next
    background poll — 60s later.

    This test codifies the problem described in the fast-lane proposal. When the Agent
    ships the product-aware bypass fix, this test should be updated to assert that
    FFE_FLAGS IS delivered within 5s.
    """

    WAIT_SECONDS = 5

    def setup_ffe_rc_delivery_delay(self):
        """Post FFE_FLAGS config to mocked backend and wait 5 seconds."""
        # Build the RC payload with FFE_FLAGS config
        rc_state = rc.backend_rc_state
        rc_state.reset()
        rc_state.set_config(f"{RC_PATH}/ffe-speed-test/config", UFC_FIXTURE_DATA)
        rc_state.version += 1
        payload = rc_state.to_payload()

        # Post protobuf to the mocked backend (Agent will pick it up on next poll)
        rc_protobuf = build_rc_configurations_protobuf(payload)
        MockedBackendResponse(path="/api/v0.1/configurations", content=rc_protobuf).send()

        # Wait 5 seconds — enough for the tracer to poll many times (1s interval),
        # but NOT enough for the Agent's 60s background poll to fire
        time.sleep(self.WAIT_SECONDS)

    def test_ffe_rc_delivery_delay(self):
        """Assert FFE_FLAGS has NOT been acknowledged by the tracer within 5 seconds.

        With a 60s Agent refresh interval and no product-aware bypass, the Agent's
        cache does not contain FFE_FLAGS yet. The tracer polls the Agent every 1s
        but gets empty responses. No FFE_FLAGS config_state should appear.
        """
        ffe_states_found = []

        for data in interfaces.library.get_data(path_filters="/v0.7/config"):
            config_states = (
                data.get("request", {}).get("content", {}).get("client", {}).get("state", {}).get("config_states", [])
            )
            for config_state in config_states:
                if config_state.get("product") == RC_PRODUCT:
                    ffe_states_found.append(config_state)

        assert len(ffe_states_found) == 0, (
            f"FFE_FLAGS was delivered within {self.WAIT_SECONDS}s despite 60s Agent refresh interval. "
            f"This should not happen without the product-aware bypass fix. "
            f"Found {len(ffe_states_found)} FFE_FLAGS config states: {ffe_states_found}"
        )
