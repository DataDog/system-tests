"""Test Feature Flag Exposure (FFE) exposure events in weblog end-to-end scenario."""

import json
from pathlib import Path

from utils import (
    weblog,
    interfaces,
    scenarios,
    features,
    remote_config as rc,
)


RC_PRODUCT = "FFE_FLAGS"
RC_PATH = f"datadog/2/{RC_PRODUCT}"


def _load_ufc_fixture():
    """Load the UFC fixture file."""
    fixture_path = Path("tests/parametric/fixtures/test_data/flags-v1.json")
    with fixture_path.open() as f:
        ufc_payload = json.load(f)
    return ufc_payload["data"]["attributes"]


UFC_FIXTURE_DATA = _load_ufc_fixture()


@scenarios.default
@features.feature_flag_exposure
class Test_FFE_Exposure_Events:
    """Test FFE exposure events in end-to-end weblog scenario."""

    def setup_remote_config(self):
        """Set up FFE Remote Config."""
        config_id = "ffe-test-config"
        rc_config = {
            "action": "apply",
            "flag_configuration": UFC_FIXTURE_DATA,
            "flag_environment": "test",
            "id": config_id,
        }
        rc.send_command(path=f"{RC_PATH}/{config_id}/config", config=rc_config)

    def test_ffe_exposure_event_generation(self):
        """Test that FFE generates exposure events when flags are evaluated via weblog."""

        # Start FFE provider first
        response = weblog.post("/ffe/start", json={})
        assert response.status_code == 200, f"Failed to start FFE provider: {response.text}"

        # Set up Remote Config after provider is initialized
        self.setup_remote_config()

        # Use a simple test case
        flag = "new-user-onboarding"
        variation_type = "STRING"
        default_value = "default"
        targeting_key = "alice"
        attributes = {"email": "alice@mycompany.com", "country": "US"}

        eval_response = weblog.post(
            "/ffe/evaluate",
            json={
                "flag": flag,
                "variationType": variation_type,
                "defaultValue": default_value,
                "targetingKey": targeting_key,
                "attributes": attributes,
            },
        )
        assert eval_response.status_code == 200, f"Flag evaluation failed: {eval_response.text}"

        # Wait for exposure events to be sent to agent
        def validator(data):
            """Validate exposure events were sent."""
            if data["path"] == "/evp_proxy/v2/api/v2/exposures":
                body = json.loads(data["body"])

                # The payload structure is: {"context": {...}, "exposures": [...]}
                assert "exposures" in body, "Response missing 'exposures' field"
                assert isinstance(body["exposures"], list), "Exposures should be a list"
                assert len(body["exposures"]) > 0, "Expected at least one exposure event"

                # Validate structure of first exposure event
                event = body["exposures"][0]
                assert "flag" in event, "Exposure event missing 'flag' field"
                assert "key" in event["flag"], "Flag missing 'key' field"
                assert event["flag"]["key"] == flag, f"Expected flag '{flag}', got '{event['flag']['key']}'"

                # Validate subject matches targeting key
                assert "subject" in event, "Exposure event missing 'subject' field"
                assert event["subject"]["id"] == targeting_key, f"Expected subject '{targeting_key}', got '{event['subject']['id']}'"

                return True
            return False

        interfaces.agent.wait_for(validator, timeout=30)
