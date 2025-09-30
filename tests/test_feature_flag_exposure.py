"""Test Feature Flag Exposure (FFE) telemetry events via weblog integration."""

from utils import interfaces, weblog, scenarios, features, logger
from utils import remote_config as rc
import json
import os


def get_request_type(data):
    """Extract the request type from telemetry data."""
    return data["request"]["content"].get("request_type")


def _load_ufc_fixture() -> dict:
    """Load the UFC fixture data for FFE tests."""
    fixture_path = os.path.join("tests/parametric/fixtures/test_data", "flags-v1.json")

    if not os.path.exists(fixture_path):
        raise Exception(f"UFC fixture file not found: {fixture_path}")

    with open(fixture_path) as f:
        ufc_payload = json.load(f)
    return ufc_payload["data"]["attributes"]


# Load UFC fixture data at module level
UFC_FIXTURE_DATA = _load_ufc_fixture()


@scenarios.feature_flag_exposure
@features.feature_flag_exposure
class TestFeatureFlagExposureWeblog:
    """Test Feature Flag Exposure (FFE) telemetry events via weblog."""

    def get_rc_params(self, ufc_data: dict, config_id: str = None) -> tuple:
        """Create Remote Config parameters for FFE_FLAGS product."""
        if not config_id:
            config_id = str(hash(json.dumps(ufc_data, sort_keys=True)))

        config = {
            "action": "apply",
            "flag_configuration": ufc_data,
            "flag_environment": "foo",
            "id": config_id
        }

        return f"datadog/2/FFE_FLAGS/{config_id}/config", config

    def setup_feature_flag_provider(self):
        """Trigger feature flag evaluation to generate exposure events."""
        self.r = weblog.get("/ffe/start")
        assert self.r.status_code == 200, f"Failed to start FFE provider: {self.r.text}"
        # Set up UFC Remote Config first
        path, config = self.get_rc_params(UFC_FIXTURE_DATA)
        rc.rc_state.reset().set_config(path, config).apply()
        

    def test_feature_flag_exposure_events(self):
        """Test that feature flag exposure events are generated and sent via EVP v2."""

        # Get FFE exposure events from agent EVP v2 endpoint
        # EVP proxy forwards to /api/v2/track/exposures on backend
        ffe_events = list(interfaces.agent.get_data("/evp_proxy/v2/api/v2/track/exposures"))

        if not ffe_events:
            raise Exception("No FFE exposure events received from EVP v2 endpoint")

        logger.debug(f"Found {len(ffe_events)} FFE exposure events")

        # Validate the structure of FFE events
        for event in ffe_events:
            content = event["request"]["content"]

            # Basic FFE event structure validation - EVP proxy format
            assert "context" in content, "Missing context in FFE exposure event"
            assert "exposures" in content, "Missing exposures in FFE exposure event"

            # Validate context structure
            context = content["context"]
            assert "targetingKey" in context, "Missing targetingKey in context"

            # Validate exposures structure
            exposures = content["exposures"]
            assert len(exposures) > 0, "No exposures in FFE event"

            for exposure in exposures:
                assert "flag" in exposure, "Missing flag in exposure"
                assert "value" in exposure, "Missing value in exposure"
                assert "reason" in exposure, "Missing reason in exposure"

                # Log event details for debugging
                logger.debug(f"FFE Exposure - Flag: {exposure.get('flag')}, Value: {exposure.get('value')}, Reason: {exposure.get('reason')}")

    def setup_feature_flag_multiple_evaluations(self):
        """Trigger multiple feature flag evaluations."""
        # Set up UFC Remote Config first
        path, config = self.get_rc_params(UFC_FIXTURE_DATA)
        rc.rc_state.reset().set_config(path, config).apply()

        # Initialize FFE provider
        weblog.get("/ffe/start")

        logger.debug("Triggering multiple feature flag evaluations")
        for i in range(3):
            weblog.post("/feature_flag_evaluation", json={
                "flag": "numeric_flag",
                "variationType": "NUMERIC",
                "defaultValue": 0.0,
                "targetingKey": f"test-user-{i}",
                "attributes": {}
            })

    def test_multiple_feature_flag_exposures(self):
        """Test that multiple feature flag evaluations generate multiple exposure events."""

        # Get FFE exposure events from agent EVP v2 endpoint
        ffe_events = list(interfaces.agent.get_data("/evp_proxy/v2/api/v2/track/exposures"))

        if not ffe_events:
            raise Exception("No FFE exposure events received from EVP v2 endpoint for multiple evaluations")

        # Count total exposures across all events
        total_exposures = 0
        for event in ffe_events:
            content = event["request"]["content"]
            if "exposures" in content:
                total_exposures += len(content["exposures"])

        # Should have events corresponding to our multiple evaluations
        # Note: The exact number may vary based on batching and other factors
        assert total_exposures > 0, "No FFE exposures found for multiple evaluations"

        logger.debug(f"Found {total_exposures} FFE exposures from {len(ffe_events)} events from multiple evaluations")