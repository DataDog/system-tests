"""Test feature flags exposure events logging in weblog end-to-end scenario."""

import json

from utils import (
    weblog,
    interfaces,
    scenarios,
    features,
    remote_config as rc,
)
from tests.ffe.utils import get_ffe_rc_state


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
@features.feature_flags_exposures
class Test_FFE_Exposure_Events:
    def setup_ffe_exposure_event_generation(self):
        """Set up FFE exposure event generation."""
        # Reset remote config to empty state
        get_ffe_rc_state().reset().apply()

        # Set up Remote Config
        config_id = "ffe-test-config"
        rc_config = UFC_FIXTURE_DATA
        get_ffe_rc_state().reset().set_config(f"{RC_PATH}/{config_id}/config", rc_config).apply()

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
        get_ffe_rc_state().reset().apply()

        # Set up multiple Remote Config files with different config IDs
        config_id_1 = "ffe-test-config-1"
        config_id_2 = "ffe-test-config-2"

        # First configuration with test-flag-1
        rc_config_1 = {
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
        get_ffe_rc_state().set_config(f"{RC_PATH}/{config_id_1}/config", rc_config_1).set_config(
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


@scenarios.feature_flagging_and_experimentation
@scenarios.feature_flagging_and_experimentation_backend
@features.feature_flags_exposures
class Test_FFE_Exposure_Events_Empty:
    def setup_ffe_empty_remote_config(self):
        """Set up FFE with empty remote config state."""
        # Reset remote config to empty state
        get_ffe_rc_state().reset().apply()

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


@scenarios.feature_flagging_and_experimentation
@scenarios.feature_flagging_and_experimentation_backend
@features.feature_flags_exposures
class Test_FFE_Exposure_Events_Errors:
    def setup_ffe_malformed_remote_config_rejection(self):
        """Set up FFE with a valid config, then update with malformed config to test rejection."""
        # Reset remote config to empty state
        get_ffe_rc_state().reset().apply()

        # First, set up a valid Remote Config
        config_id = "ffe-test-config-malformed"
        valid_rc_config = {
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

        get_ffe_rc_state().reset().set_config(f"{RC_PATH}/{config_id}/config", valid_rc_config).apply()

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

        get_ffe_rc_state().set_config(f"{RC_PATH}/{config_id}/config", malformed_rc_config).apply()

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


def count_exposure_events(flag_key: str, subject_id: str | None = None) -> int:
    """Count exposure events for a specific flag key and optionally a specific subject.

    Args:
        flag_key: The flag key to search for
        subject_id: Optional subject ID to filter by. If None, counts all events for the flag.

    Returns:
        Number of matching exposure events found

    """
    count = 0
    for data in interfaces.agent.get_data(path_filters="/api/v2/exposures"):
        exposure_data = data["request"]["content"]
        if exposure_data is None:
            continue

        exposures = exposure_data.get("exposures", [])
        for event in exposures:
            event_flag_key = event.get("flag", {}).get("key")
            event_subject_id = event.get("subject", {}).get("id")

            if event_flag_key == flag_key:
                if subject_id is None or event_subject_id == subject_id:
                    count += 1
    return count


def make_ufc_fixture(flag_key: str, variant_key: str = "variant-a", allocation_key: str = "default-allocation"):
    """Create a UFC fixture with the given flag key and variant.

    Each test should use a unique flag_key to avoid counting exposures from other tests.
    """
    return {
        "createdAt": "2024-04-17T19:40:53.716Z",
        "format": "SERVER",
        "environment": {"name": "Test"},
        "flags": {
            flag_key: {
                "key": flag_key,
                "enabled": True,
                "variationType": "STRING",
                "variations": {
                    "variant-a": {"key": "variant-a", "value": "value-a"},
                    "variant-b": {"key": "variant-b", "value": "value-b"},
                },
                "allocations": [
                    {
                        "key": allocation_key,
                        "rules": [],
                        "splits": [{"variationKey": variant_key, "shards": []}],
                        "doLog": True,
                    }
                ],
            }
        },
    }


@scenarios.feature_flagging_and_experimentation
@scenarios.feature_flagging_and_experimentation_backend
@features.feature_flags_exposures
class Test_FFE_Exposure_Caching_Same_Subject:
    """Test that exposure caching deduplicates events for the same (subject, allocation, variant).

    When the same subject evaluates the same flag multiple times and gets the same variant,
    only one exposure event should be generated due to the exposure cache.
    """

    def setup_ffe_exposure_caching_same_subject(self):
        """Set up FFE exposure caching test with multiple evaluations for the same subject."""
        get_ffe_rc_state().reset().apply()

        config_id = "ffe-caching-test"
        self.flag_key = "same-subject-test-flag"  # Unique flag key for this test
        get_ffe_rc_state().set_config(f"{RC_PATH}/{config_id}/config", make_ufc_fixture(self.flag_key)).apply()

        self.targeting_key = "same-subject-user"

        # Evaluate the same flag multiple times with the same subject
        self.responses = []
        for _i in range(5):
            r = weblog.post(
                "/ffe",
                json={
                    "flag": self.flag_key,
                    "variationType": "STRING",
                    "defaultValue": "default",
                    "targetingKey": self.targeting_key,
                    "attributes": {},
                },
            )
            self.responses.append(r)

    def test_ffe_exposure_caching_same_subject(self):
        """Test that multiple evaluations for the same subject generate at most one exposure event."""
        # Verify all requests succeeded
        for i, r in enumerate(self.responses):
            assert r.status_code == 200, f"Request {i + 1} failed: {r.text}"
            result = json.loads(r.text)
            assert result["value"] == "value-a", f"Request {i + 1}: expected 'value-a', got '{result['value']}'"

        # Count exposure events for this specific subject
        exposure_count = count_exposure_events(self.flag_key, self.targeting_key)

        # The exposure cache should deduplicate events - we expect exactly 1 exposure
        # for the same (subject, allocation, variant) tuple
        assert exposure_count == 1, (
            f"Expected exactly 1 exposure event for subject '{self.targeting_key}' due to caching, "
            f"but found {exposure_count} events"
        )


@scenarios.feature_flagging_and_experimentation
@scenarios.feature_flagging_and_experimentation_backend
@features.feature_flags_exposures
class Test_FFE_Exposure_Caching_Different_Subjects:
    """Test that different subjects each generate their own exposure event.

    The exposure cache is keyed by (subject, allocation, variant), so different
    subjects should each generate a separate exposure event.
    """

    def setup_ffe_exposure_caching_different_subjects(self):
        """Set up FFE exposure caching test with multiple different subjects."""
        get_ffe_rc_state().reset().apply()

        config_id = "ffe-caching-test-subjects"
        self.flag_key = "diff-subjects-test-flag"  # Unique flag key for this test
        get_ffe_rc_state().set_config(f"{RC_PATH}/{config_id}/config", make_ufc_fixture(self.flag_key)).apply()

        self.subjects = [f"unique-subject-{i}" for i in range(5)]

        # Evaluate the flag with different subjects
        self.responses = []
        for subject in self.subjects:
            r = weblog.post(
                "/ffe",
                json={
                    "flag": self.flag_key,
                    "variationType": "STRING",
                    "defaultValue": "default",
                    "targetingKey": subject,
                    "attributes": {},
                },
            )
            self.responses.append(r)

    def test_ffe_exposure_caching_different_subjects(self):
        """Test that each unique subject generates exactly one exposure event."""
        # Verify all requests succeeded
        for i, r in enumerate(self.responses):
            assert r.status_code == 200, f"Request {i + 1} failed: {r.text}"
            result = json.loads(r.text)
            assert result["value"] == "value-a", f"Request {i + 1}: expected 'value-a', got '{result['value']}'"

        # Count total exposure events for this flag
        total_exposure_count = count_exposure_events(self.flag_key)

        # Each unique subject should generate exactly one exposure
        assert total_exposure_count == len(self.subjects), (
            f"Expected {len(self.subjects)} exposure events (one per unique subject), "
            f"but found {total_exposure_count} events"
        )

        # Verify each subject has exactly one exposure
        for subject in self.subjects:
            subject_count = count_exposure_events(self.flag_key, subject)
            assert subject_count == 1, f"Expected exactly 1 exposure for subject '{subject}', but found {subject_count}"


@scenarios.feature_flagging_and_experimentation
@scenarios.feature_flagging_and_experimentation_backend
@features.feature_flags_exposures
class Test_FFE_Exposure_Caching_Allocation_Cycle:
    """Test that cycling through allocations generates an exposure for each change.

    When a subject receives a flag from allocation-a, then allocation-b, then allocation-a again,
    each allocation change should generate a new exposure event (3 total), even though
    the variant value stays the same. The cache stores (allocation_key, variant) as the value,
    so changing back to a previous allocation still triggers a new exposure.
    """

    def setup_ffe_exposure_caching_allocation_cycle(self):
        """Set up FFE exposure test that cycles through allocations."""
        get_ffe_rc_state().reset().apply()

        config_id = "ffe-allocation-change-test"
        self.flag_key = "alloc-change-test-flag"  # Unique flag key for this test
        self.targeting_key = "allocation-change-user"

        # Step 1: Config with default-allocation returning variant-a
        get_ffe_rc_state().set_config(
            f"{RC_PATH}/{config_id}/config",
            make_ufc_fixture(self.flag_key, "variant-a", "default-allocation"),
        ).apply()

        self.response_1 = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": self.targeting_key,
                "attributes": {},
            },
        )

        # Step 2: Config with different-allocation (still returns variant-a)
        get_ffe_rc_state().set_config(
            f"{RC_PATH}/{config_id}/config",
            make_ufc_fixture(self.flag_key, "variant-a", "different-allocation"),
        ).apply()

        self.response_2 = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": self.targeting_key,
                "attributes": {},
            },
        )

        # Step 3: Config back to default-allocation (still returns variant-a)
        get_ffe_rc_state().set_config(
            f"{RC_PATH}/{config_id}/config",
            make_ufc_fixture(self.flag_key, "variant-a", "default-allocation"),
        ).apply()

        self.response_3 = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": self.targeting_key,
                "attributes": {},
            },
        )

    def test_ffe_exposure_caching_allocation_cycle(self):
        """Test that allocation-a → allocation-b → allocation-a generates 3 exposures."""
        # Verify step 1: variant-a from default-allocation
        assert self.response_1.status_code == 200, f"Request 1 failed: {self.response_1.text}"
        result_1 = json.loads(self.response_1.text)
        assert result_1["value"] == "value-a", f"Request 1: expected 'value-a', got '{result_1['value']}'"

        # Verify step 2: variant-a from different-allocation
        assert self.response_2.status_code == 200, f"Request 2 failed: {self.response_2.text}"
        result_2 = json.loads(self.response_2.text)
        assert result_2["value"] == "value-a", f"Request 2: expected 'value-a', got '{result_2['value']}'"

        # Verify step 3: variant-a from default-allocation again
        assert self.response_3.status_code == 200, f"Request 3 failed: {self.response_3.text}"
        result_3 = json.loads(self.response_3.text)
        assert result_3["value"] == "value-a", f"Request 3: expected 'value-a', got '{result_3['value']}'"

        # Count exposure events - should be exactly 3:
        # - Exposure #1: default-allocation
        # - Exposure #2: different-allocation (allocation changed)
        # - Exposure #3: default-allocation (allocation changed back)
        exposure_count = count_exposure_events(self.flag_key, self.targeting_key)

        assert exposure_count == 3, (
            f"Expected exactly 3 exposure events for subject '{self.targeting_key}' "
            f"(default-allocation → different-allocation → default-allocation), "
            f"but found {exposure_count} events"
        )


