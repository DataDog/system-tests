"""Test Feature Flag Exposure (FFE) functionality via parametric tests."""

import json
import os
import pytest
from typing import Any, Dict, List

from utils import (
    features,
    scenarios,
)
from utils.dd_constants import Capabilities, RemoteConfigApplyState
from .conftest import _TestAgentAPI, APMLibrary

RC_PRODUCT = "FFE_FLAGS"
RC_PATH = f"datadog/2/{RC_PRODUCT}"

parametrize = pytest.mark.parametrize

# Load the UFC fixture file at module level
def _load_ufc_fixture() -> Dict[str, Any]:
    """Load the UFC fixture file."""
    fixture_path = os.path.join("tests/parametric/fixtures/test_data", "flags-v1.json")

    if not os.path.exists(fixture_path):
        pytest.skip(f"Fixture file not found: {fixture_path}")

    with open(fixture_path) as f:
        ufc_payload = json.load(f)
    return ufc_payload["data"]['attributes']

def _get_test_case_files() -> List[str]:
    """Get all test case files from the fixtures directory."""
    test_data_dir = os.path.join("tests/parametric/fixtures/test_data/tests")
    if not os.path.exists(test_data_dir):
        return []

    return [f for f in os.listdir(test_data_dir) if f.endswith('.json')]

# Load fixture at module level for reuse across tests
UFC_FIXTURE_DATA = _load_ufc_fixture()
ALL_TEST_CASE_FILES = _get_test_case_files()

DEFAULT_ENVVARS = {
    "DD_FLAGGING_PROVIDER_ENABLED": "true",
    "_DD_FFE_FLUSH_INTERVAL": "1000",
    "_DD_FFE_TIMEOUT": "5000",
    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.2",
    "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.2",
}


def _create_ffe_rc_config(ufc_data: Dict[str, Any], config_id: str = None) -> Dict[str, Any]:
    """Create a Remote Config payload for UFC (User Feature Configuration)."""
    if not config_id:
        config_id = str(hash(json.dumps(ufc_data, sort_keys=True)))

    config = { 
        "action": "apply",
        "flag_configuration": ufc_data,
        "flag_environment": "foo",

    }
    config["id"] = config_id
    return config


def _set_ffe_rc(test_agent: _TestAgentAPI, ufc_data: Dict[str, Any], config_id: str = None) -> str:
    """Set FFE Remote Config and return the config ID."""
    if not config_id:
        config_id = str(hash(json.dumps(ufc_data, sort_keys=True)))

    rc_config = _create_ffe_rc_config(ufc_data, config_id)
    test_agent.set_remote_config(
        path=f"{RC_PATH}/{config_id}/config",
        payload=rc_config
    )
    return config_id


def _wait_for_ffe_rc_applied(test_agent: _TestAgentAPI) -> Dict[str, Any]:
    """Wait for FFE Remote Config to be acknowledged."""
    # Wait for RC acknowledgment
    return test_agent.wait_for_rc_apply_state(
        RC_PRODUCT,
        state=RemoteConfigApplyState.ACKNOWLEDGED,
        clear=True
    )


@scenarios.parametric
@features.feature_flag_exposure
class TestFeatureFlagExposure:
    """Test Feature Flag Exposure (FFE) functionality."""

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_ffe_capability_registration(self, library_env, test_agent: _TestAgentAPI, test_library: APMLibrary):
        """Ensure FFE capabilities are registered with Remote Config."""
        # Check for FFE-related capabilities
        capabilities = test_agent.wait_for_rc_capabilities()

        # Verify UFC capability is present
        expected_capabilities = {Capabilities.FFE_FLAG_CONFIGURATION_RULES}  # Assuming this exists
        assert expected_capabilities.issubset(capabilities), \
            f"Missing FFE capabilities: {expected_capabilities - capabilities}"

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_ffe_remote_config_integration(self, library_env, test_agent: _TestAgentAPI, test_library: APMLibrary):
        """Test basic FFE Remote Config integration."""
        # Use the pre-loaded UFC fixture data
        config_id = _set_ffe_rc(test_agent, UFC_FIXTURE_DATA)

        # Wait for configuration to be applied
        apply_state = _wait_for_ffe_rc_applied(test_agent)
        assert apply_state["apply_state"] == RemoteConfigApplyState.ACKNOWLEDGED.value
        assert apply_state["product"] == RC_PRODUCT


    @parametrize("library_env", [{**DEFAULT_ENVVARS, "DD_FFE_ENABLED": "false"}])
    def test_ffe_disabled(self, library_env, test_agent: _TestAgentAPI, test_library: APMLibrary):
        """Test that FFE functionality is properly disabled when DD_FFE_ENABLED=false."""
        # When FFE is disabled, no UFC capabilities should be registered
        capabilities = test_agent.wait_for_rc_capabilities()

        # Verify UFC capability is NOT present
        ufc_capabilities = {cap for cap in capabilities if RC_PRODUCT in cap.name}
        assert len(ufc_capabilities) == 0, f"UFC capabilities found when FFE disabled: {ufc_capabilities}"

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @parametrize("test_case_file", ALL_TEST_CASE_FILES)
    def test_ffe_evaluation_with_test_cases(self, library_env, test_case_file, test_agent: _TestAgentAPI, test_library: APMLibrary):
        """Test FFE evaluation using test case files."""
        # Load the test case file
        test_case_path = os.path.join("tests/parametric/fixtures/test_data/tests", test_case_file)

        if not os.path.exists(test_case_path):
            pytest.skip(f"Test case file not found: {test_case_path}")

        with open(test_case_path) as f:
            test_cases = json.load(f)

        # Set up UFC Remote Config first
        _set_ffe_rc(test_agent, UFC_FIXTURE_DATA)
        _wait_for_ffe_rc_applied(test_agent)

        # Initialize FFE provider
        response = test_library._client._session.post(test_library._client._url("/ffe/start"), json={})
        assert response.status_code == 200, f"Failed to start FFE provider: {response.text}"

        # Run each test case
        for i, test_case in enumerate(test_cases):
            flag = test_case["flag"]
            variation_type = test_case["variationType"]
            default_value = test_case["defaultValue"]
            targeting_key = test_case["targetingKey"]
            attributes = test_case.get("attributes", {})
            expected_result = test_case["result"]["value"]

            # Call the FFE evaluation endpoint
            evaluation_request = {
                "flag": flag,
                "variationType": variation_type,
                "defaultValue": default_value,
                "targetingKey": targeting_key,
                "attributes": attributes
            }

            response = test_library._client._session.post(test_library._client._url("/ffe/evaluate"), json=evaluation_request)
            assert response.status_code == 200, f"FFE evaluation failed for test case {i} in {test_case_file}: {response.text}"

            result = response.json()
            actual_value = result.get("value")

            # Assert the evaluation result matches expected value
            assert actual_value == expected_result, (
                f"Test case {i} in {test_case_file} failed: "
                f"flag='{flag}', targetingKey='{targeting_key}', "
                f"expected={expected_result}, actual={actual_value}"
            )
