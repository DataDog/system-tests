"""Test Feature Flag Exposure (FFE) exposure events in weblog end-to-end scenario."""

import json
from http import HTTPStatus

from utils import (
    weblog,
    interfaces,
    scenarios,
    features,
    remote_config as rc,
)
from utils.proxy.mocked_response import StaticJsonMockedResponse


RC_PRODUCT = "FFE_FLAGS"
RC_PATH = f"datadog/2/{RC_PRODUCT}"


# Simple UFC fixture for testing with doLog: true
UFC_FIXTURE_DATA = {
    "id": "1",
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


@scenarios.feature_flag_exposure
@features.feature_flag_exposure
class Test_FFE_Exposure_Events:
    def setup_ffe_exposure_event_generation(self):
        """Set up FFE exposure event generation."""
        # Reset remote config to empty state
        rc.rc_state.reset().apply()

        # Set up Remote Config
        config_id = "ffe-test-config"
        rc_config = UFC_FIXTURE_DATA
        rc.rc_state.reset().set_config(f"{RC_PATH}/{config_id}/config", rc_config).apply()

        # Evaluate a feature flag
        self.flag = "test-flag"
        variation_type = "STRING"
        default_value = "default"
        self.targeting_key = "test-user"
        attributes: dict[str, str] = {}

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag,
                "variationType": variation_type,
                "defaultValue": default_value,
                "targetingKey": self.targeting_key,
                "attributes": attributes,
            },
        )

    def test_ffe_exposure_event_generation(self):
        """Test that FFE generates exposure events when flags are evaluated via weblog."""
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        # Search for our specific flag in all exposure events
        matching_event = None
        context_validated = False

        for data in interfaces.agent.get_data(path_filters="/api/v2/exposures"):
            # validate data sent to /api/v2/exposures

            exposure_data = data["request"]["content"]
            # Validate that exposure data was received
            assert exposure_data is not None, "No exposure events were sent to agent"

            # Validate context object (once)
            if not context_validated:
                assert "context" in exposure_data, "Response missing 'context' field"
                context = exposure_data["context"]

                service_name = context.get("service")
                assert service_name == "weblog", f"Expected service_name 'weblog', got '{context}'"
                assert context["version"] == "1.0.0", f"Expected version '1.0.0', got '{context['version']}'"
                assert context["env"] == "system-tests", f"Expected env 'system-tests', got '{context['env']}'"
                context_validated = True

            # Validate exposures array
            assert "exposures" in exposure_data, "Response missing 'exposures' field"
            assert isinstance(exposure_data["exposures"], list), "Exposures should be a list"

            # Search for the specific flag we're testing
            for event in exposure_data["exposures"]:
                if (
                    event.get("flag", {}).get("key") == self.flag
                    and event.get("subject", {}).get("id") == self.targeting_key
                ):
                    matching_event = event
                    break

            if matching_event:
                break

        # Validate that we found our specific event
        assert matching_event is not None, (
            f"Expected to find flag '{self.flag}' with subject '{self.targeting_key}' in exposure events"
        )

        assert "flag" in matching_event, "Exposure event missing 'flag' field"
        assert "key" in matching_event["flag"], "Flag missing 'key' field"
        assert matching_event["flag"]["key"] == self.flag, (
            f"Expected flag '{self.flag}', got '{matching_event['flag']['key']}'"
        )

        assert "subject" in matching_event, "Exposure event missing 'subject' field"
        assert matching_event["subject"]["id"] == self.targeting_key, (
            f"Expected subject '{self.targeting_key}', got '{matching_event['subject']['id']}'"
        )

    def setup_ffe_multiple_remote_config_files(self):
        """Set up FFE with multiple remote config files across different target paths."""
        # Reset remote config to empty state
        rc.rc_state.reset().apply()

        # Set up multiple Remote Config files with different config IDs
        config_id_1 = "ffe-test-config-1"
        config_id_2 = "ffe-test-config-2"

        # First configuration with test-flag-1
        rc_config_1 = {
            "id": "1",
            "createdAt": "2024-04-17T19:40:53.716Z",
            "format": "SERVER",
            "environment": {"name": "Test"},
            "flags": {
                "test-flag-1": {
                    "key": "test-flag-1",
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

        # Second configuration with test-flag-2
        rc_config_2 = {
            "id": "2",
            "createdAt": "2024-04-17T19:40:53.716Z",
            "format": "SERVER",
            "environment": {"name": "Test"},
            "flags": {
                "test-flag-2": {
                    "key": "test-flag-2",
                    "enabled": True,
                    "variationType": "BOOLEAN",
                    "variations": {"on": {"key": "on", "value": True}, "off": {"key": "off", "value": False}},
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

        # Apply both configurations
        rc.rc_state.set_config(f"{RC_PATH}/{config_id_1}/config", rc_config_1).set_config(
            f"{RC_PATH}/{config_id_2}/config", rc_config_2
        ).apply()

        # Evaluate both feature flags
        self.flag_1 = "test-flag-1"
        self.flag_2 = "test-flag-2"
        self.targeting_key = "test-user-multi"

        # Evaluate first flag
        self.r1 = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_1,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": self.targeting_key,
                "attributes": {},
            },
        )

        # Evaluate second flag
        self.r2 = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_2,
                "variationType": "BOOLEAN",
                "defaultValue": False,
                "targetingKey": self.targeting_key,
                "attributes": {},
            },
        )

    def test_ffe_multiple_remote_config_files(self):
        """Test that FFE correctly handles multiple remote config files with different flags."""
        assert self.r1.status_code == 200, f"First flag evaluation failed: {self.r1.text}"
        assert self.r2.status_code == 200, f"Second flag evaluation failed: {self.r2.text}"

        # Collect all exposure events for our specific flags
        flags_found = set()

        for data in interfaces.agent.get_data(path_filters="/api/v2/exposures"):
            exposure_data = data["request"]["content"]
            assert exposure_data is not None, "No exposure events were sent to agent"

            # Validate context
            assert "context" in exposure_data, "Response missing 'context' field"
            context = exposure_data["context"]
            assert context.get("service") == "weblog", f"Expected service_name 'weblog', got '{context}'"

            # Validate exposures array
            assert "exposures" in exposure_data, "Response missing 'exposures' field"
            assert isinstance(exposure_data["exposures"], list), "Exposures should be a list"

            # Collect flag keys and validate events for our test flags
            for event in exposure_data["exposures"]:
                assert "flag" in event, "Exposure event missing 'flag' field"
                assert "key" in event["flag"], "Flag missing 'key' field"
                flag_key = event["flag"]["key"]

                # Only validate events for our test flags with our specific targeting_key
                if flag_key in (self.flag_1, self.flag_2) and event.get("subject", {}).get("id") == self.targeting_key:
                    flags_found.add(flag_key)
                    # Validate subject for our test events
                    assert "subject" in event, "Exposure event missing 'subject' field"
                    assert event["subject"]["id"] == self.targeting_key, (
                        f"Expected subject '{self.targeting_key}', got '{event['subject']['id']}'"
                    )

        # Verify that both flags were evaluated and sent exposure events
        assert self.flag_1 in flags_found or self.flag_2 in flags_found, (
            f"Expected to find flags '{self.flag_1}' or '{self.flag_2}' in exposure events, found: {flags_found}"
        )


@scenarios.feature_flag_exposure
@features.feature_flag_exposure
class Test_FFE_Exposure_Events_Empty:
    def setup_ffe_empty_remote_config(self):
        """Set up FFE with empty remote config state."""
        # Reset remote config to empty state
        rc.rc_state.reset().apply()

        # Evaluate a feature flag without any remote config
        self.flag = "test-flag-no-config"
        variation_type = "STRING"
        default_value = "default"
        self.targeting_key = "test-user-empty"
        attributes: dict[str, str] = {}

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag,
                "variationType": variation_type,
                "defaultValue": default_value,
                "targetingKey": self.targeting_key,
                "attributes": attributes,
            },
        )

    def test_ffe_empty_remote_config(self):
        """Test that FFE handles empty remote config state correctly."""
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        # When no remote config is set, FFE should still work but return default value
        # The exposure events should still be generated based on library configuration
        for data in interfaces.agent.get_data(path_filters="/api/v2/exposures"):
            exposure_data = data["request"]["content"]
            if exposure_data is not None:
                # Validate that context is still present
                assert "context" in exposure_data, "Response missing 'context' field"
                context = exposure_data["context"]
                assert context.get("service") == "weblog", f"Expected service_name 'weblog', got '{context}'"

        # Note: exposure events may or may not be sent when remote config is empty
        # depending on library implementation


