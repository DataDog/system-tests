import json
import os
from utils._context._scenarios import get_all_scenarios, ScenarioGroup


def get_github_workflow_map(scenarios, scenarios_groups):
    result = {}

    scenarios_groups = [group.strip() for group in scenarios_groups if group.strip()]
    scenarios = [scenario.strip() for scenario in scenarios if scenario.strip()]

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
        "nodejs": ["express4", "uds-express4", "express4-typescript", "nextjs"],
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
            *[f"rails{v}" for v in ["50", "51", "52", "60", "61", "70", "71"]],
        ],
    }

    return weblogs[library]


def main():
    scenario_map = get_github_workflow_map(
        os.environ["SCENARIOS"].split(","), os.environ["SCENARIOS_GROUPS"].split(",")
    )
    for github_workflow, scnearios in scenario_map.items():
        print(f"{github_workflow}_scenarios={json.dumps(scnearios)}")

    endtoend_weblogs = get_endtoend_weblogs(os.environ["LIBRARY"])
    print(f"endtoend_weblogs={json.dumps(endtoend_weblogs)}")


if __name__ == "__main__":
    main()