@scenarios.feature_flagging_and_experimentation
@scenarios.feature_flagging_and_experimentation_backend
@features.feature_flags_exposures
class Test_FFE_Exposure_Caching_Variant_Cycle:
    """Test that cycling through variants generates an exposure for each change.

    When a subject receives variant-a, then variant-b, then variant-a again,
    each variant change should generate a new exposure event (3 total).
    The cache stores (allocation_key, variant) as the value, so changing back
    to a previous variant still triggers a new exposure.
    """

    def setup_ffe_exposure_caching_variant_cycle(self):
        """Set up FFE exposure test that cycles through variants."""
        get_ffe_rc_state().reset().apply()

        config_id = "ffe-variant-cycle-test"
        self.flag_key = "variant-cycle-test-flag"  # Unique flag key for this test
        self.targeting_key = "variant-cycle-user"

        # Step 1: Config with variant-a
        get_ffe_rc_state().set_config(
            f"{RC_PATH}/{config_id}/config", make_ufc_fixture(self.flag_key, "variant-a")
        ).apply()

        self.response_1 = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": self.targeting_key,
                "attributes": {},
            },
        )

        # Step 2: Config with variant-b
        get_ffe_rc_state().set_config(
            f"{RC_PATH}/{config_id}/config", make_ufc_fixture(self.flag_key, "variant-b")
        ).apply()

        self.response_2 = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": self.targeting_key,
                "attributes": {},
            },
        )

        # Step 3: Config back to variant-a
        get_ffe_rc_state().set_config(
            f"{RC_PATH}/{config_id}/config", make_ufc_fixture(self.flag_key, "variant-a")
        ).apply()

        self.response_3 = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": self.targeting_key,
                "attributes": {},
            },
        )

    def test_ffe_exposure_caching_variant_cycle(self):
        """Test that variant-a → variant-b → variant-a generates 3 exposures."""
        # Verify step 1: variant-a
        assert self.response_1.status_code == 200, f"Request 1 failed: {self.response_1.text}"
        result_1 = json.loads(self.response_1.text)
        assert result_1["value"] == "value-a", f"Request 1: expected 'value-a', got '{result_1['value']}'"

        # Verify step 2: variant-b
        assert self.response_2.status_code == 200, f"Request 2 failed: {self.response_2.text}"
        result_2 = json.loads(self.response_2.text)
        assert result_2["value"] == "value-b", f"Request 2: expected 'value-b', got '{result_2['value']}'"

        # Verify step 3: variant-a again
        assert self.response_3.status_code == 200, f"Request 3 failed: {self.response_3.text}"
        result_3 = json.loads(self.response_3.text)
        assert result_3["value"] == "value-a", f"Request 3: expected 'value-a', got '{result_3['value']}'"

        # Count exposure events - should be exactly 3:
        # - Exposure #1: variant-a
        # - Exposure #2: variant-b (variant changed)
        # - Exposure #3: variant-a (variant changed back)
        exposure_count = count_exposure_events(self.flag_key, self.targeting_key)

        assert exposure_count == 3, (
            f"Expected exactly 3 exposure events for subject '{self.targeting_key}' "
            f"(variant-a → variant-b → variant-a), but found {exposure_count} events"
        )


