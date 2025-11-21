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
from utils.docker_fixtures import TestAgentAPI
from tests.parametric.conftest import APMLibrary

RC_PRODUCT = "FFE_FLAGS"
RC_PATH = f"datadog/2/{RC_PRODUCT}"

parametrize = pytest.mark.parametrize


# Load the UFC fixture file at module level
def _load_ufc_fixture() -> dict[str, Any]:
    """Load the UFC fixture file."""
    fixture_path = Path(__file__).parent / "flags-v1.json"

    if not fixture_path.exists():
        pytest.skip(f"Fixture file not found: {fixture_path}")

    with fixture_path.open() as f:
        return json.load(f)


def _get_test_case_files() -> list[str]:
    """Get all test case files from the fixtures directory."""
    test_data_dir = Path(__file__).parent
    if not test_data_dir.exists():
        return []

    return [f.name for f in test_data_dir.iterdir() if f.suffix == ".json" and f.name != "flags-v1.json"]


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
@features.feature_flag_exposure
class Test_Feature_Flag_Exposure:
    """Test Feature Flag Exposure (FFE) functionality.

    This test suite focuses on FFE-specific behavior: flag evaluation logic,
    OpenFeature provider integration, and exposure event generation.

    """

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_ffe_remote_config(
        self, library_env: dict[str, str], test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Test to verify FFE can receive and acknowledge UFC configurations via Remote Config."""

        apply_state = _set_and_wait_ffe_rc(test_agent, UFC_FIXTURE_DATA)
        assert apply_state["apply_state"] == RemoteConfigApplyState.ACKNOWLEDGED.value
        assert apply_state["product"] == RC_PRODUCT

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @parametrize("test_case_file", ALL_TEST_CASE_FILES)
    def test_ffe_flag_evaluation(
        self, library_env: dict[str, str], test_case_file: str, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Test FFE flag evaluation logic with various targeting scenarios.

        This is the core FFE test that validates the OpenFeature provider correctly:
        1. Loads flag configurations from Remote Config (UFC format)
        2. Evaluates flags based on targeting rules and evaluation context
        3. Returns correct variation values for different variation types
        4. Handles user targeting, attribute matching, and rollout percentages

        """
        # Load the test case file
        test_case_path = Path(__file__).parent / test_case_file

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
    @parametrize("test_case_file", ALL_TEST_CASE_FILES)
    def test_ffe_agent_empty_response_resilience(
        self, library_env: dict[str, str], test_case_file: str, test_agent: _TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Test FFE resilience when agent returns empty responses.

        This test verifies that when the agent returns empty responses,
        FFE continues to work with cached configuration data.
        """
        from utils._context._scenarios.ffe_agent_empty_response import ffe_agent_empty_response

        # Load test case data
        test_case_path = Path(__file__).parent / test_case_file
        if not test_case_path.exists():
            pytest.skip(f"Test case file not found: {test_case_path}")

        with test_case_path.open() as f:
            test_cases = json.load(f)

        # Setup FFE provider and set initial RC config
        _set_and_wait_ffe_rc(test_agent, UFC_FIXTURE_DATA)
        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        # Run happy path evaluations first
        happy_results = []
        for test_case in test_cases:
            result = test_library.ffe_evaluate(
                flag=test_case["flag"],
                variation_type=test_case["variationType"],
                default_value=test_case["defaultValue"],
                targeting_key=test_case["targetingKey"],
                attributes=test_case.get("attributes", {}),
            )
            happy_results.append(result)

            # Verify happy path result
            expected = test_case["result"]["value"]
            actual = result.get("value")
            assert actual == expected, f"Happy path failed for flag {test_case['flag']}"

        # Configure agent to return empty responses
        ffe_agent_empty_response.configure_agent_empty_responses(test_agent)

        # Run evaluations during agent failure - should use cached values
        for i, test_case in enumerate(test_cases):
            result = test_library.ffe_evaluate(
                flag=test_case["flag"],
                variation_type=test_case["variationType"],
                default_value=test_case["defaultValue"],
                targeting_key=test_case["targetingKey"],
                attributes=test_case.get("attributes", {}),
            )

            # During failure, should return same values as happy path
            expected = happy_results[i]["value"]
            actual = result.get("value")
            assert actual == expected, f"Resilience failed for flag {test_case['flag']}"

        # Restore normal responses
        ffe_agent_empty_response.restore_agent_normal_responses(test_agent)

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @parametrize("test_case_file", ALL_TEST_CASE_FILES)
    def test_ffe_agent_5xx_error_resilience(
        self, library_env: dict[str, str], test_case_file: str, test_agent: _TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Test FFE resilience when agent returns 5xx server errors."""
        from utils._context._scenarios.ffe_agent_5xx_error import ffe_agent_5xx_error

        # Load test case data
        test_case_path = Path(__file__).parent / test_case_file
        if not test_case_path.exists():
            pytest.skip(f"Test case file not found: {test_case_path}")

        with test_case_path.open() as f:
            test_cases = json.load(f)

        # Setup and run happy path
        _set_and_wait_ffe_rc(test_agent, UFC_FIXTURE_DATA)
        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        happy_results = []
        for test_case in test_cases:
            result = test_library.ffe_evaluate(
                flag=test_case["flag"],
                variation_type=test_case["variationType"],
                default_value=test_case["defaultValue"],
                targeting_key=test_case["targetingKey"],
                attributes=test_case.get("attributes", {}),
            )
            happy_results.append(result)

        # Configure agent to return 5xx errors
        ffe_agent_5xx_error.configure_agent_5xx_responses(test_agent)

        # Test resilience during 5xx errors
        for i, test_case in enumerate(test_cases):
            result = test_library.ffe_evaluate(
                flag=test_case["flag"],
                variation_type=test_case["variationType"],
                default_value=test_case["defaultValue"],
                targeting_key=test_case["targetingKey"],
                attributes=test_case.get("attributes", {}),
            )

            expected = happy_results[i]["value"]
            actual = result.get("value")
            assert actual == expected, f"Resilience failed for flag {test_case['flag']}"

        # Restore normal responses
        ffe_agent_5xx_error.restore_agent_normal_responses(test_agent)

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @parametrize("test_case_file", ALL_TEST_CASE_FILES)
    def test_ffe_agent_timeout_resilience(
        self, library_env: dict[str, str], test_case_file: str, test_agent: _TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Test FFE resilience when agent requests time out."""
        from utils._context._scenarios.ffe_agent_timeout import ffe_agent_timeout

        # Load test case data
        test_case_path = Path(__file__).parent / test_case_file
        if not test_case_path.exists():
            pytest.skip(f"Test case file not found: {test_case_path}")

        with test_case_path.open() as f:
            test_cases = json.load(f)

        # Setup and run happy path
        _set_and_wait_ffe_rc(test_agent, UFC_FIXTURE_DATA)
        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        happy_results = []
        for test_case in test_cases:
            result = test_library.ffe_evaluate(
                flag=test_case["flag"],
                variation_type=test_case["variationType"],
                default_value=test_case["defaultValue"],
                targeting_key=test_case["targetingKey"],
                attributes=test_case.get("attributes", {}),
            )
            happy_results.append(result)

        # Configure agent timeouts
        ffe_agent_timeout.configure_agent_timeouts(test_agent)

        # Test resilience during timeouts
        for i, test_case in enumerate(test_cases):
            result = test_library.ffe_evaluate(
                flag=test_case["flag"],
                variation_type=test_case["variationType"],
                default_value=test_case["defaultValue"],
                targeting_key=test_case["targetingKey"],
                attributes=test_case.get("attributes", {}),
            )

            expected = happy_results[i]["value"]
            actual = result.get("value")
            assert actual == expected, f"Resilience failed for flag {test_case['flag']}"

        # Restore normal timing
        ffe_agent_timeout.restore_agent_normal_timing(test_agent)

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @parametrize("test_case_file", ALL_TEST_CASE_FILES)
    def test_ffe_agent_connection_refused_resilience(
        self, library_env: dict[str, str], test_case_file: str, test_agent: _TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Test FFE resilience when agent connection is refused."""
        from utils._context._scenarios.ffe_agent_connection_refused import ffe_agent_connection_refused

        # Load test case data
        test_case_path = Path(__file__).parent / test_case_file
        if not test_case_path.exists():
            pytest.skip(f"Test case file not found: {test_case_path}")

        with test_case_path.open() as f:
            test_cases = json.load(f)

        # Setup and run happy path
        _set_and_wait_ffe_rc(test_agent, UFC_FIXTURE_DATA)
        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        happy_results = []
        for test_case in test_cases:
            result = test_library.ffe_evaluate(
                flag=test_case["flag"],
                variation_type=test_case["variationType"],
                default_value=test_case["defaultValue"],
                targeting_key=test_case["targetingKey"],
                attributes=test_case.get("attributes", {}),
            )
            happy_results.append(result)

        # Stop agent container
        ffe_agent_connection_refused.stop_agent_container(test_agent)

        # Test resilience during connection refused
        for i, test_case in enumerate(test_cases):
            result = test_library.ffe_evaluate(
                flag=test_case["flag"],
                variation_type=test_case["variationType"],
                default_value=test_case["defaultValue"],
                targeting_key=test_case["targetingKey"],
                attributes=test_case.get("attributes", {}),
            )

            expected = happy_results[i]["value"]
            actual = result.get("value")
            assert actual == expected, f"Resilience failed for flag {test_case['flag']}"

        # Restart agent container
        ffe_agent_connection_refused.restart_agent_container(test_agent)

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @parametrize("test_case_file", ALL_TEST_CASE_FILES)
    def test_ffe_rc_endpoint_error_resilience(
        self, library_env: dict[str, str], test_case_file: str, test_agent: _TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Test FFE resilience when Remote Config endpoint returns errors."""
        from utils._context._scenarios.ffe_rc_endpoint_error import ffe_rc_endpoint_error

        # Load test case data
        test_case_path = Path(__file__).parent / test_case_file
        if not test_case_path.exists():
            pytest.skip(f"Test case file not found: {test_case_path}")

        with test_case_path.open() as f:
            test_cases = json.load(f)

        # Setup and run happy path
        _set_and_wait_ffe_rc(test_agent, UFC_FIXTURE_DATA)
        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        happy_results = []
        for test_case in test_cases:
            result = test_library.ffe_evaluate(
                flag=test_case["flag"],
                variation_type=test_case["variationType"],
                default_value=test_case["defaultValue"],
                targeting_key=test_case["targetingKey"],
                attributes=test_case.get("attributes", {}),
            )
            happy_results.append(result)

        # Configure RC endpoint errors
        ffe_rc_endpoint_error.configure_rc_endpoint_errors(test_agent)

        # Test resilience during RC errors
        for i, test_case in enumerate(test_cases):
            result = test_library.ffe_evaluate(
                flag=test_case["flag"],
                variation_type=test_case["variationType"],
                default_value=test_case["defaultValue"],
                targeting_key=test_case["targetingKey"],
                attributes=test_case.get("attributes", {}),
            )

            expected = happy_results[i]["value"]
            actual = result.get("value")
            assert actual == expected, f"Resilience failed for flag {test_case['flag']}"

        # Restore normal RC responses
        ffe_rc_endpoint_error.restore_rc_normal_responses(test_agent)

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @parametrize("test_case_file", ALL_TEST_CASE_FILES)
    def test_ffe_rc_network_delay_resilience(
        self, library_env: dict[str, str], test_case_file: str, test_agent: _TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Test FFE resilience when Remote Config requests are delayed."""
        from utils._context._scenarios.ffe_rc_network_delay import ffe_rc_network_delay

        # Load test case data
        test_case_path = Path(__file__).parent / test_case_file
        if not test_case_path.exists():
            pytest.skip(f"Test case file not found: {test_case_path}")

        with test_case_path.open() as f:
            test_cases = json.load(f)

        # Setup and run happy path
        _set_and_wait_ffe_rc(test_agent, UFC_FIXTURE_DATA)
        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        happy_results = []
        for test_case in test_cases:
            result = test_library.ffe_evaluate(
                flag=test_case["flag"],
                variation_type=test_case["variationType"],
                default_value=test_case["defaultValue"],
                targeting_key=test_case["targetingKey"],
                attributes=test_case.get("attributes", {}),
            )
            happy_results.append(result)

        # Configure RC network delays
        ffe_rc_network_delay.configure_rc_network_delays(test_agent)

        # Test resilience during network delays
        for i, test_case in enumerate(test_cases):
            result = test_library.ffe_evaluate(
                flag=test_case["flag"],
                variation_type=test_case["variationType"],
                default_value=test_case["defaultValue"],
                targeting_key=test_case["targetingKey"],
                attributes=test_case.get("attributes", {}),
            )

            expected = happy_results[i]["value"]
            actual = result.get("value")
            assert actual == expected, f"Resilience failed for flag {test_case['flag']}"

        # Restore normal RC timing
        ffe_rc_network_delay.restore_rc_normal_timing(test_agent)

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @parametrize("test_case_file", ALL_TEST_CASE_FILES)
    def test_ffe_rc_empty_config_resilience(
        self, library_env: dict[str, str], test_case_file: str, test_agent: _TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Test FFE resilience when Remote Config returns empty configuration."""
        from utils._context._scenarios.ffe_rc_empty_config import ffe_rc_empty_config

        # Load test case data
        test_case_path = Path(__file__).parent / test_case_file
        if not test_case_path.exists():
            pytest.skip(f"Test case file not found: {test_case_path}")

        with test_case_path.open() as f:
            test_cases = json.load(f)

        # Setup and run happy path
        _set_and_wait_ffe_rc(test_agent, UFC_FIXTURE_DATA)
        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        happy_results = []
        for test_case in test_cases:
            result = test_library.ffe_evaluate(
                flag=test_case["flag"],
                variation_type=test_case["variationType"],
                default_value=test_case["defaultValue"],
                targeting_key=test_case["targetingKey"],
                attributes=test_case.get("attributes", {}),
            )
            happy_results.append(result)

        # Configure empty RC config
        empty_config = ffe_rc_empty_config.configure_empty_rc_config(test_agent)
        _set_and_wait_ffe_rc(test_agent, empty_config)

        # Test resilience with empty config - should fallback to cached values
        for i, test_case in enumerate(test_cases):
            result = test_library.ffe_evaluate(
                flag=test_case["flag"],
                variation_type=test_case["variationType"],
                default_value=test_case["defaultValue"],
                targeting_key=test_case["targetingKey"],
                attributes=test_case.get("attributes", {}),
            )

            expected = happy_results[i]["value"]
            actual = result.get("value")
            assert actual == expected, f"Resilience failed for flag {test_case['flag']}"

        # Restore normal config
        _set_and_wait_ffe_rc(test_agent, UFC_FIXTURE_DATA)

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @parametrize("test_case_file", ALL_TEST_CASE_FILES)
    def test_ffe_rc_malformed_response_resilience(
        self, library_env: dict[str, str], test_case_file: str, test_agent: _TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Test FFE resilience when Remote Config returns malformed data."""
        from utils._context._scenarios.ffe_rc_malformed_response import ffe_rc_malformed_response

        # Load test case data
        test_case_path = Path(__file__).parent / test_case_file
        if not test_case_path.exists():
            pytest.skip(f"Test case file not found: {test_case_path}")

        with test_case_path.open() as f:
            test_cases = json.load(f)

        # Setup and run happy path
        _set_and_wait_ffe_rc(test_agent, UFC_FIXTURE_DATA)
        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        happy_results = []
        for test_case in test_cases:
            result = test_library.ffe_evaluate(
                flag=test_case["flag"],
                variation_type=test_case["variationType"],
                default_value=test_case["defaultValue"],
                targeting_key=test_case["targetingKey"],
                attributes=test_case.get("attributes", {}),
            )
            happy_results.append(result)

        # Configure malformed RC config
        malformed_config = ffe_rc_malformed_response.create_malformed_rc_config()
        try:
            _set_and_wait_ffe_rc(test_agent, malformed_config)
        except Exception:
            # Expected to fail with malformed data, continue with cached config
            pass

        # Test resilience with malformed config - should use cached values
        for i, test_case in enumerate(test_cases):
            result = test_library.ffe_evaluate(
                flag=test_case["flag"],
                variation_type=test_case["variationType"],
                default_value=test_case["defaultValue"],
                targeting_key=test_case["targetingKey"],
                attributes=test_case.get("attributes", {}),
            )

            expected = happy_results[i]["value"]
            actual = result.get("value")
            assert actual == expected, f"Resilience failed for flag {test_case['flag']}"

        # Restore normal config
        _set_and_wait_ffe_rc(test_agent, UFC_FIXTURE_DATA)
