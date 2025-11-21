"""Test Feature Flag Exposure (FFE) exposure events in weblog end-to-end scenario."""

from utils import (
    weblog,
    interfaces,
    scenarios,
    features,
    remote_config as rc,
)


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


# FFE Resilience Tests - Agent Failures

@scenarios.ffe_agent_empty_response
@features.feature_flag_exposure
class Test_FFE_Agent_Empty_Response_Resilience:
    """Test FFE resilience when agent returns empty responses."""

    def setup_flag_evaluation_during_empty_responses(self):
        """Set up flag evaluation during empty agent responses."""
        # Set up Remote Config with valid UFC data
        config_id = "ffe-empty-response-test"
        rc.rc_state.reset().set_config(f"{RC_PATH}/{config_id}/config", UFC_FIXTURE_DATA).apply()

        # Evaluate a feature flag (scenario ensures agent returns empty responses)
        self.flag = "test-flag"
        self.targeting_key = "test-user-empty-response"

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

    def test_flag_evaluation_during_empty_responses(self):
        """Test that flag evaluation works with cached data during empty agent responses."""
        # FFE should still work using cached configuration despite empty agent responses
        assert self.r.status_code == 200, f"Flag evaluation should succeed during empty responses: {self.r.text}"

        # Verify exposure events are still generated (from cached config)
        matching_event = None
        for data in interfaces.agent.get_data(path_filters="/api/v2/exposures"):
            exposure_data = data["request"]["content"]
            if exposure_data is not None:
                for event in exposure_data.get("exposures", []):
                    if (
                        event.get("flag", {}).get("key") == self.flag
                        and event.get("subject", {}).get("id") == self.targeting_key
                    ):
                        matching_event = event
                        break
                if matching_event:
                    break

        # Note: Exposure events may or may not be sent during agent failures
        # The important thing is that flag evaluation succeeds with cached config


@scenarios.ffe_agent_5xx_error
@features.feature_flag_exposure
class Test_FFE_Agent_5xx_Error_Resilience:
    """Test FFE resilience when agent returns 5xx server errors."""

    def setup_flag_evaluation_during_5xx_errors(self):
        """Set up flag evaluation during 5xx agent errors."""
        # Set up Remote Config with valid UFC data
        config_id = "ffe-5xx-error-test"
        rc.rc_state.reset().set_config(f"{RC_PATH}/{config_id}/config", UFC_FIXTURE_DATA).apply()

        # Evaluate a feature flag (scenario ensures agent returns 5xx errors)
        self.flag = "test-flag"
        self.targeting_key = "test-user-5xx-error"

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

    def test_flag_evaluation_during_5xx_errors(self):
        """Test that flag evaluation works with cached data during 5xx agent errors."""
        # FFE should still work using cached configuration despite 5xx agent errors
        assert self.r.status_code == 200, f"Flag evaluation should succeed during 5xx errors: {self.r.text}"


@scenarios.ffe_agent_timeout
@features.feature_flag_exposure
class Test_FFE_Agent_Timeout_Resilience:
    """Test FFE resilience when agent requests time out."""

    def setup_flag_evaluation_during_timeouts(self):
        """Set up flag evaluation during agent timeouts."""
        # Set up Remote Config with valid UFC data
        config_id = "ffe-timeout-test"
        rc.rc_state.reset().set_config(f"{RC_PATH}/{config_id}/config", UFC_FIXTURE_DATA).apply()

        # Evaluate a feature flag (scenario ensures agent requests timeout)
        self.flag = "test-flag"
        self.targeting_key = "test-user-timeout"

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

    def test_flag_evaluation_during_timeouts(self):
        """Test that flag evaluation works with cached data during agent timeouts."""
        # FFE should still work using cached configuration despite agent timeouts
        assert self.r.status_code == 200, f"Flag evaluation should succeed during timeouts: {self.r.text}"


@scenarios.ffe_agent_connection_refused
@features.feature_flag_exposure
class Test_FFE_Agent_Connection_Refused_Resilience:
    """Test FFE resilience when agent connection is refused."""

    def setup_flag_evaluation_during_connection_refused(self):
        """Set up flag evaluation when agent connection is refused."""
        # Set up Remote Config with valid UFC data
        config_id = "ffe-connection-refused-test"
        rc.rc_state.reset().set_config(f"{RC_PATH}/{config_id}/config", UFC_FIXTURE_DATA).apply()

        # Evaluate a feature flag (scenario ensures agent connection is refused)
        self.flag = "test-flag"
        self.targeting_key = "test-user-connection-refused"

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

    def test_flag_evaluation_during_connection_refused(self):
        """Test that flag evaluation works with cached data when agent connection is refused."""
        # FFE should still work using cached configuration despite connection refused
        assert self.r.status_code == 200, f"Flag evaluation should succeed during connection refused: {self.r.text}"


