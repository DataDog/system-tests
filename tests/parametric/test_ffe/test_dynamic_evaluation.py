"""Test FFE (Feature Flags & Experimentation) functionality via parametric tests."""

import json
import pytest
from pathlib import Path
from typing import Any

from utils import (
    context,
    features,
    scenarios,
)
from utils.dd_constants import RemoteConfigApplyState
from utils.docker_fixtures import TestAgentAPI
from tests.parametric.conftest import APMLibrary

RC_PRODUCT = "FFE_FLAGS"
RC_PATH = f"datadog/2/{RC_PRODUCT}"

parametrize = pytest.mark.parametrize


# Load the UFC fixture file at module level
def _load_ufc_fixture() -> dict[str, Any]:
    """Load the UFC fixture file."""
    fixture_path = Path(__file__).parent / "ffe-data/config/ufc-config.json"

    if not fixture_path.exists():
        pytest.skip(f"Fixture file not found: {fixture_path}")

    with fixture_path.open() as f:
        return json.load(f)


def _get_test_case_files() -> list[str]:
    """Get all test case files from the fixtures directory."""
    test_data_dir = Path(__file__).parent / "ffe-data/evaluation-cases"
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
    test_agent: TestAgentAPI, ufc_data: dict[str, Any], config_id: str | None = None
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
    rc_config = ufc_data

    # Set the config
    test_agent.set_remote_config(path=f"{RC_PATH}/{config_id}/config", payload=rc_config)

    # Wait for RC acknowledgment
    return test_agent.wait_for_rc_apply_state(RC_PRODUCT, state=RemoteConfigApplyState.ACKNOWLEDGED, clear=True)


@scenarios.parametric
@features.feature_flags_dynamic_evaluation
class Test_Feature_Flag_Dynamic_Evaluation:
    """Test Feature Flagging dynamic evaluation functionality.

    This test suite focuses on flag evaluation logic.

    """

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_ffe_remote_config(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Test to verify FFE can receive and acknowledge UFC configurations via Remote Config."""

        assert test_library.is_alive(), "library container is not alive"
        apply_state = _set_and_wait_ffe_rc(test_agent, UFC_FIXTURE_DATA)
        assert apply_state["apply_state"] == RemoteConfigApplyState.ACKNOWLEDGED.value
        assert apply_state["product"] == RC_PRODUCT

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @parametrize("test_case_file", ALL_TEST_CASE_FILES)
    def test_ffe_flag_evaluation(self, test_case_file: str, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Test FFE flag evaluation logic with various targeting scenarios.

        This is the core FFE test that validates the OpenFeature provider correctly:
        1. Loads flag configurations from Remote Config (UFC format)
        2. Evaluates flags based on targeting rules and evaluation context
        3. Returns correct variation values for different variation types
        4. Handles user targeting, attribute matching, and rollout percentages

        """
        # Skip OF.7 (empty targeting key) test for libraries with known bugs
        # Java: FFL-1729 - OpenFeature Java SDK rejects empty targeting keys
        # Node.js: FFL-1730 - OpenFeature JS SDK rejects empty targeting keys
        if test_case_file == "test-case-of-7-empty-targeting-key.json":
            if context.library.name in ("java", "nodejs"):
                pytest.skip("OF.7 empty targeting key bug: FFL-1729 (java), FFL-1730 (nodejs)")

        # Load the test case file
        test_case_path = Path(__file__).parent / "ffe-data/evaluation-cases" / test_case_file

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

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_ffe_of7_empty_targeting_key(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """OF.7: Empty string is a valid targeting key.

        This test validates that flag evaluation succeeds when the targeting key
        is an empty string. The flag should still match allocations and return
        the expected value, not fail with TARGETING_KEY_MISSING.

        Temporary dedicated test until FFL-1729 (Java) and FFL-1730 (Node.js) are resolved.
        """
        # Set up UFC Remote Config and wait for it to be applied
        _set_and_wait_ffe_rc(test_agent, UFC_FIXTURE_DATA)

        # Initialize FFE provider
        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        # Evaluate flag with empty targeting key
        result = test_library.ffe_evaluate(
            flag="empty-targeting-key-flag",
            variation_type="STRING",
            default_value="default",
            targeting_key="",
            attributes={},
        )

        assert result.get("value") == "on-value", (
            f"OF.7 failed: empty targeting key should return 'on-value', got '{result.get('value')}'"
        )
