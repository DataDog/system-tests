import json
import os
from utils._context._scenarios import get_all_scenarios, ScenarioGroup


def get_github_workflow_map(scenarios, scenarios_groups):
    result = {}

    for group in scenarios_groups:
        try:
            ScenarioGroup(group)
        except ValueError as e:
            raise ValueError(f"Valid groups are: {[item.value for item in ScenarioGroup]}") from e

    for scenario in get_all_scenarios():
        if not scenario.github_workflow:
            continue

        if scenario.github_workflow not in result:
            result[scenario.github_workflow] = []

        if scenario.name in scenarios:
            result[scenario.github_workflow].append(scenario.name)

        for group in scenarios_groups:
            if ScenarioGroup(group) in scenario.scenario_groups:
                result[scenario.github_workflow].append(scenario.name)
                break

    return result


def main():
    scnenario_map = get_github_workflow_map(
        json.loads(os.environ["SCENARIOS"]), json.loads(os.environ["SCENARIOS_GROUPS"])
    )
    for github_workflow, scnearios in scnenario_map.items():
        print(f"{github_workflow}_scenarios={json.dumps(scnearios)}")


if __name__ == "__main__":
    main()
