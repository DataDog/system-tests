import itertools
import json
import logging
from datetime import datetime, UTC
from pathlib import Path

import pytest

from utils import scenarios, context
from utils._context._scenarios import get_all_scenarios
from utils._context._scenarios.endtoend import EndToEndScenario

logger = logging.getLogger(__name__)

# Map of scenario pairs that cannot be merged and their specific reasons
# Structure: {"SCENARIO_A": {"SCENARIO_B": "reason", "SCENARIO_C": "reason"}}
# This allows one-to-many relationships where one scenario cannot be merged with multiple others
SKIP_MERGE_SCENARIOS = {
    "APPSEC_BLOCKING_FULL_DENYLIST": {
        "REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD": """
            If merge into REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD that is identical to this scenario,
            test_remote_configuration.py::Test_RemoteConfigurationUpdateSequenceASMDD::test_tracer_update_sequence
            will fail
        """.strip(),
        # Future example: if this scenario had multiple conflicting scenarios:
        # "ANOTHER_SCENARIO": "Different reason for another specific conflict",
    },
    "TRACE_PROPAGATION_STYLE_DEFAULT": {
        "TRACING_CONFIG_EMPTY": """TODO: check if this scenario can be merged into APPSEC_BLOCKING_FULL_DENYLIST""".strip(),
    },
    # Future example: Another scenario with its own restrictions:
    # "SOME_OTHER_SCENARIO": {
    #     "CONFLICTING_SCENARIO_1": "Reason for conflict with scenario 1",
    #     "CONFLICTING_SCENARIO_2": "Reason for conflict with scenario 2",
    # },
}