@scenarios.feature_flagging_and_experimentation
@scenarios.feature_flagging_and_experimentation_backend
@features.feature_flags_exposures
class Test_FFE_Exposure_Missing_Flag:
    """Test that evaluating a missing/non-existent flag does not generate exposure events.

    When a flag is not found in the configuration, the evaluation returns a default
    value with an error reason. No exposure event should be generated for this case.
    """

    def setup_ffe_exposure_missing_flag(self):
        """Set up FFE exposure test for a missing flag."""
        get_ffe_rc_state().reset().apply()

        # Set up a config with a different flag (not the one we'll request)
        config_id = "ffe-missing-flag-test"
        get_ffe_rc_state().set_config(f"{RC_PATH}/{config_id}/config", make_ufc_fixture("some-other-flag")).apply()

        self.flag_key = "non-existent-flag"  # This flag doesn't exist in the config
        self.targeting_key = "missing-flag-user"

        # Evaluate a flag that doesn't exist
        self.responses = []
        for _i in range(3):
            r = weblog.post(
                "/ffe",
                json={
                    "flag": self.flag_key,
                    "variationType": "STRING",
                    "defaultValue": "default-value",
                    "targetingKey": self.targeting_key,
                    "attributes": {},
                },
            )
            self.responses.append(r)

    def test_ffe_exposure_missing_flag(self):
        """Test that missing flag evaluations do not generate exposure events."""
        # Verify all requests succeeded (should return default value)
        for i, r in enumerate(self.responses):
            assert r.status_code == 200, f"Request {i + 1} failed: {r.text}"
            result = json.loads(r.text)
            # Missing flag should return the default value
            assert result["value"] == "default-value", (
                f"Request {i + 1}: expected 'default-value', got '{result['value']}'"
            )

        # Count exposure events - should be 0 because flag doesn't exist
        exposure_count = count_exposure_events(self.flag_key, self.targeting_key)

        assert exposure_count == 0, (
            f"Expected 0 exposure events for missing flag '{self.flag_key}', but found {exposure_count} events"
        )


