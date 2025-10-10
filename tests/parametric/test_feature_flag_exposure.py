"""Test Feature Flag Exposure (FFE) functionality via parametric tests."""

import json
import pytest
from pathlib import Path
from typing import Any

from utils import (
    features,
    scenarios,
)
from utils.dd_constants import RemoteConfigApplyState
from .conftest import _TestAgentAPI, APMLibrary

RC_PRODUCT = "FFE_FLAGS"
RC_PATH = f"datadog/2/{RC_PRODUCT}"

parametrize = pytest.mark.parametrize


# Load the UFC fixture file at module level
def _load_ufc_fixture() -> dict[str, Any]:
    """Load the UFC fixture file."""
    fixture_path = Path("tests/parametric/fixtures/test_data/flags-v1.json")

    if not fixture_path.exists():
        pytest.skip(f"Fixture file not found: {fixture_path}")

    with fixture_path.open() as f:
        ufc_payload = json.load(f)
    return ufc_payload["data"]["attributes"]


def _get_test_case_files() -> list[str]:
    """Get all test case files from the fixtures directory."""
    test_data_dir = Path("tests/parametric/fixtures/test_data/tests")
    if not test_data_dir.exists():
        return []

    return [f.name for f in test_data_dir.iterdir() if f.suffix == ".json"]


# Load fixture at module level for reuse across tests
UFC_FIXTURE_DATA = _load_ufc_fixture()
ALL_TEST_CASE_FILES = _get_test_case_files()

DEFAULT_ENVVARS = {
    "DD_EXPERIMENTAL_FLAGGING_PROVIDER_ENABLED": "true",
    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.2",
    "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.2",
}


def _set_and_wait_ffe_rc(
    test_agent: _TestAgentAPI, ufc_data: dict[str, Any], config_id: str | None = None
) -> dict[str, Any]:
    """Set FFE Remote Config and wait for it to be acknowledged.

    Args:
        test_agent: The test agent API instance
        ufc_data: The UFC (User Feature Configuration) data payload
        config_id: Optional config ID, will be generated from data hash if not provided

    Returns:
        The apply state response from the test agent

    """
    if not config_id:
        config_id = str(hash(json.dumps(ufc_data, sort_keys=True)))

    # Create RC config payload
    rc_config = {"action": "apply", "flag_configuration": ufc_data, "flag_environment": "foo", "id": config_id}

    # Set the config
    test_agent.set_remote_config(path=f"{RC_PATH}/{config_id}/config", payload=rc_config)

    # Wait for RC acknowledgment
    return test_agent.wait_for_rc_apply_state(RC_PRODUCT, state=RemoteConfigApplyState.ACKNOWLEDGED, clear=True)


@scenarios.parametric
@features.feature_flag_exposure
class Test_Feature_Flag_Exposure:
    """Test Feature Flag Exposure (FFE) functionality.

    This test suite focuses on FFE-specific behavior: flag evaluation logic,
    OpenFeature provider integration, and exposure event generation.

    """

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_ffe_remote_config(
        self, library_env: dict[str, str], test_agent: _TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Test to verify FFE can receive and acknowledge UFC configurations via Remote Config."""

        apply_state = _set_and_wait_ffe_rc(test_agent, UFC_FIXTURE_DATA)
        assert apply_state["apply_state"] == RemoteConfigApplyState.ACKNOWLEDGED.value
        assert apply_state["product"] == RC_PRODUCT

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @parametrize("test_case_file", ALL_TEST_CASE_FILES)
    def test_ffe_flag_evaluation(
        self, library_env: dict[str, str], test_case_file: str, test_agent: _TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Test FFE flag evaluation logic with various targeting scenarios.

        This is the core FFE test that validates the OpenFeature provider correctly:
        1. Loads flag configurations from Remote Config (UFC format)
        2. Evaluates flags based on targeting rules and evaluation context
        3. Returns correct variation values for different variation types
        4. Handles user targeting, attribute matching, and rollout percentages

        """
        # Load the test case file
        test_case_path = Path("tests/parametric/fixtures/test_data/tests") / test_case_file

        if not test_case_path.exists():
            pytest.skip(f"Test case file not found: {test_case_path}")

        with test_case_path.open() as f:
            test_cases = json.load(f)

        # Set up UFC Remote Config and wait for it to be applied
        _set_and_wait_ffe_rc(test_agent, UFC_FIXTURE_DATA)

        # Initialize FFE provider
        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        # Run each test case
        for i, test_case in enumerate(test_cases):
            flag = test_case["flag"]
            variation_type = test_case["variationType"]
            default_value = test_case["defaultValue"]
            targeting_key = test_case["targetingKey"]
            attributes = test_case.get("attributes", {})
            expected_result = test_case["result"]["value"]

            result = test_library.ffe_evaluate(
                flag=flag,
                variation_type=variation_type,
                default_value=default_value,
                targeting_key=targeting_key,
                attributes=attributes,
            )
            actual_value = result.get("value")

            # Assert the evaluation result matches expected value
            assert actual_value == expected_result, (
                f"Test case {i} in {test_case_file} failed: "
                f"flag='{flag}', targetingKey='{targeting_key}', "
                f"expected={expected_result}, actual={actual_value}"
            )