@scenarios.test_the_test
def test_minimal_number_of_scenarios():
    """Verify that EndToEnd scenarios don't have identical configurations and environment variables.

    This test performs a three-level validation:
    LEVEL 1: Uses EndToEndScenario.__eq__ method to perform comprehensive comparison
             of all configuration parameters.
    LEVEL 2: Checks if they have identical environment variables (weblog_env and agent_env).
    LEVEL 3: Checks if one scenario's weblog_env can be included in another's (subset validation).

    Test FAILS when:
    - LEVEL 1 + LEVEL 2: scenarios_are_equivalent == True AND environment_variables_identical == True

    Test REPORTS (but doesn't fail) when:
    - LEVEL 1 + LEVEL 3: scenarios_are_equivalent == True AND one_env_can_be_included_in_other == True
    """
    all_scenarios = get_all_scenarios()

    # Filter only scenarios that are exactly EndToEndScenario class (not subclasses)
    endtoend_scenarios: list[EndToEndScenario] = [
        scenario for scenario in all_scenarios if type(scenario) is EndToEndScenario
    ]

    def is_merge_blocked(scenario_a_name, scenario_b_name):
        """Check if two specific scenarios cannot be merged due to defined restrictions.

        This function checks both directions since merge restrictions are bidirectional.
        Returns (is_blocked, reason) where is_blocked is True if merge is not allowed.
        """
        # Check if scenario_a blocks merging with scenario_b
        if scenario_a_name in SKIP_MERGE_SCENARIOS:
            if scenario_b_name in SKIP_MERGE_SCENARIOS[scenario_a_name]:
                return True, SKIP_MERGE_SCENARIOS[scenario_a_name][scenario_b_name]

        # Check if scenario_b blocks merging with scenario_a (bidirectional)
        if scenario_b_name in SKIP_MERGE_SCENARIOS:
            if scenario_a_name in SKIP_MERGE_SCENARIOS[scenario_b_name]:
                return True, SKIP_MERGE_SCENARIOS[scenario_b_name][scenario_a_name]

        return False, ""

    def scenarios_are_equivalent(scenario_a, scenario_b):
        """Check if two scenarios are equivalent and could be merged.

        Uses the EndToEndScenario.__eq__ method which compares all configuration
        parameters except name, doc and weblog_env.
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
                # Skip None values as they indicate the variable should not be set
                if value is not None:
                    normalized[key] = str(value)

        return normalized

    def can_scenario_be_included(scenario_a, scenario_b):
        """Check if one scenario's weblog_env can be included in another's (subset validation).

        Returns True if the scenario with fewer weblog_env variables can be included
        in the other without conflicts (no variables with same name but different values).

        This uses the original weblog_env from constructor, not the final processed environment.
        """
        # Get original weblog_env from constructor
        original_env_a = getattr(scenario_a, "weblog_env", None) or {}
        original_env_b = getattr(scenario_b, "weblog_env", None) or {}

        # Determine which has fewer variables
        if len(original_env_a) <= len(original_env_b):
            smaller_env = original_env_a
            larger_env = original_env_b
            smaller_name = scenario_a.name
            larger_name = scenario_b.name
        else:
            smaller_env = original_env_b
            larger_env = original_env_a
            smaller_name = scenario_b.name
            larger_name = scenario_a.name

        # If both are empty, they're equivalent (handled by LEVEL 2)
        if not smaller_env and not larger_env:
            return False, "", ""

        # If smaller is empty but larger is not, smaller can be included in larger
        if not smaller_env and larger_env:
            return True, smaller_name, larger_name

        # Check if all variables in smaller_env exist in larger_env with same values
        for key, value in smaller_env.items():
            if key not in larger_env:
                # Variable doesn't exist in larger env, can still be included
                continue
            elif larger_env[key] != value:
                # Same variable name but different value = conflict
                return False, "", ""

        # All smaller_env variables are compatible with larger_env
        return True, smaller_name, larger_name

    # First, log scenario pairs marked to skip merge
    for scenario_name, blocked_scenarios in SKIP_MERGE_SCENARIOS.items():
        for blocked_scenario_name, reason in blocked_scenarios.items():
            logger.warning(
                f"Scenario '{scenario_name}' cannot be merged with '{blocked_scenario_name}'. Reason: {reason}"
            )

    # List to collect potential merge candidates (LEVEL 3)
    potential_merges = []

    # Compare each scenario with every other scenario
    for scenario_a, scenario_b in itertools.combinations(endtoend_scenarios, 2):
        # Skip scenario pairs marked to skip merge
        merge_blocked, block_reason = is_merge_blocked(scenario_a.name, scenario_b.name)
        if merge_blocked:
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

        # LEVEL 3: Check if one scenario's weblog_env can be included in another's
        can_be_included, smaller_scenario, larger_scenario = can_scenario_be_included(scenario_a, scenario_b)

        # FAIL CONDITIONS:
        # 1. LEVEL 1 + LEVEL 2: equivalent configs AND identical environment variables (MUST FAIL)
        if scenarios_equivalent and envs_identical:
            pytest.fail(
                f"Scenario '{scenario_a.name}' can be merged into scenario '{scenario_b.name}' "
                f"because they have equivalent configurations AND identical environment variables:\n"
                f"Weblog env: {weblog_env_a}\n"
                f"Agent env: {agent_env_a}"
            )

        # 2. LEVEL 1 + LEVEL 3: equivalent configs AND one can be included in the other (REPORT ONLY)
        if scenarios_equivalent and can_be_included:
            # Get original weblog_env from constructor (not final processed environment)
            smaller_original_env = (
                getattr(scenario_a, "weblog_env", None)
                if scenario_a.name == smaller_scenario
                else getattr(scenario_b, "weblog_env", None)
            )
            larger_original_env = (
                getattr(scenario_a, "weblog_env", None)
                if scenario_a.name == larger_scenario
                else getattr(scenario_b, "weblog_env", None)
            )

            # Calculate what new variables would be inserted
            smaller_env = smaller_original_env or {}
            larger_env = larger_original_env or {}

            # Variables that would be added to the larger scenario
            new_variables_to_insert = {key: value for key, value in smaller_env.items() if key not in larger_env}

            potential_merges.append(
                {
                    "smaller_scenario": smaller_scenario,
                    "larger_scenario": larger_scenario,
                    "reason": "equivalent configurations with compatible weblog_env (subset relationship)",
                    "new_variables_to_insert": new_variables_to_insert,
                    "smaller_weblog_env": smaller_env,
                    "larger_weblog_env": larger_env,
                }
            )

    # Generate report file with potential merges
    if potential_merges:
        # Create report file path in the scenario's log folder
        log_folder = Path(context.scenario.host_log_folder)
        report_file = log_folder / "potential_scenario_merges.json"

        # Ensure the log directory exists
        log_folder.mkdir(parents=True, exist_ok=True)

        # Prepare report data
        report_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "total_scenarios_analyzed": len(endtoend_scenarios),
            "potential_merge_candidates": len(potential_merges),
            "merges": potential_merges,
        }

        # Write report file
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        # Log summary
        logger.warning(f"Found {len(potential_merges)} potential merge candidates.")
        logger.warning(f"Report generated: {report_file.resolve()}")
        logger.info("📊 POTENTIAL SCENARIO MERGES DETECTED:")
        logger.info(f"   📄 Report file: {report_file.name}")
        logger.info(f"   🔍 Candidates found: {len(potential_merges)}")
        logger.info(f"   📈 Total scenarios: {len(endtoend_scenarios)}")
        logger.info("💡 These scenarios could potentially be merged to reduce test matrix size.")
        logger.info("   Review the report file for detailed analysis.")
    else:
        logger.info("No potential merge candidates found. All scenarios have distinct configurations.")
