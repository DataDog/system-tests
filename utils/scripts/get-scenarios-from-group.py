import sys

from utils._context._scenarios import get_all_scenarios, scenario_groups


def main(group_name: str) -> None:
    if group_name == "TRACER_ESSENTIAL_SCENARIOS":  # legacy
        group_name = "essentials"

    group_name = group_name.strip().lower().replace("_", "-")

    if group_name.endswith("-scenarios"):
        group_name = group_name[:-10]

    group = scenario_groups[group_name]

    scenarios = [scenario.name for scenario in get_all_scenarios() if group in scenario.scenario_groups]
    scenarios.sort()

    print("\n".join(scenarios))


if __name__ == "__main__":
    main(sys.argv[1])