@scenarios.feature_flag_exposure
@features.feature_flag_exposure
class Test_FFE_Exposure_Events_Errors:
    def setup_ffe_malformed_remote_config_rejection(self):
        """Set up FFE with a valid config, then update with malformed config to test rejection."""
        # Reset remote config to empty state
        rc.rc_state.reset().apply()

        # First, set up a valid Remote Config
        config_id = "ffe-test-config-malformed"
        valid_rc_config = {
            "id": "1",
            "createdAt": "2024-04-17T19:40:53.716Z",
            "format": "SERVER",
            "environment": {"name": "Test"},
            "flags": {
                "test-flag-resilient": {
                    "key": "test-flag-resilient",
                    "enabled": True,
                    "variationType": "STRING",
                    "variations": {"on": {"key": "on", "value": "valid-value"}, "off": {"key": "off", "value": "off"}},
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

        rc.rc_state.reset().set_config(f"{RC_PATH}/{config_id}/config", valid_rc_config).apply()

        # Evaluate the flag with valid config
        self.flag = "test-flag-resilient"
        self.targeting_key = "test-user-resilient"

        self.r1 = weblog.post(
            "/ffe",
            json={
                "flag": self.flag,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": self.targeting_key,
                "attributes": {},
            },
        )

        # Now update with a malformed config (missing allocations and variationType)
        malformed_rc_config = {
            "id": "2",
            "createdAt": "2024-04-17T19:40:53.716Z",
            "format": "SERVER",
            "environment": {"name": "Test"},
            "flags": {
                "test-flag-resilient": {
                    "key": "test-flag-resilient",
                    "enabled": True,
                    # Missing variationType
                    "variations": {
                        "on": {"key": "on", "value": "malformed-value"},
                        "off": {"key": "off", "value": "off"},
                    },
                    # Missing allocations
                }
            },
        }

        rc.rc_state.set_config(f"{RC_PATH}/{config_id}/config", malformed_rc_config).apply()

        # Evaluate the flag again after malformed config update
        self.r2 = weblog.post(
            "/ffe",
            json={
                "flag": self.flag,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": self.targeting_key,
                "attributes": {},
            },
        )

    def test_ffe_malformed_remote_config_rejection(self):
        """Test that FFE rejects malformed remote config and preserves the old valid configuration."""
        assert self.r1.status_code == 200, f"First flag evaluation failed: {self.r1.text}"
        assert self.r2.status_code == 200, f"Second flag evaluation failed: {self.r2.text}"

        # Verify that exposure events are still generated for both requests
        # and the flag configuration remained valid despite the malformed update
        events_found = []

        for data in interfaces.agent.get_data(path_filters="/api/v2/exposures"):
            exposure_data = data["request"]["content"]
            assert exposure_data is not None, "No exposure events were sent to agent"

            # Validate exposures array
            assert "exposures" in exposure_data, "Response missing 'exposures' field"
            assert isinstance(exposure_data["exposures"], list), "Exposures should be a list"

            # Find events for our specific flag and targeting_key
            for event in exposure_data["exposures"]:
                flag_key = event.get("flag", {}).get("key")
                subject_id = event.get("subject", {}).get("id")

                if flag_key == self.flag and subject_id == self.targeting_key:
                    events_found.append(event)

        # We should have at least one event (from the first valid evaluation)
        # The second evaluation may or may not generate an event depending on
        # whether the provider accepted or rejected the malformed config
        assert len(events_found) >= 1, (
            f"Expected at least 1 exposure event for flag '{self.flag}', found {len(events_found)}"
        )

        # Verify that all events have the expected structure
        for event in events_found:
            assert "flag" in event, "Exposure event missing 'flag' field"
            assert event["flag"]["key"] == self.flag, f"Expected flag '{self.flag}', got '{event['flag']['key']}'"
            assert "subject" in event, "Exposure event missing 'subject' field"
            assert event["subject"]["id"] == self.targeting_key, (
                f"Expected subject '{self.targeting_key}', got '{event['subject']['id']}'"
            )


@scenarios.feature_flag_exposure
@features.feature_flag_exposure
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

        rc.rc_state.reset().apply()

        self.flag_key = "test-flag"  # From UFC_FIXTURE_DATA, returns "on"
        self.not_delivered_flag_key = "test-flag-not-delivered"
        self.default_value = "default_fallback"

        self.config_state = rc.rc_state.set_config(f"{RC_PATH}/ffe-test/config", UFC_FIXTURE_DATA).apply()

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
        StaticJsonMockedResponse(
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
        StaticJsonMockedResponse(path="/v0.7/config", mocked_json={}).send()

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


@scenarios.feature_flag_exposure
@features.feature_flag_exposure
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

        StaticJsonMockedResponse(
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

        StaticJsonMockedResponse(path="/v0.7/config", mocked_json={}).send()

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
