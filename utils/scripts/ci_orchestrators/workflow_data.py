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
                            excludes_types = set(weblog_spec.get("excluded_os_types", []))

                            for vm in virtual_machines:
                                should_add_vm = True
                                os_type = vm["os_type"]
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
                                if excludes_types:
                                    if os_type in excludes_types:
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


def get_endtoend_definitions(
    library: str, scenario_map: dict, ci_environment: str, desired_execution_time: int, maximum_parallel_jobs: int
) -> dict:
    if "otel" not in library:
        scenarios = scenario_map["endtoend"] + scenario_map["graphql"]
    else:
        scenarios = scenario_map["opentelemetry"]

    # get the list of end-to-end weblogs for the given library
    weblogs = _get_endtoend_weblogs(library)

    # build a list of {weblog_name, scenarios} for each weblog
    unfiltered_jobs = [
        {
            "library": library,
            "weblog_name": weblog,
            "scenarios": _filter_scenarios(scenarios, library, weblog, ci_environment),
        }
        for weblog in weblogs
    ]

    # remove weblogs with no scenarios
    filtered_jobs = [weblog for weblog in unfiltered_jobs if len(weblog["scenarios"]) != 0]

    # split those jobs into smaller jobs
    parallelized_jobs = _split_jobs_for_parallel_execution(
        weblogs, filtered_jobs, desired_execution_time, maximum_parallel_jobs
    )

    return {
        "endtoend_defs": {
            "parallel_enable": len(parallelized_jobs) > 0,
            "parallel_weblog_names": sorted({i["weblog_name"] for i in parallelized_jobs}),
            "parallel_jobs": sorted(
                parallelized_jobs, key=lambda job: (job["weblog_name"], job["weblog_name_instance"])
            ),  # TODO rename
        }
    }


def _split_jobs_for_parallel_execution(
    weblogs: list[str], jobs: list[dict], desired_execution_time: float, maximum_parallel_jobs: int
) -> list[dict]:
    result = []

    # if desired_execution_time is 0 or below, it indicates that we don't want to split the scenarios
    if desired_execution_time <= 0:
        desired_execution_time = float("inf")

    with open("utils/scripts/ci_orchestrators/time-stats.json", "r") as file:
        time_stats = json.load(file)

    for job in jobs:
        build_time = _get_build_time(job["library"], job["weblog_name"], time_stats["build"])
        scenario_times = {
            scenario: _get_execution_time(job["library"], job["weblog_name"], scenario, time_stats["run"])
            for scenario in job["scenarios"]
        }

        for i, (scenarios, expected_job_time) in enumerate(
            _split_scenarios_for_parallel_execution(scenario_times, desired_execution_time - build_time)
        ):
            result.append(
                {
                    "library": job["library"],
                    "weblog_name": job["weblog_name"],
                    "weblog_name_instance": i,
                    "scenarios": scenarios,
                    "expected_job_time": expected_job_time + build_time,
                }
            )

    assert maximum_parallel_jobs >= len(weblogs), "There are more weblogs than maximum_parallel_jobs"

    while len(result) > maximum_parallel_jobs:
        # sort jobs by their weblog_name_instance
        # this way, we'll go through each weblog
        for job_to_delete in sorted(result, key=lambda x: x["weblog_name_instance"], reverse=True):
            weblog_jobs = [j for j in result if j["weblog_name"] == job_to_delete["weblog_name"]]

            result.remove(job_to_delete)
            weblog_jobs.remove(job_to_delete)

            # and give its scenarios to the fastest job with the same weblog
            for scenario in job_to_delete["scenarios"]:
                # find the fastest job with the same weblog
                fastest_job = min(weblog_jobs, key=lambda x: x["expected_job_time"])
                fastest_job["scenarios"].append(scenario)
                fastest_job["expected_job_time"] += scenario_times[scenario]

            if len(result) <= maximum_parallel_jobs:
                break

    return result


