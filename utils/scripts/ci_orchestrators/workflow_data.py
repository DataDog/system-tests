from collections import defaultdict
import json


def _load_json(file_path) -> dict:
    with open(file_path, "r") as file:
        return json.load(file)


def _get_weblog_spec(weblogs_spec, weblog_name) -> dict:
    for entry in weblogs_spec:
        if weblog_name == entry["name"]:
            return entry
    raise ValueError(f"Weblog variant {weblog_name} not found (please aws_ssi.json)")


def get_aws_matrix(virtual_machines_file, aws_ssi_file, scenarios: list[str], language: str) -> dict:
    """Load the json files (the virtual_machine supported by the system  and the scenario-weblog definition)
    and calculates the matrix "scenario" - "weblog" - "virtual machine" given a list of scenarios and a language.
    """

    # Load the supported vms and the aws matrix definition
    raw_data_virtual_machines = _load_json(virtual_machines_file)["virtual_machines"]
    aws_ssi = _load_json(aws_ssi_file)
    # Remove items where "disabled" is set to True
    virtual_machines = [item for item in raw_data_virtual_machines if item.get("disabled") is not True]

    results = defaultdict(lambda: defaultdict(list))  # type: dict
    scenario_matrix = aws_ssi["scenario_matrix"]
    if language not in aws_ssi["weblogs_spec"]:
        return results
    weblogs_spec = aws_ssi["weblogs_spec"][language]

    for entry in scenario_matrix:
        applicable_scenarios = entry["scenarios"]
        weblogs = entry["weblogs"]

        for scenario in scenarios:
            if scenario in applicable_scenarios:
                for weblog_entry in weblogs:
                    if language in weblog_entry:
                        for weblog in weblog_entry[language]:
                            weblog_spec = _get_weblog_spec(weblogs_spec, weblog)
                            excluded = set(weblog_spec.get("excluded_os_branches", []))
                            exact = set(weblog_spec.get("exact_os_branches", []))
                            excluded_names = set(weblog_spec.get("excluded_os_names", []))

                            for vm in virtual_machines:
                                should_add_vm = True
                                os_branch = vm["os_branch"]
                                os_name = vm["name"]
                                if exact:
                                    if os_branch not in exact:
                                        # results[scenario][weblog].append(vm["name"])
                                        should_add_vm = False
                                if excluded:
                                    if os_branch in excluded:
                                        should_add_vm = False
                                if excluded_names:
                                    if os_name in excluded_names:
                                        should_add_vm = False

                                if should_add_vm:
                                    results[scenario][weblog].append(vm["name"])

    return results


def _get_graphql_weblogs(library) -> list[str]:
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


def _get_endtoend_weblogs(library, ci_environment: str) -> list[str]:
    weblogs: dict[str, list[str]] = {
        "cpp": ["nginx"],
        "dotnet": ["poc", "uds"],
        "golang": [
            "chi",
            "echo",
            "gin",
            "net-http",
            "uds-echo",
            "net-http-orchestrion",
            "gqlgen",
            "graph-gophers",
            "graphql-go",
        ],
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


def _get_opentelemetry_weblogs(library) -> list[str]:
    weblogs: dict[str, list[str]] = {
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


def get_endtoend_matrix(language: str, scenario_map: dict, ci_environment: str) -> dict:
    result = defaultdict(dict)  # type: dict[str, dict]

    for github_workflow, scenario_list in scenario_map.items():
        result[github_workflow]["scenarios"] = scenario_list

    result["endtoend"]["weblogs"] = _get_endtoend_weblogs(language, ci_environment)
    result["graphql"]["weblogs"] = _get_graphql_weblogs(language)
    result["opentelemetry"]["weblogs"] = _get_opentelemetry_weblogs(language)

    return result


def get_endtoend_definitions(library: str, scenario_map: dict, ci_environment: str) -> dict:
    endtoend_scenarios = scenario_map["endtoend"] + scenario_map["graphql"]
    opentelemetry_scenarios = scenario_map["opentelemetry"]

    weblogs = [
        {
            "library": library,
            "weblog_name": weblog,
            "scenarios": _filter_scenarios(endtoend_scenarios, library, weblog, ci_environment),
        }
        for weblog in _get_endtoend_weblogs(library, ci_environment)
    ] + [
        {
            "library": f"{library}_otel",
            "weblog_name": weblog,
            "scenarios": _filter_scenarios(opentelemetry_scenarios, f"{library}_otel", weblog, ci_environment),
        }
        for weblog in _get_opentelemetry_weblogs(library)
    ]

    return {"endtoend_defs": {"weblogs": [weblog for weblog in weblogs if len(weblog["scenarios"]) != 0]}}


def _filter_scenarios(scenarios: list[str], library: str, weblog: str, ci_environment: str) -> list[str]:
    return sorted([scenario for scenario in set(scenarios) if _is_supported(library, weblog, scenario, ci_environment)])


def _is_supported(library: str, weblog: str, scenario: str, ci_environment: str) -> bool:
    # this function will remove some couple scenarios/weblog that are not supported
    if ci_environment != "dev" and library == "python" and weblog == "django-py3.13":
        # as now, django-py3.13 support is not released
        return False

    if scenario == "OTEL_INTEGRATIONS":
        if library not in ("java_otel", "python_otel", "nodejs_otel"):
            return False
        if ci_environment == "dev":
            return False

    if scenario in ("OTEL_LOG_E2E", "OTEL_METRIC_E2E", "OTEL_TRACING_E2E"):
        if library not in ("java_otel",):
            return False
        if ci_environment == "dev":
            return False

    if scenario in ("GRAPHQL_APPSEC",):
        possible_values = (
            ("golang", "gqlgen"),
            ("golang", "graph-gophers"),
            ("golang", "graphql-go"),
            ("ruby", "graphql23"),
            ("nodejs", "express4"),
            ("nodejs", "uds-express4"),
            ("nodejs", "express4-typescript"),
            ("nodejs", "express5"),
        )
        if (library, weblog) not in possible_values:
            return False

    if scenario in ("PERFORMANCES",):
        return False

    if scenario == "IPV6" and library == "ruby":
        return False

    if scenario in ("CROSSED_TRACING_LIBRARIES",):
        if weblog in ("python3.12", "django-py3.13", "spring-boot-payara"):
            # python 3.13 issue : APMAPI-1096
            return False

    if scenario in ("APPSEC_MISSING_RULES", "APPSEC_CORRUPTED_RULES") and library == "cpp":
        # C++ 1.2.0 freeze when the rules file is missing
        return False

    if weblog in ["gqlgen", "graph-gophers", "graphql-go", "graphql23"]:
        if scenario not in ("GRAPHQL_APPSEC",):
            return False

    if weblog in ["spring-boot-otel", "express4-otel", "flask-poc-otel"]:
        if scenario not in ("OTEL_LOG_E2E", "OTEL_METRIC_E2E", "OTEL_TRACING_E2E"):
            return False

    return True
