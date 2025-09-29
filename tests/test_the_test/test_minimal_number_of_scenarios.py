import itertools
import json
from typing import Any

import pytest

from utils._context._scenarios import get_all_scenarios, EndToEndScenario, scenarios
from utils import logger

# Map of scenario pairs that cannot be merged and their specific reasons
# Please keep this list ordered.
# You don't need to add B/A if A/B exists
# Structure: {("SCENARIO_A", "SCENARIO_B"): "reason"}
SKIP_MERGE_SCENARIOS: dict[tuple[str, str], str] = {
    ("APPSEC_API_SECURITY_RC", "APPSEC_RUNTIME_ACTIVATION"): """ Can't merge because:
FAILED tests/appsec/test_remote_config_rule_changes.py::Test_BlockingActionChangesWithRemoteConfig::test_block_405
FAILED tests/appsec/test_remote_config_rule_changes.py::Test_Unknown_Action::test_unknown_action
FAILED tests/appsec/test_remote_config_rule_changes.py::Test_Multiple_Actions::test_multiple_actions
FAILED tests/appsec/test_runtime_activation.py::Test_RuntimeActivation::test_asm_features
FAILED tests/appsec/test_runtime_activation.py::Test_RuntimeDeactivation::test_asm_features
FAILED tests/appsec/test_suspicious_attacker_blocking.py::Test_Suspicious_Attacker_Blocking::test_block_suspicious_attacker""",
    ("APPSEC_AUTO_EVENTS_RC", "APPSEC_RUNTIME_ACTIVATION"): "TODO",
    ("APPSEC_BLOCKING", "GRAPHQL_APPSEC"): "TODO",
    ("APPSEC_BLOCKING_FULL_DENYLIST", "APPSEC_RUNTIME_ACTIVATION"): "TODO",
    # If merge into REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD that is identical to this scenario,
    # test_remote_configuration.py::Test_RemoteConfigurationUpdateSequenceASMDD::test_tracer_update_sequence will fail
    ("APPSEC_BLOCKING_FULL_DENYLIST", "REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD"): "Incompatible test sequence",
    ("APPSEC_REQUEST_BLOCKING", "APPSEC_BLOCKING_FULL_DENYLIST"): "TODO",
    ("APPSEC_REQUEST_BLOCKING", "APPSEC_RUNTIME_ACTIVATION"): "TODO",
    ("APPSEC_RUNTIME_ACTIVATION", "REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD"): "TODO",
    ("APPSEC_RUNTIME_ACTIVATION", "REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES_NOCACHE"): "TODO",
    ("APPSEC_RUNTIME_ACTIVATION", "REMOTE_CONFIG_MOCKED_BACKEND_LIVE_DEBUGGING"): "TODO",
    ("APPSEC_RUNTIME_ACTIVATION", "TRACING_CONFIG_NONDEFAULT_4"): "TODO",
    ("REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD", "APPSEC_REQUEST_BLOCKING"): "TODO",
    ("REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES", "REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES_NOCACHE"): "TODO",
    ("TRACING_CONFIG_EMPTY", "TRACE_PROPAGATION_STYLE_DEFAULT"): "TODO",
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

    # Filter only scenarios that are exactly EndToEndScenario class (not subclasses)
    endtoend_scenarios: list[EndToEndScenario] = [
        scenario for scenario in get_all_scenarios() if type(scenario) is EndToEndScenario
    ]

    # sort keys in SKIP_MERGE_SCENARIOS
    ignored_pairs = {tuple(sorted(key)): reason for key, reason in SKIP_MERGE_SCENARIOS.items()}

    # Compare each scenario with every other scenario
    for scenario_a, scenario_b in itertools.combinations(endtoend_scenarios, 2):
        key = tuple(sorted((scenario_b.name, scenario_a.name)))

        logger.info(f"Checking {key}")

        # Skip scenario pairs marked to skip merge
        if key in ignored_pairs:
            logger.debug(f"-> Merge is blocked: {ignored_pairs[key]}")
            continue

        # LEVEL 1: Check if scenarios are completely equivalent
        ignored = {
            # scenario specific
            ".doc",
            ".name",
            ".scenario_groups",
            # duplicated values
            "._required_containers",
            "._supporting_containers",
            ".weblog_container.depends_on",
            # will use a dedicated logic
            ".weblog_container.environment",
            ".agent_container.environment",
        }

        diff = _get_difference(scenario_a, scenario_b, ignored=ignored)
        logger.debug(f"-> differences: {diff}")

        if diff is not None:
            # They have a difference, continue to next pair
            continue

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

        logger.debug(f"-> envs_identical: {envs_identical}")

        if envs_identical:
            logger.error(f"-> Scenarios {key} are identicals!")
            logger.error(f"Weblog env: {json.dumps(weblog_env_a, indent=2)}")
            logger.error(f"Agent env: {json.dumps(agent_env_a, indent=2)}")

            pytest.fail(
                f"Scenario '{scenario_a.name}' can be merged into scenario '{scenario_b.name}' "
                f"because they have equivalent configurations AND identical environment variables:\n"
            )

        small_scenario = (
            scenario_a
            if len(scenario_a.weblog_container.environment) < len(scenario_b.weblog_container.environment)
            else scenario_b
        )
        large_scenario = (
            scenario_a
            if len(scenario_a.weblog_container.environment) >= len(scenario_b.weblog_container.environment)
            else scenario_b
        )

        # 2. LEVEL 1 + LEVEL 3: equivalent configs AND one can be included in the other (REPORT ONLY)
        # python trickery to get if a dict is a sub set of another
        if small_scenario.weblog_container.environment.items() <= large_scenario.weblog_container.environment.items():
            logger.error(f"Small scenario: {small_scenario.name}")
            logger.error(f"Large scenario: {large_scenario.name}")

            log_dict_diff(small_scenario.weblog_container.environment, large_scenario.weblog_container.environment)

            pytest.fail(
                f"Scenarios {key} have equivalent configurations with compatible weblog_env (subset relationship)"
            )


def normalize_env(env_dict: dict) -> dict[str, str]:
    """Removes None values."""
    return {key: str(value) for key, value in env_dict.items() if value is not None}


def _get_difference(a: Any, b: Any, ignored: set[str], base_name: str = "") -> str | None:  # noqa: ANN401
    """Compare two objects recursively and return a description of the first difference found.

    Parameters
    ----------
    a : Any
        The first object to compare.
    b : Any
        The second object to compare.
    ignored : set of str
        A set of attribute names or keys to ignore during comparison.
    base_name : str, optional
        A prefix used in the returned difference path (default is an empty string).

    Returns
    -------
    str or None
        A human-readable string describing the first difference found,
        or ``None`` if the two objects are considered equal (after ignoring
        the specified attributes).

    """

    if base_name in ignored or a is b:
        # Handle identical references and ignored props
        return None

    # type differ -> not the same
    if type(a) is not type(b):
        return f"{base_name}: type_diff"

    # Handle simple types
    if isinstance(a, (int, float, str, bool, type(None))):
        return None if a == b else f"{base_name}:  {a} vs {b}"

    # Handle sequences
    if isinstance(a, (list, tuple)):
        if len(a) != len(b):
            return f"{base_name}: size differs"

        for x, y in zip(a, b, strict=True):
            if (diff := _get_difference(x, y, ignored, f"{base_name}[]")) is not None:
                return diff

        return None

    # Handle dicts
    if isinstance(a, dict):
        if a.keys() != b.keys():
            return f"{base_name}: keys {a.keys()} {b.keys()}"

        for name in a:
            if (diff := _get_difference(a[name], b[name], ignored, f"{base_name}.{name}")) is not None:
                return diff

        return None

    # Handle objects with attributes
    if hasattr(a, "__dict__") and hasattr(b, "__dict__"):
        return _get_difference(vars(a), vars(b), ignored, base_name)

    # Fallback
    return None if a == b else f"{base_name}: {a} vs {b}"


def log_dict_diff(a: dict, b: dict) -> None:
    for key in a.keys() - b.keys():
        logger.error(f"- {key}: {a[key]!r} (missing in second dict)")

    for key in b.keys() - a.keys():
        logger.error(f"+ {key}: {b[key]!r} (missing in first dict)")

    for key in a.keys() & b.keys():
        if a[key] != b[key]:
            logger.error(f"~ {key}: {a[key]!r} -> {b[key]!r}")