def _split_scenarios_for_parallel_execution(scenario_times: dict[str, float], desired_execution_time: float):
    total_execution_time = sum(scenario_times.values())
    backpack_count = int(total_execution_time / desired_execution_time) + 1
    backpack_average_time = total_execution_time / backpack_count

    backpack: list[str] = []
    backpack_time = 0.0

    for scenario, execution_time in scenario_times.items():
        backpack.append(scenario)
        backpack_time += execution_time

        if backpack_time > backpack_average_time:
            yield backpack, backpack_time

            backpack = []
            backpack_time = 0

    if len(backpack) > 0:
        yield backpack, backpack_time


def _get_build_time(library: str, weblog: str, build_stats: dict) -> float:
    if library not in build_stats:
        return build_stats["*"]

    if weblog not in build_stats[library]:
        return build_stats[library]["*"]

    return build_stats[library][weblog]


def _get_execution_time(library: str, weblog: str, scenario: str, run_stats: dict) -> int | float:
    if scenario not in run_stats:
        return run_stats["*"]

    if library not in run_stats[scenario]:
        return run_stats[scenario]["*"]

    if weblog not in run_stats[scenario][library]:
        return run_stats[scenario][library]["*"]

    return run_stats[scenario][library][weblog]


def _filter_scenarios(scenarios: list[str], library: str, weblog: str, ci_environment: str) -> list[str]:
    return sorted([scenario for scenario in set(scenarios) if _is_supported(library, weblog, scenario, ci_environment)])


