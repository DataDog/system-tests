import re
import warnings
from utils import scenarios
from utils._context._scenarios import get_all_scenarios
from utils._context._scenarios.endtoend import EndToEndScenario


@scenarios.test_the_test
def test_minimal_number_of_scenarios():
    """
    Verify that EndToEnd scenarios don't have identical environment variables.
    If two scenarios have the same weblog_env and agent_env, they could be merged.
    """
    all_scenarios = get_all_scenarios()
    
    # Filter only EndToEnd scenarios
    endtoend_scenarios = [
        scenario for scenario in all_scenarios 
        if isinstance(scenario, EndToEndScenario)
    ]
    
    def normalize_env(env_dict):
        """Normalize environment dict by removing dynamic/system variables and handling None values."""
        if not env_dict:
            return {}
        
        # Exclude variables that are dynamic or system-specific
        excluded_vars = {
            'SYSTEMTESTS_SCENARIO',  # This is always different per scenario
            'DD_LOGS_INJECTION',     # May be added dynamically
        }
        
        normalized = {}
        for key, value in env_dict.items():
            if key not in excluded_vars:
                # Convert None values to empty string for consistent comparison
                normalized[key] = str(value) if value is not None else ""
        
        return normalized
    
    # Compare each scenario with every other scenario
    for i, scenario_a in enumerate(endtoend_scenarios):
        for j, scenario_b in enumerate(endtoend_scenarios):
            if i >= j:  # Skip self-comparison and duplicate pairs
                continue
                
            # Check if either scenario is marked to skip merge
            if getattr(scenario_a, 'skip_merge', False):
                reason = getattr(scenario_a, 'skip_merge_reason', 'No reason provided')
                warnings.warn(
                    f"Scenario '{scenario_a.name}' is marked to skip merge. Reason: {reason}",
                    UserWarning
                )
                continue
                
            if getattr(scenario_b, 'skip_merge', False):
                reason = getattr(scenario_b, 'skip_merge_reason', 'No reason provided')
                warnings.warn(
                    f"Scenario '{scenario_b.name}' is marked to skip merge. Reason: {reason}",
                    UserWarning
                )
                continue
                
            # Get and normalize environment variables for both scenarios
            weblog_env_a = normalize_env(scenario_a.weblog_container.environment)
            agent_env_a = normalize_env(scenario_a.agent_container.environment)
            
            weblog_env_b = normalize_env(scenario_b.weblog_container.environment)
            agent_env_b = normalize_env(scenario_b.agent_container.environment)
            
            # Check if both weblog and agent environments are identical
            weblog_envs_match = weblog_env_a == weblog_env_b
            agent_envs_match = agent_env_a == agent_env_b
            
            # If both environments match, these scenarios could be merged
            assert not (weblog_envs_match and agent_envs_match), (
                f"Scenario '{scenario_a.name}' can be merged into scenario '{scenario_b.name}' "
                f"because they have identical environment variables:\n"
                f"Weblog env: {weblog_env_a}\n"
                f"Agent env: {agent_env_a}"
            )

# assert len(get_all_scenarios()) == 3
