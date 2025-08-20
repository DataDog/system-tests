import logging
import pytest
from utils import scenarios
from utils._context._scenarios import get_all_scenarios
from utils._context._scenarios.endtoend import EndToEndScenario

logger = logging.getLogger(__name__)


@scenarios.test_the_test
def test_minimal_number_of_scenarios():
    """Verify that EndToEnd scenarios don't have both equivalent configurations AND identical environment variables.

    This test performs a two-level validation and ONLY fails if BOTH conditions are true:
    LEVEL 1: Uses EndToEndScenario.__eq__ method to perform comprehensive comparison
             of all configuration parameters.
    LEVEL 2: Checks if they have identical environment variables (weblog_env and agent_env).

    Test FAILS only when: scenarios_are_equivalent == True AND environment_variables_identical == True
    """
    all_scenarios = get_all_scenarios()

    # Filter only scenarios that are exactly EndToEndScenario class (not subclasses)
    endtoend_scenarios = [scenario for scenario in all_scenarios if type(scenario) is EndToEndScenario]

    def scenarios_are_equivalent(scenario_a, scenario_b):
        """Check if two scenarios are equivalent and could be merged.

        Uses the EndToEndScenario.__eq__ method which compares all configuration
        parameters except name, doc, skip_merge, skip_merge_reason and weblog_env.
        This is more comprehensive than just comparing environment variables.
        """
        return scenario_a == scenario_b

    def normalize_env(env_dict):
        """Normalize environment dict by removing dynamic/system variables and handling None values."""
        if not env_dict:
            return {}

        # Exclude variables that are dynamic or system-specific
        excluded_vars = {
            "SYSTEMTESTS_SCENARIO",  # This is always different per scenario
            "DD_LOGS_INJECTION",  # May be added dynamically
        }

        normalized = {}
        for key, value in env_dict.items():
            if key not in excluded_vars:
                # Convert None values to empty string for consistent comparison
                normalized[key] = str(value) if value is not None else ""

        return normalized

    # First, log scenarios marked to skip merge (only once per scenario)
    logged_skip_scenarios = set()
    for scenario in endtoend_scenarios:
        if getattr(scenario, "skip_merge", False) and scenario.name not in logged_skip_scenarios:
            reason = getattr(scenario, "skip_merge_reason", "No reason provided")
            logger.warning(f"Scenario '{scenario.name}' is marked to skip merge. Reason: {reason}")
            logged_skip_scenarios.add(scenario.name)

    # Compare each scenario with every other scenario
    for i, scenario_a in enumerate(endtoend_scenarios):
        for j, scenario_b in enumerate(endtoend_scenarios):
            if i >= j:  # Skip self-comparison and duplicate pairs
                continue

            # Skip scenarios marked to skip merge
            if getattr(scenario_a, "skip_merge", False) or getattr(scenario_b, "skip_merge", False):
                continue

            # LEVEL 1: Check if scenarios are completely equivalent using comprehensive comparison
            scenarios_equivalent = scenarios_are_equivalent(scenario_a, scenario_b)

            # LEVEL 2: Check if they have identical environment variables
            # Get and normalize environment variables for both scenarios
            weblog_env_a = normalize_env(scenario_a.weblog_container.environment)
            agent_env_a = normalize_env(scenario_a.agent_container.environment)

            weblog_env_b = normalize_env(scenario_b.weblog_container.environment)
            agent_env_b = normalize_env(scenario_b.agent_container.environment)

            # Check if both weblog and agent environments are identical
            weblog_envs_match = weblog_env_a == weblog_env_b
            agent_envs_match = agent_env_a == agent_env_b
            envs_identical = weblog_envs_match and agent_envs_match

            # FAIL only if BOTH conditions are true: equivalent configs AND identical environment variables
            if scenarios_equivalent and envs_identical:
                pytest.fail(
                    f"Scenario '{scenario_a.name}' can be merged into scenario '{scenario_b.name}' "
                    f"because they have equivalent configurations AND identical environment variables:\n"
                    f"Weblog env: {weblog_env_a}\n"
                    f"Agent env: {agent_env_a}"
                )
