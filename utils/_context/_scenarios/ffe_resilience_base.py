"""Base scenario class for FFE (Feature Flag Evaluation) resilience testing.

This module provides the foundation for testing FFE behavior during various
agent and Remote Config failure conditions.
"""

import json
from pathlib import Path
from typing import Any, TYPE_CHECKING

import pytest

from utils.dd_constants import RemoteConfigApplyState
from utils.docker_fixtures._test_agent import TestAgentAPI

from .core import Scenario, scenario_groups

if TYPE_CHECKING:
    from utils.docker_fixtures import ParametricTestClientApi as APMLibrary


class FFEResilienceScenarioBase(Scenario):
    """Base class for FFE resilience testing scenarios.

    Provides common functionality for testing FFE behavior during
    agent and Remote Config failure conditions.
    """

    def __init__(self, name: str, doc: str) -> None:
        super().__init__(
            name=name,
            doc=doc,
            github_workflow="endtoend",  # Use endtoend workflow
            scenario_groups=[scenario_groups.feature_flag_exposure],
        )

        # Set properties that FFE tests need
        self.rc_api_enabled = True
        self.weblog_env = {
            "DD_EXPERIMENTAL_FLAGGING_PROVIDER_ENABLED": "true",
            "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.2",
        }

    def setup_ffe_test_environment(self, test_agent: TestAgentAPI, test_library: "APMLibrary", ufc_data: dict) -> None:
        """Set up the standard FFE test environment with RC and provider initialization.

        Args:
            test_agent: Test agent API instance
            test_library: APM library instance
            ufc_data: UFC fixture data for Remote Config
        """
        # Set up UFC Remote Config and wait for it to be applied
        apply_state = self.set_and_wait_ffe_rc(test_agent, ufc_data)
        assert apply_state["apply_state"] == RemoteConfigApplyState.ACKNOWLEDGED.value
        assert apply_state["product"] == "FFE_FLAGS"

        # Initialize FFE provider
        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

    def set_and_wait_ffe_rc(self, test_agent: TestAgentAPI, ufc_data: dict, config_id: str | None = None) -> dict[str, Any]:
        """Set FFE Remote Config and wait for it to be acknowledged.

        Args:
            test_agent: Test agent API instance
            ufc_data: UFC configuration data
            config_id: Optional config ID (defaults to "test_config")

        Returns:
            Apply state information from Remote Config
        """
        config_id = config_id or "test_config"

        rc_config = {
            "config": {
                "id": config_id,
                "product": "FFE_FLAGS",
                "sha256": "test",
            },
            "file": {
                "path": f"datadog/2/FFE_FLAGS/{config_id}/config",
                "content": ufc_data,
            },
        }

        # Set the config
        test_agent.set_remote_config(path=f"datadog/2/FFE_FLAGS/{config_id}/config", payload=rc_config)

        # Wait for RC acknowledgment
        return test_agent.wait_for_rc_apply_state("FFE_FLAGS", state=RemoteConfigApplyState.ACKNOWLEDGED, clear=True)

    def run_comprehensive_flag_evaluations(
        self, test_library: "APMLibrary", test_cases: list[dict], test_case_file: str, phase_name: str
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

    def verify_cached_evaluations(
        self, test_library: "APMLibrary", reference_results: dict[int, dict], test_case_file: str, phase_name: str
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

    def verify_evaluation_consistency(
        self, test_library: "APMLibrary", reference_results: dict[int, dict], phase_name: str, num_rounds: int = 3, num_cases: int = 3
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

    def load_test_cases(self, test_case_file: str) -> list[dict]:
        """Load test cases from JSON file.

        Args:
            test_case_file: Name of the test case file

        Returns:
            List of test case dictionaries
        """
        test_case_path = Path(__file__).parent.parent.parent / "tests" / "parametric" / "test_feature_flag_exposure" / test_case_file

        if not test_case_path.exists():
            pytest.skip(f"Test case file not found: {test_case_path}")

        with test_case_path.open() as f:
            return json.load(f)