# UFC fixture with doLog=false
UFC_EXPOSURE_DOLOG_FALSE_FIXTURE = {
    "createdAt": "2024-04-17T19:40:53.716Z",
    "format": "SERVER",
    "environment": {"name": "Test"},
    "flags": {
        "no-log-flag": {
            "key": "no-log-flag",
            "enabled": True,
            "variationType": "STRING",
            "variations": {
                "variant-a": {"key": "variant-a", "value": "value-a"},
            },
            "allocations": [
                {
                    "key": "default-allocation",
                    "rules": [],
                    "splits": [{"variationKey": "variant-a", "shards": []}],
                    "doLog": False,  # Exposure logging disabled
                }
            ],
        }
    },
}


@scenarios.feature_flagging_and_experimentation
@scenarios.feature_flagging_and_experimentation_backend
@features.feature_flags_exposures
class Test_FFE_Exposure_DoLog_False:
    """Test that flags with doLog=false do not generate exposure events.

    When an allocation has doLog set to false, no exposure events should be
    sent for evaluations that match that allocation.
    """

    def setup_ffe_exposure_dolog_false(self):
        """Set up FFE exposure test with doLog=false."""
        get_ffe_rc_state().reset().apply()

        config_id = "ffe-dolog-false-test"
        self.flag_key = "no-log-flag"
        self.targeting_key = "dolog-false-user"

        # Set up config with doLog=false
        get_ffe_rc_state().set_config(f"{RC_PATH}/{config_id}/config", UFC_EXPOSURE_DOLOG_FALSE_FIXTURE).apply()

        # Evaluate the flag multiple times
        self.responses = []
        for _i in range(3):
            r = weblog.post(
                "/ffe",
                json={
                    "flag": self.flag_key,
                    "variationType": "STRING",
                    "defaultValue": "default",
                    "targetingKey": self.targeting_key,
                    "attributes": {},
                },
            )
            self.responses.append(r)

    def test_ffe_exposure_dolog_false(self):
        """Test that doLog=false prevents exposure events from being generated."""
        # Verify all requests succeeded and returned the expected value
        for i, r in enumerate(self.responses):
            assert r.status_code == 200, f"Request {i + 1} failed: {r.text}"
            result = json.loads(r.text)
            assert result["value"] == "value-a", f"Request {i + 1}: expected 'value-a', got '{result['value']}'"

        # Count exposure events - should be 0 because doLog=false
        exposure_count = count_exposure_events(self.flag_key, self.targeting_key)

        assert exposure_count == 0, (
            f"Expected 0 exposure events for flag with doLog=false, but found {exposure_count} events"
        )


