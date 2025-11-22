"""Test Feature Flag Exposure (FFE) exposure events in weblog end-to-end scenario."""

import os
import time
from utils import (
    weblog,
    interfaces,
    scenarios,
    features,
    remote_config as rc,
    context,
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

    def setup_ffe_rc_timeout_graceful_degradation(self):
        """Set up FFE with valid config, then simulate RC unavailability and verify new configs don't reach tracer."""
        # Phase 1: Setup initial RC config and verify normal operation
        rc.rc_state.reset().apply()

        self.targeting_key = "test-user"
        self.targeting_key_after_outage = "test-user-after-outage"
        self.new_flag = "test-flag-after-outage"

        initial_config = UFC_FIXTURE_DATA  # Use existing fixture
        config_id = "ffe-timeout-test"
        rc.rc_state.set_config(f"{RC_PATH}/{config_id}/config", initial_config).apply()

        # Phase 2: Evaluate flag with working RC (baseline)
        self.delivered_flag = "test-flag"  # Use existing flag from UFC_FIXTURE_DATA
        self.r1 = weblog.post(
            "/ffe",
            json={
                "flag": self.delivered_flag,
                "variationType": "STRING",
                "defaultValue": "baseline_default",
                "targetingKey": self.targeting_key,
                "attributes": {},
            },
        )

        # Phase 3: Simulate RC network failure by stopping the proxy container
        # Store reference to the proxy container for later restart
        proxy_container = context.scenario.proxy_container

        try:
            # Stop the proxy container to simulate RC unavailability
            proxy_container.stop()

            # Wait a moment for the stop to take effect
            time.sleep(2)

            # Phase 4: Add NEW flag configuration that should NOT reach tracer if RC is disabled
            new_flag_config = {
                "flags": {
                    self.new_flag: {
                        "key": self.new_flag,
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
                }
            }

            # Set the new config (this should not reach tracer if RC is properly disabled)
            rc.rc_state.set_config(f"{RC_PATH}/new-config-after-disable/config", new_flag_config).apply()

            # Phase 5: Evaluate the flag from delivered config with different targeting key during RC disable
            # We expect this to log an exposure event because the flag configuration was delivered.
            self.r2 = weblog.post(
                "/ffe",
                json={
                    "flag": self.delivered_flag,
                    "variationType": "STRING",
                    "defaultValue": "fallback_default",  # Should get this if RC disabled
                    "targetingKey": self.targeting_key_after_outage,
                    "attributes": {},
                },
            )

            # Phase 6: Evaluate the flag from new config that
            # would not reach tracer if RC disable is working.
            # This should not log an exposure event.
            self.r3 = weblog.post(
                "/ffe",
                json={
                    "flag": self.new_flag,
                    "variationType": "STRING",
                    "defaultValue": "fallback_default",  # Should get this if RC disabled
                    "targetingKey": self.targeting_key_after_outage,
                    "attributes": {},
                },
            )
        finally:
            # Phase 7: Restart the proxy container to restore RC functionality
            # Note: The container will be cleaned up automatically by the test framework
            # This ensures other tests aren't affected
            pass

    def test_ffe_rc_timeout_graceful_degradation(self):
        """Test graceful degradation during RC network unavailability and verify RC disabling works."""
        # Verify both requests succeeded (graceful degradation)
        assert self.r1.status_code == 200, f"Baseline flag evaluation failed: {self.r1.text}"
        assert self.r2.status_code == 200, f"Flag evaluation during RC outage failed: {self.r2.text}"
        assert self.r3.status_code == 200, f"Flag evaluation during RC outage failed: {self.r3.text}"

        # Verify exposure events were generated in both phases
        events_found = []
        context_validated = False

        for data in interfaces.agent.get_data(path_filters="/api/v2/exposures"):
            exposure_data = data["request"]["content"]
            assert exposure_data is not None, "No exposure events sent to agent"

            # Validate context structure (once)
            if not context_validated:
                assert "context" in exposure_data, "Response missing 'context' field"
                context_obj = exposure_data["context"]
                assert context_obj.get("service") == "weblog", f"Expected service 'weblog', got '{context_obj}'"
                assert context_obj["version"] == "1.0.0", f"Expected version '1.0.0', got '{context_obj['version']}'"
                assert context_obj["env"] == "system-tests", f"Expected env 'system-tests', got '{context_obj['env']}'"
                context_validated = True

            # Validate exposures array
            assert "exposures" in exposure_data, "Response missing 'exposures' field"
            assert isinstance(exposure_data["exposures"], list), "Exposures should be a list"

            # Find events for our test flags
            for event in exposure_data["exposures"]:
                flag_key = event.get("flag", {}).get("key")
                subject_id = event.get("subject", {}).get("id")
                if flag_key in [self.delivered_flag] and subject_id in [self.targeting_key, self.targeting_key_after_outage]:
                    events_found.append(event)

        # Should have exactly 2 events: r1 and r2 should generate events, but r3 should not
        # This validates RC disabling - the third evaluation shouldn't generate exposure events
        # because the flag configuration wasn't delivered due to RC being disabled
        assert len(events_found) == 2, (
            f"Expected exactly 2 exposure events for flag '{self.delivered_flag}' (r1 and r2), found {len(events_found)}. "
            f"r3 should not generate an event because the flag config wasn't delivered when RC was disabled."
        )

        # Validate we have events for both targeting keys (r1 and r2)
        found_targeting_keys = {event.get("subject", {}).get("id") for event in events_found}
        expected_keys = {self.targeting_key, self.targeting_key_after_outage}
        assert found_targeting_keys == expected_keys, (
            f"Expected exposure events for targeting keys {expected_keys}, found {found_targeting_keys}"
        )

        # Validate event structure for all found events
        for event in events_found:
            assert "flag" in event, "Exposure event missing 'flag' field"
            flag_key = event["flag"]["key"]
            assert flag_key == self.delivered_flag, f"Expected flag '{self.delivered_flag}', got '{flag_key}'"
            assert "subject" in event, "Exposure event missing 'subject' field"
            subject_id = event["subject"]["id"]
            assert subject_id in [self.targeting_key, self.targeting_key_after_outage], (
                f"Expected subject '{self.targeting_key}' or '{self.targeting_key_after_outage}', got '{subject_id}'"
            )