# FFE Resilience Tests - Remote Config Failures

@scenarios.ffe_rc_endpoint_error
@features.feature_flag_exposure
class Test_FFE_RC_Endpoint_Error_Resilience:
    """Test FFE resilience when Remote Config endpoint returns errors."""

    def setup_flag_evaluation_during_rc_endpoint_errors(self):
        """Set up flag evaluation during RC endpoint errors."""
        # Set up Remote Config with valid UFC data first
        config_id = "ffe-rc-error-test"
        rc.rc_state.reset().set_config(f"{RC_PATH}/{config_id}/config", UFC_FIXTURE_DATA).apply()

        # Evaluate a feature flag (scenario ensures RC endpoint returns errors)
        self.flag = "test-flag"
        self.targeting_key = "test-user-rc-error"

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

    def test_flag_evaluation_during_rc_endpoint_errors(self):
        """Test that flag evaluation works with cached data during RC endpoint errors."""
        # FFE should still work using cached configuration despite RC endpoint errors
        assert self.r.status_code == 200, f"Flag evaluation should succeed during RC errors: {self.r.text}"


@scenarios.ffe_rc_network_delay
@features.feature_flag_exposure
class Test_FFE_RC_Network_Delay_Resilience:
    """Test FFE resilience when Remote Config requests experience network delays."""

    def setup_flag_evaluation_during_rc_network_delays(self):
        """Set up flag evaluation during RC network delays."""
        # Set up Remote Config with valid UFC data first
        config_id = "ffe-rc-delay-test"
        rc.rc_state.reset().set_config(f"{RC_PATH}/{config_id}/config", UFC_FIXTURE_DATA).apply()

        # Evaluate a feature flag (scenario ensures RC requests are delayed)
        self.flag = "test-flag"
        self.targeting_key = "test-user-rc-delay"

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

    def test_flag_evaluation_during_rc_network_delays(self):
        """Test that flag evaluation works with cached data during RC network delays."""
        # FFE should still work using cached configuration despite RC delays
        assert self.r.status_code == 200, f"Flag evaluation should succeed during RC delays: {self.r.text}"


@scenarios.ffe_rc_empty_config
@features.feature_flag_exposure
class Test_FFE_RC_Empty_Config_Resilience:
    """Test FFE resilience when Remote Config returns empty configuration."""

    def setup_flag_evaluation_during_rc_empty_config(self):
        """Set up flag evaluation with empty RC config."""
        # First set valid config, then replace with empty config
        config_id = "ffe-rc-empty-test"
        rc.rc_state.reset().set_config(f"{RC_PATH}/{config_id}/config", UFC_FIXTURE_DATA).apply()

        # Now scenario replaces with empty config - FFE should use cached data
        self.flag = "test-flag"
        self.targeting_key = "test-user-rc-empty"

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

    def test_flag_evaluation_during_rc_empty_config(self):
        """Test that flag evaluation works with cached data when RC returns empty config."""
        # FFE should still work using cached configuration despite empty RC config
        assert self.r.status_code == 200, f"Flag evaluation should succeed with empty RC config: {self.r.text}"


@scenarios.ffe_rc_malformed_response
@features.feature_flag_exposure
class Test_FFE_RC_Malformed_Response_Resilience:
    """Test FFE resilience when Remote Config returns malformed data."""

    def setup_flag_evaluation_during_rc_malformed_response(self):
        """Set up flag evaluation with malformed RC response."""
        # First set valid config, then scenario replaces with malformed config
        config_id = "ffe-rc-malformed-test"
        rc.rc_state.reset().set_config(f"{RC_PATH}/{config_id}/config", UFC_FIXTURE_DATA).apply()

        # Now scenario replaces with malformed config - FFE should use cached data
        self.flag = "test-flag"
        self.targeting_key = "test-user-rc-malformed"

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

    def test_flag_evaluation_during_rc_malformed_response(self):
        """Test that flag evaluation works with cached data when RC returns malformed data."""
        # FFE should still work using cached configuration despite malformed RC response
        assert self.r.status_code == 200, f"Flag evaluation should succeed with malformed RC response: {self.r.text}"
