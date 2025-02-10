import argparse
import json
from utils._context._scenarios import get_all_scenarios, ScenarioGroup
from ci_orchestrators.gitlab.gitlab_ci_orchestrator import print_aws_gitlab_pipeline
from ci_orchestrators.github.github_ci_orchestrator import print_github_output
from ci_orchestrators.scenario_groups.endtoend_orchestrator import get_endtoend_matrix

from ci_orchestrators.scenario_groups.ssi_orchestrator import get_aws_matrix


def get_workflow_map(scenarios, scenarios_groups) -> dict:
    result = {}  # type: dict[str, list[str]]

    scenarios_groups = [group.strip() for group in scenarios_groups if group.strip()]
    scenarios = {scenario.strip(): False for scenario in scenarios if scenario.strip()}

    for group in scenarios_groups:
        try:
            ScenarioGroup(group)
        except ValueError as e:
            raise ValueError(f"Valid groups are: {[item.value for item in ScenarioGroup]}") from e

    for scenario in get_all_scenarios():
        # TODO change the variable "github_workflow" to "ci_workflow" in the scenario object
        if not scenario.github_workflow:
            scenarios[scenario.name] = True  # won't be executed, but it exists
            continue

        if scenario.github_workflow not in result:
            result[scenario.github_workflow] = []

        if scenario.name in scenarios:
            result[scenario.github_workflow].append(scenario.name)
            scenarios[scenario.name] = True

        for group in scenarios_groups:
            if ScenarioGroup(group) in scenario.scenario_groups:
                result[scenario.github_workflow].append(scenario.name)
                break

    for scenario, found in scenarios.items():
        if not found:
            raise ValueError(f"Scenario {scenario} does not exists")

    return result


def _handle_github(language: str, scenario_map: dict, parametric_job_count: int, ci_environment: str) -> None:
    result = get_endtoend_matrix(language, scenario_map, parametric_job_count, ci_environment)
    print_github_output(result)


def _handle_gitlab(language: str, scenario_map: dict, ci_environment: str) -> None:
    if "aws_ssi" in scenario_map:
        aws_matrix = get_aws_matrix(
            "utils/virtual_machine/virtual_machines.json",
            "utils/scripts/ci_orchestrators/scenario_groups/aws_ssi.json",
            scenario_map["aws_ssi"],
            language,
        )
        print_aws_gitlab_pipeline(language, aws_matrix, ci_environment)


def _handle_json(language: str, scenario_map: dict, parametric_job_count: int, ci_environment: str) -> None:
    if "aws_ssi" in scenario_map:
        result = get_aws_matrix(
            "utils/virtual_machine/virtual_machines.json",
            "utils/scripts/ci_orchestrators/scenario_groups/aws_ssi.json",
            scenario_map["aws_ssi"],
            language,
        )
        print(json.dumps(result))
    else:
        result = get_endtoend_matrix(language, scenario_map, parametric_job_count, ci_environment)
        print(json.dumps(result))


def main(
    language: str, scenarios: str, groups: str, parametric_job_count: int, ci_environment: str, output_format: str
) -> None:
    # this data struture is a dict where:
    #  the key is the workflow identifier
    #  the value is also a dict, where the key/value pair is the parameter name/value.
    scenario_map = get_workflow_map(scenarios.split(","), groups.split(","))

    if output_format == "github":
        _handle_github(language, scenario_map, parametric_job_count, ci_environment)
    elif output_format == "gitlab":
        _handle_gitlab(language, scenario_map, ci_environment)
    elif output_format == "json":
        _handle_json(language, scenario_map, parametric_job_count, ci_environment)
    else:
        raise ValueError(f"Invalid format: {format}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="get-ci-parameters", description="Get scenarios and weblogs to run")
    parser.add_argument(
        "language",
        type=str,
        help="One of the supported Datadog languages",
        choices=["cpp", "dotnet", "python", "ruby", "golang", "java", "nodejs", "php"],
    )

    parser.add_argument(
        "--format",
        "-f",
        type=str,
        help="Select the output format",
        choices=["github", "gitlab", "json"],
        default="github",
    )

    parser.add_argument("--scenarios", "-s", type=str, help="Scenarios to run", default="")
    parser.add_argument("--groups", "-g", type=str, help="Scenario groups to run", default="")

    # workflow specific parameters
    parser.add_argument("--parametric-job-count", type=int, help="How may jobs must run parametric scenario", default=1)

    # Misc
    parser.add_argument("--ci-environment", type=str, help="Used internally in system-tests CI", default="custom")

    args = parser.parse_args()

    main(
        language=args.language,
        scenarios=args.scenarios,
        groups=args.groups,
        ci_environment=args.ci_environment,
        output_format=args.format,
        parametric_job_count=args.parametric_job_count,
    )
