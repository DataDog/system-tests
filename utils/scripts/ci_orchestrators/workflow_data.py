from collections import defaultdict
import json
import os
from pathlib import Path


def _load_json(file_path: str) -> dict:
    with open(file_path, "r") as file:
        return json.load(file)


def _get_weblog_spec(weblogs_spec: list[dict], weblog_name: str) -> dict:
    for entry in weblogs_spec:
        if weblog_name == entry["name"]:
            return entry
    raise ValueError(f"Weblog variant {weblog_name} not found (please aws_ssi.json)")


def get_k8s_matrix(k8s_ssi_file: str, scenarios: list[str], language: str) -> dict:
    """Computes the matrix "scenario" - "weblog" - "cluster agent" given a list of scenarios and a language."""
    k8s_ssi = _load_json(k8s_ssi_file)
    cluster_agent_specs = k8s_ssi["cluster_agent_spec"]

    results = defaultdict(lambda: defaultdict(list))  # type: dict
    scenario_matrix = k8s_ssi["scenario_matrix"]
    for entry in scenario_matrix:
        applicable_scenarios = entry["scenarios"]
        weblogs = entry["weblogs"]
        supported_cluster_agents = entry.get("cluster_agents", [])
        for scenario in scenarios:
            if scenario in applicable_scenarios:
                for weblog_entry in weblogs:
                    if language in weblog_entry:
                        for weblog in weblog_entry[language]:
                            if supported_cluster_agents:
                                for cluster_agent in supported_cluster_agents:
                                    if cluster_agent in cluster_agent_specs:
                                        results[scenario][weblog].append(cluster_agent_specs[cluster_agent])
                                    else:
                                        raise ValueError(f"Cluster agent {cluster_agent} not found in the k8s_ssi.json")
                            else:
                                results[scenario][weblog] = []
    return results


def get_k8s_injector_dev_matrix(k8s_injector_dev_file: str, scenarios: list[str], language: str) -> dict:
    """Computes the matrix "scenario" - "weblog" given a list of scenarios and a language."""
    k8s_injector_dev = _load_json(k8s_injector_dev_file)

    results = defaultdict(lambda: defaultdict(list))  # type: dict
    scenario_matrix = k8s_injector_dev["scenario_matrix"]
    for entry in scenario_matrix:
        applicable_scenarios = entry["scenarios"]
        weblogs = entry["weblogs"]
        for scenario in scenarios:
            if scenario in applicable_scenarios:
                for weblog_entry in weblogs:
                    if language in weblog_entry:
                        for weblog in weblog_entry[language]:
                            results[scenario][weblog] = []
    return results


def get_aws_matrix(virtual_machines_file: str, aws_ssi_file: str, scenarios: list[str], language: str) -> dict:
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


def get_docker_ssi_matrix(
    images_file: str, runtimes_file: str, docker_ssi_file: str, scenarios: list[str], language: str
) -> dict:
    """Load the JSON files (the docker imgs and runtimes supported by the system and the scenario-weblog definition)"""
    images = _load_json(images_file)
    runtimes = _load_json(runtimes_file)
    docker_ssi = _load_json(docker_ssi_file)
    results = defaultdict(lambda: defaultdict(list))  # type: dict

    scenario_matrix = docker_ssi.get("scenario_matrix", [])
    weblogs_spec = docker_ssi.get("weblogs_spec", {}).get(language)

    if not weblogs_spec:
        return results

    for entry in scenario_matrix:
        applicable_scenarios = set(entry.get("scenarios", []))
        weblogs = entry.get("weblogs", [])

        for scenario in scenarios:
            if scenario in applicable_scenarios:
                for weblog_entry in weblogs:
                    if language in weblog_entry:
                        for weblog in weblog_entry[language]:
                            weblog_spec = _get_weblog_spec(weblogs_spec, weblog)
                            supported_images = weblog_spec.get("supported_images", [])

                            for supported_image in supported_images:
                                allowed_runtimes = []
                                allowed_versions = supported_image.get("allowed_runtime_versions", [])

                                if not allowed_versions:
                                    allowed_runtimes.append("")
                                elif "*" in allowed_versions:
                                    allowed_runtimes.extend(
                                        runtime["version"]
                                        for runtime in runtimes["docker_ssi_runtimes"].get(language, [])
                                    )
                                else:
                                    runtime_map = {
                                        rt["version_id"]: rt["version"]
                                        for rt in runtimes["docker_ssi_runtimes"].get(language, [])
                                    }
                                    for runtime_id in allowed_versions:
                                        if runtime_id in runtime_map:
                                            allowed_runtimes.append(runtime_map[runtime_id])
                                        else:
                                            raise ValueError(f"Runtime {runtime_id} not found in the runtimes file")

                                image_reference, image_arch_reference = next(
                                    (
                                        (img["image"], img["architecture"])
                                        for img in images["docker_ssi_images"]
                                        if img["name"] == supported_image["name"]
                                    ),
                                )

                                if not image_reference:
                                    raise ValueError(f"Image {supported_image['name']} not found in the images file")

                                results[scenario][weblog].append(
                                    {image_reference: allowed_runtimes, "arch": image_arch_reference}
                                )

    return results


