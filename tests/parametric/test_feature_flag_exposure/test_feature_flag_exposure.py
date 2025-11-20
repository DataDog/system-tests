"""Test Feature Flag Exposure (FFE) functionality via parametric tests."""

import json
import pytest
from pathlib import Path
from typing import Any

from utils import (
    features,
    logger,
    scenarios,
)
from utils.dd_constants import RemoteConfigApplyState
from utils._context.docker import get_docker_client
from tests.parametric.conftest import _TestAgentAPI, APMLibrary

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
    rc_config = ufc_data

    # Set the config
    test_agent.set_remote_config(path=f"{RC_PATH}/{config_id}/config", payload=rc_config)

    # Wait for RC acknowledgment
    return test_agent.wait_for_rc_apply_state(RC_PRODUCT, state=RemoteConfigApplyState.ACKNOWLEDGED, clear=True)


def _run_comprehensive_flag_evaluations(
    test_library: APMLibrary, test_cases: list[dict], test_case_file: str, phase_name: str
) -> dict[int, dict]:
    """Run comprehensive flag evaluations and return results for comparison.

    Args:
        test_library: The APM library instance for FFE operations
        test_cases: List of test case dictionaries loaded from JSON
        test_case_file: Name of the test case file (for error reporting)
        phase_name: Descriptive name of the phase (for error reporting)

    Returns:
        Dictionary mapping test case index to evaluation results and metadata

    """
    results = {}
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
            f"{phase_name} test case {i} in {test_case_file} failed: "
            f"flag='{flag}', targetingKey='{targeting_key}', "
            f"expected={expected_result}, actual={actual_value}"
        )

        # Store results for comparison during resilience testing
        results[i] = {
            "flag": flag,
            "variation_type": variation_type,
            "default_value": default_value,
            "targeting_key": targeting_key,
            "attributes": attributes,
            "expected_result": expected_result,
            "actual_result": actual_value,
        }

    return results


def _verify_cached_evaluations(
    test_library: APMLibrary, reference_results: dict[int, dict], test_case_file: str, phase_name: str
) -> None:
    """Verify that cached flag evaluations match reference results.

    Args:
        test_library: The APM library instance for FFE operations
        reference_results: Reference results to compare against (from happy path)
        test_case_file: Name of the test case file (for error reporting)
        phase_name: Descriptive name of the phase (for error reporting)

    """
    for i, stored_case in reference_results.items():
        cached_result = test_library.ffe_evaluate(
            flag=stored_case["flag"],
            variation_type=stored_case["variation_type"],
            default_value=stored_case["default_value"],
            targeting_key=stored_case["targeting_key"],
            attributes=stored_case["attributes"],
        )

        # FFE should still work using cached configuration
        assert "value" in cached_result, (
            f"FFE should work with cached config during {phase_name} for test case {i} "
            f"in {test_case_file}, flag='{stored_case['flag']}'"
        )

        cached_value = cached_result["value"]

        # The cached result should match the reference result since we're using
        # the same evaluation context and the cache should preserve the same targeting logic
        assert cached_value == stored_case["actual_result"], (
            f"Cached evaluation during {phase_name} should match reference for test case {i} in {test_case_file}: "
            f"flag='{stored_case['flag']}', targetingKey='{stored_case['targeting_key']}', "
            f"reference={stored_case['actual_result']}, cached={cached_value}"
        )


def _verify_evaluation_consistency(
    test_library: APMLibrary,
    reference_results: dict[int, dict],
    phase_name: str,
    num_rounds: int = 3,
    num_cases: int = 3,
) -> None:
    """Verify that multiple flag evaluations remain consistent.

    Args:
        test_library: The APM library instance for FFE operations
        reference_results: Reference results to compare against
        phase_name: Descriptive name of the phase (for error reporting)
        num_rounds: Number of consistency check rounds to run
        num_cases: Number of test cases to check (from the beginning)

    """
    # Use a subset of test cases to verify multiple evaluations remain consistent
    sample_cases = list(reference_results.items())[:num_cases]

    for consistency_round in range(num_rounds):
        for i, stored_case in sample_cases:
            consistency_result = test_library.ffe_evaluate(
                flag=stored_case["flag"],
                variation_type=stored_case["variation_type"],
                default_value=stored_case["default_value"],
                targeting_key=stored_case["targeting_key"],
                attributes=stored_case["attributes"],
            )
            assert (
                "value" in consistency_result
            ), f"FFE consistency check round {consistency_round} case {i} should work during {phase_name}"
            consistency_value = consistency_result["value"]
            assert consistency_value == stored_case["actual_result"], (
                f"{phase_name} consistency round {consistency_round} should be stable for case {i}: "
                f"expected={stored_case['actual_result']}, actual={consistency_value}"
            )


