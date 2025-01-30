from collections import defaultdict
import argparse
import json
from utils._context._scenarios import get_all_scenarios, ScenarioGroup


def get_github_workflow_map(scenarios, scenarios_groups) -> dict:
    result = {}

    scenarios_groups = [group.strip() for group in scenarios_groups if group.strip()]
    scenarios = {scenario.strip(): False for scenario in scenarios if scenario.strip()}

    for group in scenarios_groups:
        try:
            ScenarioGroup(group)
        except ValueError as e:
            raise ValueError(f"Valid groups are: {[item.value for item in ScenarioGroup]}") from e

    for scenario in get_all_scenarios():
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


def get_graphql_weblogs(library) -> list[str]:
    weblogs = {
        "cpp": [],
        "dotnet": [],
        "golang": ["gqlgen", "graph-gophers", "graphql-go"],
        "java": [],
        "nodejs": ["express4", "uds-express4", "express4-typescript", "express5"],
        "php": [],
        "python": [],
        "ruby": ["graphql23"],
    }

    return weblogs[library]


def get_endtoend_weblogs(library, ci_environment: str) -> list[str]:
    weblogs = {
        "cpp": ["nginx"],
        "dotnet": ["poc", "uds"],
        "golang": ["chi", "echo", "gin", "net-http", "uds-echo"],
        "java": [
            "akka-http",
            "jersey-grizzly2",
            "play",
            "ratpack",
            "resteasy-netty3",
            "spring-boot-jetty",
            "spring-boot",
            "spring-boot-3-native",
            "spring-boot-openliberty",
            "spring-boot-wildfly",
            "spring-boot-undertow",
            "spring-boot-payara",
            "vertx3",
            "vertx4",
            "uds-spring-boot",
        ],
        "nodejs": ["express4", "uds-express4", "express4-typescript", "express5", "nextjs"],
        "php": [
            *[f"apache-mod-{v}" for v in ["7.0", "7.1", "7.2", "7.3", "7.4", "8.0", "8.1", "8.2"]],
            *[f"apache-mod-{v}-zts" for v in ["7.0", "7.1", "7.2", "7.3", "7.4", "8.0", "8.1", "8.2"]],
            *[f"php-fpm-{v}" for v in ["7.0", "7.1", "7.2", "7.3", "7.4", "8.0", "8.1", "8.2"]],
        ],
        "python": ["flask-poc", "django-poc", "uwsgi-poc", "uds-flask", "python3.12", "fastapi", "django-py3.13"],
        "ruby": [
            "rack",
            "uds-sinatra",
            *[f"sinatra{v}" for v in ["14", "20", "21", "22", "30", "31", "32", "40"]],
            *[f"rails{v}" for v in ["42", "50", "51", "52", "60", "61", "70", "71", "72", "80"]],
        ],
    }

    if ci_environment != "dev":
        # as now, django-py3.13 support is not released
        weblogs["python"].remove("django-py3.13")

    return weblogs[library]


def get_opentelemetry_weblogs(library) -> list[str]:
    weblogs = {
        "cpp": [],
        "dotnet": [],
        "golang": [],
        "java": ["spring-boot-otel"],
        "nodejs": ["express4-otel"],
        "php": [],
        "python": ["flask-poc-otel"],
        "ruby": [],
    }

    return weblogs[library]


class Workflow:
    def __init__(self) -> None:
        self.parameters = {}

    def __getitem__(self, key: str):
        return self.parameters[key]


class Result:
    def __init__(self) -> None:
        self.workflows: dict[str, Workflow] = defaultdict(Workflow)

    def __getitem__(self, key: str) -> Workflow:
        return self.workflows[key]

    def print(self, output_format: str) -> None:
        if output_format == "github":
            for workflow_name, workflow in self.workflows.items():
                for parameter, value in workflow.parameters.items():
                    print(f"{workflow_name}_{parameter}={json.dumps(value)}")
        else:
            raise ValueError(f"Invalid format: {format}")


def main(
    language: str, scenarios: str, groups: str, parametric_job_count: int, ci_environment: str, output_format: str
) -> None:
    result = Result()
    scenario_map = get_github_workflow_map(scenarios.split(","), groups.split(","))

    print(groups)
    for github_workflow, scenario_list in scenario_map.items():
        result[github_workflow].parameters["scenarios"] = scenario_list

    result["endtoend"].parameters["weblogs"] = get_endtoend_weblogs(language, ci_environment)
    result["graphql"].parameters["weblogs"] = get_graphql_weblogs(language)
    result["opentelemetry"].parameters["weblogs"] = get_opentelemetry_weblogs(language)
    result["parametric"].parameters["job_count"] = parametric_job_count
    result["parametric"].parameters["job_matrix"] = list(range(1, parametric_job_count + 1))

    result.print(output_format)
    print(f"_experimental_parametric_job_matrix={result['parametric'].parameters['job_matrix']!s}")  # legacy


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="get-github-parameters", description="Get scenarios and weblogs to run")
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
        choices=["github"],
        default="github",
    )

    parser.add_argument("--scenarios", "-s", type=str, help="Scenarios to run", default="")
    parser.add_argument("--groups", "-g", type=str, help="Scenario groups to run", default="")

    # workflow specific parameters
    parser.add_argument("--parametric-job_count", type=int, help="How may jobs must run parametric scenario", default=1)

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
