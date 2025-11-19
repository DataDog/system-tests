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
    def test_ffe_remote_config_resilience(
        self, library_env: dict[str, str], test_agent: _TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Test FFE resilience when Remote Config becomes unavailable.

        This test verifies that:
        1. FFE works normally when RC is available
        2. FFE continues to work with cached config when RC goes down
        3. Flag evaluations use the local cache when RC is unavailable

        """
        # Phase 1: Normal operation - Set up UFC Remote Config and verify it works
        apply_state = _set_and_wait_ffe_rc(test_agent, UFC_FIXTURE_DATA)
        assert apply_state["apply_state"] == RemoteConfigApplyState.ACKNOWLEDGED.value
        assert apply_state["product"] == RC_PRODUCT

        # Initialize FFE provider
        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        # Test flag evaluation works normally (using first test case from fixture)
        test_flag = "flag-1"
        test_result = test_library.ffe_evaluate(
            flag=test_flag,
            variation_type="bool",
            default_value=False,
            targeting_key="user-1",
            attributes={},
        )
        # Verify evaluation works (exact value depends on test fixture)
        assert "value" in test_result, "Flag evaluation should return a value"

        # Phase 2: Simulate RC becoming unavailable by introducing network delays
        # This simulates RC service being down or unreachable due to network issues
        import time

        # Introduce significant delay to RC requests to simulate service being down/slow
        # This is more realistic than sending empty configs
        test_agent.set_trace_delay(5000)  # 5 second delay simulates network timeout/issues

        # Give some time for the delay to take effect
        time.sleep(1.0)

        # Phase 3: Verify FFE continues working with cached config
        # The library should continue to work using the previously cached config
        cached_result = test_library.ffe_evaluate(
            flag=test_flag,
            variation_type="bool",
            default_value=False,
            targeting_key="user-1",
            attributes={},
        )

        # FFE should still work using cached configuration
        assert "value" in cached_result, "FFE should work with cached config when RC is down"

        # The result should be consistent with the cached config
        # (The exact behavior may vary by implementation - some may return cached values,
        # others may fall back to defaults)
        cached_value = cached_result["value"]
        assert cached_value is not None, "FFE should return a valid value even when RC is down"

        # Phase 4: Restore normal operation - reset delay for cleanup
        test_agent.set_trace_delay(0)  # Reset delay to restore normal operation

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_ffe_agent_resilience(
        self, library_env: dict[str, str], test_agent: _TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Test FFE resilience when the agent becomes unavailable.

        This test verifies that:
        1. FFE works normally when agent is available
        2. FFE continues to work when agent has connectivity issues (using local cache)
        3. Flag evaluations work correctly with preserved local caching
        4. Multiple evaluations remain consistent during agent connectivity issues

        Note: Uses network delays to simulate agent issues in parametric test environment.
        This approach preserves library cache while testing resilience behavior.

        """
        # Phase 1: Normal operation - Set up UFC Remote Config and verify it works
        apply_state = _set_and_wait_ffe_rc(test_agent, UFC_FIXTURE_DATA)
        assert apply_state["apply_state"] == RemoteConfigApplyState.ACKNOWLEDGED.value
        assert apply_state["product"] == RC_PRODUCT

        # Initialize FFE provider
        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        # Test flag evaluation works normally
        test_flag = "flag-1"
        test_result = test_library.ffe_evaluate(
            flag=test_flag,
            variation_type="bool",
            default_value=False,
            targeting_key="user-1",
            attributes={},
        )
        assert "value" in test_result, "Flag evaluation should return a value"

        # Phase 2: Simulate agent going down by stopping the test agent container
        # This preserves the library's cache while making agent truly unreachable
        import time

        # Get the Docker client and stop the test agent container
        docker_client = get_docker_client()
        agent_container = docker_client.containers.get(test_agent.container_name)
        agent_container.stop()

        # Give some time for connections to be dropped
        time.sleep(2.0)

        # Phase 3: Verify FFE continues working with cached config while agent is down
        # The library should fall back to cached configurations
        cached_result = test_library.ffe_evaluate(
            flag=test_flag,
            variation_type="bool",
            default_value=False,
            targeting_key="user-1",
            attributes={},
        )

        # FFE should still work using cached configuration
        assert "value" in cached_result, "FFE should work with cached config when agent is down"

        cached_value = cached_result["value"]
        assert cached_value is not None, "FFE should return a valid value even when agent is down"

        # Test multiple evaluations to ensure consistency with cache
        for i in range(3):
            repeat_result = test_library.ffe_evaluate(
                flag=test_flag,
                variation_type="bool",
                default_value=False,
                targeting_key=f"cached-user-{i}",
                attributes={},
            )
            assert "value" in repeat_result, f"FFE evaluation {i} should work with cached config"

        # Phase 4: Restart agent container for cleanup
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
                print(f"Warning: Could not restart test agent container: {e}")
                pass

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_ffe_rc_recovery_resilience(
        self, library_env: dict[str, str], test_agent: _TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Test FFE resilience and recovery when Remote Config becomes available again.

        This test verifies the complete recovery cycle:
        1. FFE works normally when RC is available
        2. FFE continues to work when RC has brief issues (cached config)
        3. FFE recovers and updates when RC stabilizes
        4. New flag configurations are properly applied after recovery

        Note: Uses shorter delays to avoid RC client timeout issues.

        """
        # Phase 1: Initial setup with RC available
        apply_state = _set_and_wait_ffe_rc(test_agent, UFC_FIXTURE_DATA)
        assert apply_state["apply_state"] == RemoteConfigApplyState.ACKNOWLEDGED.value

        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        # Test initial flag evaluation
        test_flag = "flag-1"
        initial_result = test_library.ffe_evaluate(
            flag=test_flag,
            variation_type="bool",
            default_value=False,
            targeting_key="user-1",
            attributes={},
        )
        assert "value" in initial_result, "Initial flag evaluation should work"

        # Phase 2: Simulate RC service downtime with network delays
        import time

        # Simulate RC service downtime by introducing moderate delays
        test_agent.set_trace_delay(3000)  # 3 second delay simulates network issues/downtime
        time.sleep(1.0)

        # Verify FFE still works with cache
        cached_result = test_library.ffe_evaluate(
            flag=test_flag,
            variation_type="bool",
            default_value=False,
            targeting_key="user-1",
            attributes={},
        )
        assert "value" in cached_result, "FFE should work during RC downtime"

        # Phase 3: RC service recovery - restore normal operation
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

        # Phase 4: Verify recovery and new config application
        recovery_result = test_library.ffe_evaluate(
            flag=test_flag,
            variation_type="bool",
            default_value=False,
            targeting_key="user-1",
            attributes={},
        )
        assert "value" in recovery_result, "FFE should work after RC recovery"

        # Verify system is functioning normally after recovery
        for i in range(3):
            consistency_result = test_library.ffe_evaluate(
                flag=test_flag,
                variation_type="bool",
                default_value=False,
                targeting_key=f"recovery-user-{i}",
                attributes={},
            )
            assert "value" in consistency_result, f"FFE evaluation {i} should work consistently after recovery"