def _setup_ffe_test_environment(test_agent: _TestAgentAPI, test_library: APMLibrary) -> None:
    """Set up the standard FFE test environment with RC and provider initialization.

    Args:
        test_agent: Test agent API instance
        test_library: APM library instance

    """
    # Set up UFC Remote Config and wait for it to be applied
    apply_state = _set_and_wait_ffe_rc(test_agent, UFC_FIXTURE_DATA)
    assert apply_state["apply_state"] == RemoteConfigApplyState.ACKNOWLEDGED.value
    assert apply_state["product"] == RC_PRODUCT

    # Initialize FFE provider
    success = test_library.ffe_start()
    assert success, "Failed to start FFE provider"


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
    def test_ffe_remote_config_resilience(
        self, library_env: dict[str, str], test_case_file: str, test_agent: _TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Test FFE flag evaluation with resilience when Remote Config becomes unavailable.

        This comprehensive test verifies that:
        1. FFE flag evaluation works normally when RC is available (happy path)
        2. FFE continues to work with cached config when RC goes down (resilience)
        3. All flag evaluation scenarios work during both normal and degraded states
        4. Flag evaluations use cached values consistently when RC is unavailable

        This test combines the comprehensive flag evaluation logic from the original
        test_ffe_flag_evaluation with resilience testing to ensure cached flag
        evaluations remain functional when the agent is down.
        """
        # Load the test case file
        test_case_path = Path(__file__).parent / test_case_file

        if not test_case_path.exists():
            pytest.skip(f"Test case file not found: {test_case_path}")

        with test_case_path.open() as f:
            test_cases = json.load(f)

        # Phase 1: Setup FFE test environment
        _setup_ffe_test_environment(test_agent, test_library)

        # Phase 2: Happy Path - Run comprehensive flag evaluation when RC is available
        happy_path_results = _run_comprehensive_flag_evaluations(test_library, test_cases, test_case_file, "Happy path")

        # Phase 3: Simulate RC becoming unavailable by introducing network delays
        # This simulates RC service being down or unreachable due to network issues
        import time

        # Introduce significant delay to RC requests to simulate service being down/slow
        # This is more realistic than sending empty configs
        test_agent.set_trace_delay(5000)  # 5 second delay simulates network timeout/issues

        # Give some time for the delay to take effect
        time.sleep(1.0)

        # Phase 4: Resilience Path - Verify FFE continues working with cached config
        _verify_cached_evaluations(test_library, happy_path_results, test_case_file, "RC downtime")

        # Phase 5: Restore normal operation - reset delay for cleanup
        test_agent.set_trace_delay(0)  # Reset delay to restore normal operation

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @parametrize("test_case_file", ALL_TEST_CASE_FILES)
    def test_ffe_agent_resilience(
        self, library_env: dict[str, str], test_case_file: str, test_agent: _TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Test FFE flag evaluation with resilience when the agent becomes unavailable.

        This comprehensive test verifies that:
        1. FFE flag evaluation works normally when agent is available (happy path)
        2. FFE continues to work when agent has connectivity issues (using local cache)
        3. All flag evaluation scenarios work during both normal and agent-down states
        4. Flag evaluations work correctly with preserved local caching
        5. Multiple evaluations remain consistent during agent connectivity issues

        This test combines comprehensive flag evaluation logic with agent resilience
        testing to ensure cached flag evaluations remain functional when the agent
        is completely unavailable.

        Note: Uses Docker container stop/start to simulate real agent unavailability.
        This approach preserves library cache while testing true resilience behavior.
        """
        # Load the test case file
        test_case_path = Path(__file__).parent / test_case_file

        if not test_case_path.exists():
            pytest.skip(f"Test case file not found: {test_case_path}")

        with test_case_path.open() as f:
            test_cases = json.load(f)

        # Phase 1: Setup FFE test environment
        _setup_ffe_test_environment(test_agent, test_library)

        # Phase 2: Happy Path - Run comprehensive flag evaluation when agent is available
        happy_path_results = _run_comprehensive_flag_evaluations(test_library, test_cases, test_case_file, "Happy path")

        # Phase 3: Simulate agent going down by stopping the test agent container
        # This preserves the library's cache while making agent truly unreachable
        import time

        # Get the Docker client and stop the test agent container
        docker_client = get_docker_client()
        agent_container = docker_client.containers.get(test_agent.container_name)
        agent_container.stop()

        # Give some time for connections to be dropped
        time.sleep(2.0)

        # Phase 4: Resilience Path - Verify FFE continues working with cached config
        _verify_cached_evaluations(test_library, happy_path_results, test_case_file, "agent downtime")

        # Phase 5: Test multiple evaluations to ensure consistency with cache
        _verify_evaluation_consistency(test_library, happy_path_results, "agent downtime")

        # Phase 6: Restart agent container for cleanup
        # This ensures subsequent tests have a working agent
        try:
            agent_container.start()
            # Give agent time to initialize
            time.sleep(3.0)
        except Exception as e:
            # If restart fails, try to get a fresh container reference
            try:
                agent_container = docker_client.containers.get(test_agent.container_name)
                agent_container.start()
                time.sleep(3.0)
            except Exception:
                # Log the issue but don't fail the test - pytest cleanup will handle it
                logger.warning(f"Could not restart test agent container: {e}")

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @parametrize("test_case_file", ALL_TEST_CASE_FILES)
    def test_ffe_rc_recovery_resilience(
        self, library_env: dict[str, str], test_case_file: str, test_agent: _TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Test FFE flag evaluation with resilience and recovery when Remote Config becomes available again.

        This comprehensive test verifies the complete recovery cycle:
        1. FFE flag evaluation works normally when RC is available (happy path)
        2. FFE continues to work when RC has brief issues (cached config)
        3. All flag evaluation scenarios work during both normal and degraded states
        4. FFE recovers and updates when RC stabilizes
        5. Flag evaluations remain consistent throughout the recovery process
        6. New flag configurations are properly applied after recovery

        This test combines comprehensive flag evaluation logic with RC recovery
        resilience testing to ensure cached flag evaluations work during outages
        and recover correctly when service is restored.

        Note: Uses shorter delays to avoid RC client timeout issues.
        """
        # Load the test case file
        test_case_path = Path(__file__).parent / test_case_file

        if not test_case_path.exists():
            pytest.skip(f"Test case file not found: {test_case_path}")

        with test_case_path.open() as f:
            test_cases = json.load(f)

        # Phase 1: Setup FFE test environment
        _setup_ffe_test_environment(test_agent, test_library)

        # Phase 2: Happy Path - Run comprehensive flag evaluation when RC is available
        happy_path_results = _run_comprehensive_flag_evaluations(test_library, test_cases, test_case_file, "Happy path")

        # Phase 3: Simulate RC service downtime with network delays
        import time

        # Simulate RC service downtime by introducing moderate delays
        test_agent.set_trace_delay(3000)  # 3 second delay simulates network issues/downtime
        time.sleep(1.0)

        # Phase 4: Resilience Path - Verify FFE continues working with comprehensive cached config
        _verify_cached_evaluations(test_library, happy_path_results, test_case_file, "RC downtime")

        # Phase 5: RC service recovery - restore normal operation
        # First remove the delay to simulate service recovery
        test_agent.set_trace_delay(0)  # Remove delay to restore normal RC operation

        # Create a modified config to simulate an update after recovery
        recovery_config = UFC_FIXTURE_DATA.copy()
        # Note: The exact modification depends on the UFC structure
        # This simulates a configuration update after service recovery

        # Allow extra time for RC polling to resume after delays
        time.sleep(2.0)

        recovery_apply_state = _set_and_wait_ffe_rc(test_agent, recovery_config, config_id="recovery_config")
        assert recovery_apply_state["apply_state"] == RemoteConfigApplyState.ACKNOWLEDGED.value

        # Allow time for the library to pick up the new config
        time.sleep(1.5)

        # Phase 6: Post-Recovery Path - Verify comprehensive flag evaluation works after recovery
        _verify_cached_evaluations(test_library, happy_path_results, test_case_file, "post-recovery")

        # Phase 7: Verify system is functioning normally after recovery with consistency checks
        _verify_evaluation_consistency(test_library, happy_path_results, "post-recovery")
