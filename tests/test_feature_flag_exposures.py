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
        # Set up Remote Config
        config_id = "ffe-test-config"
        rc_config = {
            "action": "apply",
            "flag_configuration": UFC_FIXTURE_DATA,
            "flag_environment": "test",
            "id": config_id,
        }
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

        for data in interfaces.agent.get_data(path_filters="/api/v2/exposures"):
            # validate data sent to /api/v2/exposures

            exposure_data = data["request"]["content"]
            # Validate that exposure data was received
            assert exposure_data is not None, "No exposure events were sent to agent"

            # Validate context object
            assert "context" in exposure_data, "Response missing 'context' field"
            context = exposure_data["context"]
            assert (
                context["service_name"] == "weblog"
            ), f"Expected service_name 'weblog', got '{context['service_name']}'"
            assert context["version"] == "1.0.0", f"Expected version '1.0.0', got '{context['version']}'"
            assert context["env"] == "system-tests", f"Expected env 'system-tests', got '{context['env']}'"

            # Validate exposures array
            assert "exposures" in exposure_data, "Response missing 'exposures' field"
            assert isinstance(exposure_data["exposures"], list), "Exposures should be a list"
            assert len(exposure_data["exposures"]) > 0, "Expected at least one exposure event"

            # Validate structure of exposure event
            event = exposure_data["exposures"][0]
            assert "flag" in event, "Exposure event missing 'flag' field"
            assert "key" in event["flag"], "Flag missing 'key' field"
            assert event["flag"]["key"] == self.flag, f"Expected flag '{self.flag}', got '{event['flag']['key']}'"

            assert "subject" in event, "Exposure event missing 'subject' field"
            assert (
                event["subject"]["id"] == self.targeting_key
            ), f"Expected subject '{self.targeting_key}', got '{event['subject']['id']}'"
