from collections import defaultdict


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
    }  # type: dict[str, list[str]]

    return weblogs[library]


def get_endtoend_weblogs(library, ci_environment: str) -> list[str]:
    weblogs = {
        "cpp": ["nginx"],
        "dotnet": ["poc", "uds"],
        "golang": ["chi", "echo", "gin", "net-http", "uds-echo", "net-http-orchestrion"],
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
    }  # type: dict[str, list[str]]

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
    }  # type: dict[str, list[str]]

    return weblogs[library]


def get_endtoend_matrix(language: str, scenario_map: dict, parametric_job_count: int, ci_environment: str) -> dict:
    result = defaultdict(dict)  # type: dict[str, dict]

    for github_workflow, scenario_list in scenario_map.items():
        result[github_workflow]["scenarios"] = scenario_list

    result["endtoend"]["weblogs"] = get_endtoend_weblogs(language, ci_environment)
    result["graphql"]["weblogs"] = get_graphql_weblogs(language)
    result["opentelemetry"]["weblogs"] = get_opentelemetry_weblogs(language)
    result["parametric"]["job_count"] = parametric_job_count
    result["parametric"]["job_matrix"] = list(range(1, parametric_job_count + 1))

    return result