# End-to-end corner
class Job:
    """a job is a couple weblog/scenarios that will be executed in a single runner"""

    def __init__(
        self, library: str, weblog: str, weblog_instance: int, scenarios_times: dict[str, float], build_time: float
    ):
        self.library = library
        self.weblog = weblog

        # dict of scenario -> execution time of the scenario
        self._scenarios_times = scenarios_times

        # as a given weblog can have multiple runner executing its scenarios
        # weblog_instance will be used to differentiate them
        self.weblog_instance = weblog_instance

        # build_time is not directly tight to the job, as another runner will execute it
        # but it's convenient to store this info here, as we'll need it to execute the
        # split mechanism
        self.build_time = build_time

    def serialize(self) -> dict:
        return {
            "library": self.library,
            "weblog": self.weblog,
            "scenarios": sorted(self.scenarios),
            "weblog_instance": self.weblog_instance,
            "expected_job_time": self.expected_job_time + self.build_time,
        }

    @property
    def scenarios(self) -> tuple[str, ...]:
        return tuple(self._scenarios_times.keys())

    @property
    def expected_job_time(self) -> float:
        return sum(self._scenarios_times.values())

    @property
    def sort_key(self) -> tuple:
        return (self.weblog, self.weblog_instance)

    def get_scenario_time(self, scenario: str) -> float:
        return self._scenarios_times[scenario]

    def append_scenario(self, scenario: str, execution_time: float) -> None:
        assert scenario not in self._scenarios_times
        self._scenarios_times[scenario] = execution_time

    def split_for_parallel_execution(self, desired_execution_time: float) -> list["Job"]:
        result: list[Job] = []

        backpacks = _split_scenarios_for_parallel_execution(
            self._scenarios_times, desired_execution_time - self.build_time
        )
        for i, scenarios in enumerate(backpacks):
            result.append(
                Job(
                    library=self.library,
                    weblog=self.weblog,
                    weblog_instance=i + 1,
                    scenarios_times={scenario: self._scenarios_times[scenario] for scenario in scenarios},
                    build_time=self.build_time,
                )
            )

        return result


def _get_endtoend_weblogs(library: str, weblogs_filter: list[str]) -> list[str]:
    folder = f"utils/build/docker/{library}"
    result = [
        f.replace(".Dockerfile", "")
        for f in os.listdir(folder)
        if f.endswith(".Dockerfile") and ".base." not in f and Path(os.path.join(folder, f)).is_file()
    ]

    if len(weblogs_filter) != 0:
        # filter weblogs by the weblogs_filter set
        result = [weblog for weblog in result if weblog in weblogs_filter]

    return sorted(result)