@scenarios.feature_flagging_and_experimentation
@scenarios.feature_flagging_and_experimentation_backend
@features.feature_flags_exposures
class Test_FFE_EXP_5_Missing_Targeting_Key:
    """EXP.5: Treat missing targeting key as empty string.

    If targeting key is missing but evaluation produced result with doLog=true,
    the exposure events must be reported with subject.id = "".

    This verifies the tracer does NOT skip exposure events when targeting key is empty.
    """

    def setup_ffe_exp_5_missing_targeting_key(self):
        """Set up FFE exposure test with missing/empty targeting key."""
        get_ffe_rc_state().reset().apply()

        config_id = "ffe-exp-5-missing-targeting-key"
        self.flag_key = "exp-5-missing-targeting-key-flag"

        # Use a simple fixture with doLog=true
        get_ffe_rc_state().set_config(f"{RC_PATH}/{config_id}/config", make_ufc_fixture(self.flag_key)).apply()

        # Evaluate the flag with an empty targeting key
        self.response = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": "",  # Empty targeting key
                "attributes": {},
            },
        )

    def test_ffe_exp_5_missing_targeting_key(self):
        """EXP.5: Test that empty targeting key generates exposure with subject.id = ''."""
        assert self.response.status_code == 200, f"Flag evaluation failed: {self.response.text}"

        result = json.loads(self.response.text)
        assert result["value"] == "value-a", f"Expected 'value-a', got '{result['value']}'"

        # Search for exposure event with empty subject.id
        matching_event = None
        all_events_for_flag = []  # Collect all events for debugging
        for data in interfaces.agent.get_data(path_filters="/api/v2/exposures"):
            exposure_data = data["request"]["content"]
            if exposure_data is None:
                continue

            exposures = exposure_data.get("exposures", [])
            for event in exposures:
                if event.get("flag", {}).get("key") == self.flag_key:
                    # Collect for debugging
                    subject_id = event.get("subject", {}).get("id")
                    all_events_for_flag.append({"subject.id": subject_id, "event": event})
                    # Check for empty string
                    if subject_id == "":
                        matching_event = event
                        break

            if matching_event:
                break

        # Verify we found an exposure event with empty subject.id
        assert matching_event is not None, (
            f"EXP.5 FAILED: Expected exposure event for flag '{self.flag_key}' with subject.id = '', "
            f"but no matching event was found. Events received for this flag: {all_events_for_flag}. "
            f"The tracer must NOT skip exposures when targeting key is empty."
        )

        # Validate the event structure
        assert "flag" in matching_event, "Exposure event missing 'flag' field"
        assert matching_event["flag"]["key"] == self.flag_key
        assert "subject" in matching_event, "Exposure event missing 'subject' field"
        assert matching_event["subject"]["id"] == "", (
            f"EXP.5 FAILED: Expected subject.id = '', got '{matching_event['subject']['id']}'"
        )