def _is_supported(library: str, weblog: str, scenario: str, ci_environment: str) -> bool:
    # this function will remove some couple scenarios/weblog that are not supported
    if ci_environment != "dev" and library == "python" and weblog == "django-py3.13":
        # as now, django-py3.13 support is not released
        return False

    # open-telemetry-automatic
    if scenario == "OTEL_INTEGRATIONS":
        possible_values: tuple = (
            ("java_otel", "spring-boot-otel"),
            ("nodejs_otel", "express4-otel"),
            ("python_otel", "flask-poc-otel"),
        )
        if (library, weblog) not in possible_values:
            return False

    # open-telemetry-manual
    if scenario in ("OTEL_LOG_E2E", "OTEL_METRIC_E2E", "OTEL_TRACING_E2E"):
        if (library, weblog) != ("java_otel", "spring-boot-native"):
            return False

    if scenario in ("GRAPHQL_APPSEC",):
        possible_values: tuple = (
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

    # open-telemetry-manual
    if weblog == "spring-boot-native":
        if scenario not in ("OTEL_LOG_E2E", "OTEL_METRIC_E2E", "OTEL_TRACING_E2E"):
            return False

    # open-telemetry-automatic
    if weblog in ["express4-otel", "flask-poc-otel", "spring-boot-otel"]:
        if scenario not in ("OTEL_INTEGRATIONS"):
            return False

    return True


if __name__ == "__main__":
    m = {
        "endtoend": [
            "AGENT_NOT_SUPPORTING_SPAN_EVENTS",
            "APM_TRACING_E2E",
            "APM_TRACING_E2E_OTEL",
            "APM_TRACING_E2E_SINGLE_SPAN",
            "APPSEC_API_SECURITY",
            "APPSEC_API_SECURITY_NO_RESPONSE_BODY",
            "APPSEC_API_SECURITY_RC",
            "APPSEC_API_SECURITY_WITH_SAMPLING",
            "APPSEC_AUTO_EVENTS_EXTENDED",
            "APPSEC_AUTO_EVENTS_RC",
            "APPSEC_BLOCKING",
            "APPSEC_BLOCKING_FULL_DENYLIST",
            "APPSEC_CORRUPTED_RULES",
            "APPSEC_CUSTOM_OBFUSCATION",
            "APPSEC_CUSTOM_RULES",
            "APPSEC_LOW_WAF_TIMEOUT",
            "APPSEC_META_STRUCT_DISABLED",
            "APPSEC_MISSING_RULES",
            "APPSEC_NO_STATS",
            "APPSEC_RASP",
            "APPSEC_RASP_NON_BLOCKING",
            "APPSEC_RATE_LIMITER",
            "APPSEC_REQUEST_BLOCKING",
            "APPSEC_RULES_MONITORING_WITH_ERRORS",
            "APPSEC_RUNTIME_ACTIVATION",
            "APPSEC_STANDALONE",
            "APPSEC_STANDALONE_V2",
            "APPSEC_WAF_TELEMETRY",
            "CROSSED_TRACING_LIBRARIES",
            "DEBUGGER_EXCEPTION_REPLAY",
            "DEBUGGER_EXPRESSION_LANGUAGE",
            "DEBUGGER_INPRODUCT_ENABLEMENT",
            "DEBUGGER_PII_REDACTION",
            "DEBUGGER_PROBES_SNAPSHOT",
            "DEBUGGER_PROBES_STATUS",
            "DEBUGGER_SYMDB",
            "DEFAULT",
            "EVERYTHING_DISABLED",
            "IAST_DEDUPLICATION",
            "IAST_STANDALONE",
            "IAST_STANDALONE_V2",
            "INTEGRATIONS",
            "INTEGRATIONS_AWS",
            "IPV6",
            "LIBRARY_CONF_CUSTOM_HEADER_TAGS",
            "LIBRARY_CONF_CUSTOM_HEADER_TAGS_INVALID",
            "PERFORMANCES",
            "PROFILING",
            "REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD",
            "REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD_NOCACHE",
            "REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES",
            "REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES_NOCACHE",
            "REMOTE_CONFIG_MOCKED_BACKEND_LIVE_DEBUGGING",
            "RUNTIME_METRICS_ENABLED",
            "SAMPLING",
            "SCA_STANDALONE",
            "SCA_STANDALONE_V2",
            "TELEMETRY_APP_STARTED_PRODUCTS_DISABLED",
            "TELEMETRY_DEPENDENCY_LOADED_TEST_FOR_DEPENDENCY_COLLECTION_DISABLED",
            "TELEMETRY_LOG_GENERATION_DISABLED",
            "TELEMETRY_METRIC_GENERATION_DISABLED",
            "TELEMETRY_METRIC_GENERATION_ENABLED",
            "TRACE_PROPAGATION_STYLE_W3C",
            "TRACING_CONFIG_EMPTY",
            "TRACING_CONFIG_NONDEFAULT",
            "TRACING_CONFIG_NONDEFAULT_2",
            "TRACING_CONFIG_NONDEFAULT_3",
        ],
        "aws_ssi": [],
        "dockerssi": ["DOCKER_SSI"],
        "externalprocessing": [],
        "graphql": ["GRAPHQL_APPSEC"],
        "libinjection": [
            "K8S_LIB_INJECTION",
            "K8S_LIB_INJECTION_NO_AC",
            "K8S_LIB_INJECTION_NO_AC_UDS",
            "K8S_LIB_INJECTION_OPERATOR",
            "K8S_LIB_INJECTION_PROFILING_DISABLED",
            "K8S_LIB_INJECTION_PROFILING_ENABLED",
            "K8S_LIB_INJECTION_PROFILING_OVERRIDE",
            "K8S_LIB_INJECTION_SPARK_DJM",
            "K8S_LIB_INJECTION_UDS",
            "LIB_INJECTION_VALIDATION",
            "LIB_INJECTION_VALIDATION_UNSUPPORTED_LANG",
        ],
        "testthetest": [],
        "opentelemetry": ["OTEL_INTEGRATIONS", "OTEL_LOG_E2E", "OTEL_METRIC_E2E", "OTEL_TRACING_E2E"],
        "parametric": ["PARAMETRIC"],
    }

    get_endtoend_definitions("java", m, "dev", 20, 256)
