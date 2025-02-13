from collections import defaultdict
import json
import os
from pathlib import Path


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


def _get_endtoend_weblogs(library: str) -> list[str]:
    folder = f"utils/build/docker/{library}"
    result = [
        f.replace(".Dockerfile", "")
        for f in os.listdir(folder)
        if f.endswith(".Dockerfile") and ".base." not in f and Path(os.path.join(folder, f)).is_file()
    ]

    return sorted(result)


def get_endtoend_definitions(library: str, scenario_map: dict, ci_environment: str) -> dict:
    if "otel" not in library:
        scenarios = scenario_map["endtoend"] + scenario_map["graphql"]
    else:
        scenarios = scenario_map["opentelemetry"]

    unfiltered_defs = [
        {
            "library": library,
            "weblog_name": weblog,
            "scenarios": _filter_scenarios(scenarios, library, weblog, ci_environment),
        }
        for weblog in _get_endtoend_weblogs(library)
    ]

    filtered_defs = [weblog for weblog in unfiltered_defs if len(weblog["scenarios"]) != 0]

    return {"endtoend_defs": {"weblogs": filtered_defs}}


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

    if scenario in ("OTEL_LOG_E2E", "OTEL_METRIC_E2E", "OTEL_TRACING_E2E"):
        if library not in ("java_otel",):
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

    if weblog == "spring-boot-otel":
        if scenario not in ("OTEL_INTEGRATIONS", "OTEL_LOG_E2E", "OTEL_METRIC_E2E", "OTEL_TRACING_E2E"):
            return False

    if weblog in ["express4-otel", "flask-poc-otel"]:
        if scenario not in ("OTEL_INTEGRATIONS"):
            return False

    return True
