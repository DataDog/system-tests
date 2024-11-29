import argparse
import json
import os
from utils._context._scenarios import get_all_scenarios, ScenarioGroup


def get_github_workflow_map(scenarios, scenarios_groups):
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


def get_graphql_weblogs(library):
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


def get_endtoend_weblogs(library):
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
        "python": ["flask-poc", "django-poc", "uwsgi-poc", "uds-flask", "python3.12", "fastapi"],
        "ruby": [
            "rack",
            "uds-sinatra",
            *[f"sinatra{v}" for v in ["14", "20", "21", "22", "30", "31", "32", "40"]],
            *[f"rails{v}" for v in ["42", "50", "51", "52", "60", "61", "70", "71", "72", "80"]],
        ],
    }

    return weblogs[library]


def get_opentelemetry_weblogs(library):

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


def main(language: str, scenarios: str, groups: str):
    scenario_map = get_github_workflow_map(scenarios.split(","), groups.split(","))

    for github_workflow, scenarios in scenario_map.items():
        print(f"{github_workflow}_scenarios={json.dumps(scenarios)}")

    endtoend_weblogs = get_endtoend_weblogs(language)
    print(f"endtoend_weblogs={json.dumps(endtoend_weblogs)}")

    graphql_weblogs = get_graphql_weblogs(language)
    print(f"graphql_weblogs={json.dumps(graphql_weblogs)}")

    opentelemetry_weblogs = get_opentelemetry_weblogs(language)
    print(f"opentelemetry_weblogs={json.dumps(opentelemetry_weblogs)}")

    _experimental_parametric_job_count = int(os.environ.get("_EXPERIMENTAL_PARAMETRIC_JOB_COUNT", "1"))
    print(f"_experimental_parametric_job_matrix={str(list(range(1, _experimental_parametric_job_count + 1)))}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="get-github-parameters", description="Get scenarios and weblog to run",)
    parser.add_argument(
        "language",
        type=str,
        help="One of the supported Datadog languages",
        choices=["cpp", "dotnet", "python", "ruby", "golang", "java", "nodejs", "php"],
    )

    parser.add_argument("--scenarios", "-s", type=str, help="Scenarios to run", default="")
    parser.add_argument("--groups", "-g", type=str, help="Scenario groups to run", default="")

    args = parser.parse_args()

    main(language=args.language, scenarios=args.scenarios, groups=args.groups)