def get_endtoend_definitions(
    library: str,
    scenario_map: dict,
    weblogs_filter: list[str],
    ci_environment: str,
    desired_execution_time: int,
    maximum_parallel_jobs: int,
) -> dict:
    scenarios = scenario_map["endtoend"]

    # get time stats
    with open("utils/scripts/ci_orchestrators/time-stats.json", "r") as file:
        time_stats = json.load(file)

    # get the list of end-to-end weblogs for the given library
    weblogs = _get_endtoend_weblogs(library, weblogs_filter)

    # check that jobs can be splitted
    assert maximum_parallel_jobs >= len(weblogs), "There are more weblogs than maximum_parallel_jobs"

    # build a list of {weblog, scenarios} for each weblog, and assign it to a Job
    jobs: list[Job] = []
    for weblog in weblogs:
        supported_scenarios = _filter_scenarios(scenarios, library, weblog, ci_environment)

        if len(supported_scenarios) > 0:  # remove weblogs with no scenarios
            scenarios_times = {
                scenario: _get_execution_time(library, weblog, scenario, time_stats["run"])
                for scenario in supported_scenarios
            }

            jobs.append(
                Job(
                    library=library,
                    weblog=weblog,
                    weblog_instance=1,
                    scenarios_times=scenarios_times,
                    build_time=_get_build_time(library, weblog, time_stats["build"]),
                )
            )

    # split those jobs into smaller jobs if needed

    if desired_execution_time > 0:  # 0 or less means that user doesn't want to split jobs
        jobs = _split_jobs_for_parallel_execution(jobs, desired_execution_time, maximum_parallel_jobs)

    # sort jobs by weblog name and weblog instance
    jobs.sort(key=lambda job: job.sort_key)

    return {
        "endtoend_defs": {
            "parallel_enable": len(jobs) > 0,
            "parallel_weblogs": sorted({job.weblog for job in jobs}),
            "parallel_jobs": [job.serialize() for job in jobs],
        }
    }


def _split_jobs_for_parallel_execution(
    jobs: list[Job], desired_execution_time: float, maximum_parallel_jobs: int
) -> list[Job]:
    result: list[Job] = []

    for job in jobs:
        result.extend(job.split_for_parallel_execution(desired_execution_time))

    while len(result) > maximum_parallel_jobs:
        # sort jobs by their weblog_instance
        # this way, we'll go through each weblog
        for job_to_delete in sorted(result, key=lambda job: job.weblog_instance, reverse=True):
            weblog_jobs = [j for j in result if j.weblog == job_to_delete.weblog]

            result.remove(job_to_delete)
            weblog_jobs.remove(job_to_delete)

            # and give its scenarios to the fastest job with the same weblog
            for scenario in job_to_delete.scenarios:
                # find the fastest job with the same weblog
                fastest_job = min(weblog_jobs, key=lambda x: x.expected_job_time)
                fastest_job.append_scenario(scenario, job_to_delete.get_scenario_time(scenario))

            if len(result) <= maximum_parallel_jobs:
                break

    return result


def _split_scenarios_for_parallel_execution(
    scenario_times: dict[str, float], desired_execution_time: float
) -> list[list[str]]:
    class BackPack:
        def __init__(self, scenario: str, execution_time: float):
            self.scenarios: list[str] = [scenario]
            self.execution_time: float = execution_time

    # First Fit Decreasing algorithm to split scenarios into backpacks
    # https://en.wikipedia.org/wiki/First-fit-decreasing_bin_packing
    sorted_scenarios = sorted(scenario_times.items(), key=lambda item: item[1], reverse=True)

    backpacks: list[BackPack] = []

    for scenario, execution_time in sorted_scenarios:
        if execution_time > desired_execution_time or len(backpacks) == 0:
            # if the scenario is too long, or if we don't have any backpack, create a new one
            backpacks.append(BackPack(scenario, execution_time))
        else:
            placed = False
            for backpack in backpacks:
                if backpack.execution_time + execution_time <= desired_execution_time:
                    # if the scenario fits in the backpack, add it
                    backpack.scenarios.append(scenario)
                    backpack.execution_time += execution_time
                    placed = True
                    break

            if not placed:
                # if the scenario doesn't fit in any backpack, create a new one
                backpacks.append(BackPack(scenario, execution_time))

    return [backpack.scenarios for backpack in backpacks]


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


def _is_supported(library: str, weblog: str, scenario: str, _ci_environment: str) -> bool:
    # this function will remove some couple scenarios/weblog that are not supported

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

    if scenario in ("APPSEC_MISSING_RULES", "APPSEC_CORRUPTED_RULES") and library in ("cpp_nginx", "cpp_httpd"):
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
        if scenario not in ("OTEL_INTEGRATIONS",):
            return False

    return True


if __name__ == "__main__":
    m = {
        "endtoend": [
            "AGENT_NOT_SUPPORTING_SPAN_EVENTS",
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
            "TRACE_PROPAGATION_STYLE_DEFAULT",
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

    get_endtoend_definitions("ruby", m, [], "dev", desired_execution_time=400, maximum_parallel_jobs=256)
