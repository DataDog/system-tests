from collections import defaultdict
import json
from utils._context._scenarios import Scenario
from utils._context.weblog_metadata import WeblogMetaData as Weblog
from utils._context.constants import WeblogBuildMode as BuildMode


def _load_json(file_path: str) -> dict:
    with open(file_path, "r") as file:
        return json.load(file)


def _get_weblog_spec(weblogs_spec: list[dict], weblog_name: str) -> dict:
    for entry in weblogs_spec:
        if weblog_name == entry["name"]:
            return entry
    raise ValueError(f"Weblog variant {weblog_name} not found (please aws_ssi.json)")


def get_k8s_matrix(k8s_ssi_file: str, scenarios: list[Scenario], language: str) -> dict:
    """Computes the K8s test matrix mapping scenarios to weblogs and their component versions.

    Args:
        k8s_ssi_file: Path to the k8s_ssi.json configuration file
        scenarios: List of scenario names to include in the matrix
        language: Programming language to filter weblogs (e.g., "nodejs", "java")

    Returns:
        Nested dictionary structure: {scenario: {weblog[]}}

    """
    k8s_config = _load_json(k8s_ssi_file)

    results: dict[str, list] = defaultdict(list)

    # Process each entry in the scenario matrix
    for matrix_entry in k8s_config["scenario_matrix"]:
        applicable_scenarios: list[str] = matrix_entry["scenarios"]
        weblogs: list[dict[str, list[str]]] = matrix_entry["weblogs"]

        # Match scenarios and weblogs
        for scenario in scenarios:
            if scenario.name not in applicable_scenarios:
                continue

            for weblog_entry in weblogs:
                if language not in weblog_entry:
                    continue

                for weblog in weblog_entry[language]:
                    results[scenario.name].append(weblog)

    return results


def get_k8s_injector_dev_matrix(
    k8s_injector_dev_file: str, scenarios: list[Scenario], language: str
) -> dict[str, list[str]]:
    """Computes the matrix "scenario" - "weblog" given a list of scenarios and a language."""
    k8s_injector_dev = _load_json(k8s_injector_dev_file)

    results = defaultdict(lambda: defaultdict(list))  # type: dict
    scenario_matrix: list[dict] = k8s_injector_dev["scenario_matrix"]
    for entry in scenario_matrix:
        applicable_scenarios: list[str] = entry["scenarios"]
        weblogs: list[dict[str, list[str]]] = entry["weblogs"]
        for scenario in scenarios:
            if scenario.name in applicable_scenarios:
                for weblog_entry in weblogs:
                    if language in weblog_entry:
                        for weblog in weblog_entry[language]:
                            results[scenario.name][weblog] = []
    return results


def get_aws_matrix(
    virtual_machines_file: str, aws_ssi_file: str, scenarios: list[Scenario], language: str
) -> dict[str, list[str]]:
    """Load the json files (the virtual_machine supported by the system  and the scenario-weblog definition)
    and calculates the matrix "scenario" - "weblog" - "virtual machine" given a list of scenarios and a language.
    """

    # Load the supported vms and the aws matrix definition
    raw_data_virtual_machines = _load_json(virtual_machines_file)["virtual_machines"]
    aws_ssi = _load_json(aws_ssi_file)
    # Remove items where "disabled" is set to True
    virtual_machines = [item for item in raw_data_virtual_machines if item.get("disabled") is not True]

    results = defaultdict(lambda: defaultdict(list))  # type: dict
    scenario_matrix: list[dict] = aws_ssi["scenario_matrix"]
    if language not in aws_ssi["weblogs_spec"]:
        return results
    weblogs_spec = aws_ssi["weblogs_spec"][language]

    for entry in scenario_matrix:
        applicable_scenarios: list[str] = entry["scenarios"]
        weblogs: list[dict[str, list[str]]] = entry["weblogs"]

        for scenario in scenarios:
            if scenario.name in applicable_scenarios:
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
                                    results[scenario.name][weblog].append(vm["name"])

    return results


def get_docker_ssi_matrix(
    images_file: str, runtimes_file: str, docker_ssi_file: str, scenarios: list[Scenario], language: str
) -> dict[str, list[str]]:
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
        applicable_scenarios: set[str] = set(entry.get("scenarios", []))
        weblogs: list[dict[str, list[str]]] = entry.get("weblogs", [])

        for scenario in scenarios:
            if scenario.name in applicable_scenarios:
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

                                results[scenario.name][weblog].append(
                                    {image_reference: allowed_runtimes, "arch": image_arch_reference}
                                )

    return results


# End-to-end corner


class Job:
    """a job is a couple weblog/scenarios that will be executed in a single runner"""

    def __init__(
        self,
        library: str,
        weblog: Weblog,
        weblog_instance: int,
        scenarios_times: dict[str, float],
        build_time: float,
        *,
        build_base_images: bool,
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

        self.build_base_images = build_base_images
        """ Shall the end-to-end scenario rebuild the weblog base image for fully baked weblog """

    def serialize(self) -> dict:
        return {
            "runs_on": "ubuntu-latest",
            "library": self.library,
            "weblog": self.weblog.name,
            "weblog_build_required": self.weblog.require_build,
            "weblog_instance": self.weblog_instance,
            "scenarios": sorted(self.scenarios),
            "expected_job_time": self.expected_job_time + self.build_time,
            "binaries_artifact": self.weblog.artifact_name,
            "build_weblog_base_image": self.weblog.build_mode == BuildMode.local
            and self.build_base_images
            and self.weblog.base_dockerfile is not None,
        }

    @property
    def scenarios(self) -> tuple[str, ...]:
        return tuple(self._scenarios_times.keys())

    @property
    def expected_job_time(self) -> float:
        return sum(self._scenarios_times.values())

    @property
    def sort_key(self) -> tuple:
        return (self.weblog.name, self.weblog_instance)

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
                    build_base_images=self.build_base_images,
                )
            )

        return result


def _get_endtoend_weblogs(
    library: str,
    weblogs_filter: list[str],
    unique_id: str,
    ci_environment: str,
    binaries_artifact: str,
) -> list[Weblog]:
    weblogs: list[Weblog] = Weblog.load(library)

    if len(weblogs_filter) != 0:
        # filter weblogs by the weblogs_filter set
        weblogs = [w for w in weblogs if w.name in weblogs_filter]

    for weblog in weblogs:
        weblog.artifact_name = (
            f"binaries_{ci_environment}_{library}_{weblog.name}_{unique_id}"
            if weblog.build_mode == "prebuild"
            else binaries_artifact
        )

    return sorted(weblogs, key=lambda w: w.name)


def get_endtoend_definitions(
    library: str,
    scenario_map: dict,
    weblogs_filter: list[str],
    ci_environment: str,
    desired_execution_time: int,
    maximum_parallel_jobs: int,
    unique_id: str,
    binaries_artifact: str,
    *,
    build_base_images: bool = False,
) -> dict:
    scenarios: list[Scenario] = scenario_map.get("endtoend", [])

    # get time stats
    with open("utils/scripts/ci_orchestrators/time-stats.json", "r") as file:
        time_stats = json.load(file)

    # get the list of end-to-end weblogs for the given library
    weblogs: list[Weblog] = _get_endtoend_weblogs(
        library,
        weblogs_filter,
        ci_environment=ci_environment,
        unique_id=unique_id,
        binaries_artifact=binaries_artifact,
    )

    # check that jobs can be splitted
    assert maximum_parallel_jobs >= len(weblogs), "There are more weblogs than maximum_parallel_jobs"

    # build a list of {weblog, scenarios} for each weblog, and assign it to a Job
    jobs: list[Job] = []
    for weblog in weblogs:
        supported_scenarios = _filter_scenarios(scenarios, weblog)

        if len(supported_scenarios) > 0:  # remove weblogs with no scenarios
            scenarios_times = {
                scenario.name: _get_execution_time(library, weblog.name, scenario.name, time_stats["run"])
                for scenario in supported_scenarios
            }

            jobs.append(
                Job(
                    library=library,
                    weblog=weblog,
                    weblog_instance=1,
                    scenarios_times=scenarios_times,
                    build_time=_get_build_time(library, weblog, time_stats["build"]),
                    build_base_images=build_base_images,
                )
            )

    # split those jobs into smaller jobs if needed

    if desired_execution_time > 0:  # 0 or less means that user doesn't want to split jobs
        jobs = _split_jobs_for_parallel_execution(jobs, desired_execution_time, maximum_parallel_jobs)

    # sort jobs by weblog name and weblog instance
    jobs.sort(key=lambda job: job.sort_key)

    weblogs = list({job.weblog.name: job.weblog for job in jobs}.values())
    weblogs.sort(key=lambda w: w.name)

    return {
        "endtoend_defs": {
            "parallel_enable": len(jobs) > 0,
            "parallel_weblogs": [
                _get_weblog_build_job(weblog, build_base_images=build_base_images)
                for weblog in weblogs
                if weblog.build_mode == BuildMode.prebuild
            ],
            "parallel_jobs": [job.serialize() for job in jobs],
        }
    }


def _get_weblog_build_job(weblog: Weblog, *, build_base_images: bool) -> dict:
    return {
        "name": weblog.name,
        "artifact_name": weblog.artifact_name,
        "build_base_images": build_base_images and weblog.base_dockerfile is not None,
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


def _get_build_time(library: str, weblog: Weblog, build_stats: dict) -> float:
    if weblog.build_mode != BuildMode.prebuild:
        return 0.0

    if library not in build_stats:
        return build_stats["*"]

    if weblog.name not in build_stats[library]:
        return build_stats[library]["*"]

    return build_stats[library][weblog.name]


def _get_execution_time(library: str, weblog: str, scenario: str, run_stats: dict) -> int | float:
    if scenario not in run_stats:
        return run_stats["*"]

    if library not in run_stats[scenario]:
        return run_stats[scenario]["*"]

    if weblog not in run_stats[scenario][library]:
        return run_stats[scenario][library]["*"]

    return run_stats[scenario][library][weblog]


def _filter_scenarios(scenarios: list[Scenario], weblog: Weblog) -> list[Scenario]:
    return sorted(
        [scenario for scenario in set(scenarios) if weblog.support_scenario(scenario.name, scenario.weblog_categories)],
        key=lambda scenario: scenario.name,
    )
    if scenario.name == "DEBUGGER_CAPTURE_TIMEOUT":
        possible_values: tuple[tuple[str, str], ...] = (
            ("dotnet", "poc"),
            ("dotnet", "uds"),
            ("java", "spring-boot"),
            ("java", "spring-boot-jetty"),
            ("java", "spring-boot-openliberty"),
            ("java", "spring-boot-payara"),
            ("java", "spring-boot-undertow"),
            ("java", "spring-boot-wildfly"),
            ("java", "uds-spring-boot"),
            ("nodejs", "express4"),
            ("nodejs", "express4-typescript"),
            ("nodejs", "express5"),
            ("nodejs", "fastify"),
            ("nodejs", "uds-express4"),
        )
        if (library, weblog_name) not in possible_values:
            return False



if __name__ == "__main__":
    from utils._context._scenarios import scenarios

    m = {
        "endtoend": [
            scenarios.agent_not_supporting_span_events,
            scenarios.apm_tracing_e2e_otel,
            scenarios.apm_tracing_otlp,
            scenarios.apm_tracing_e2e_single_span,
        ],
        "aws_ssi": [],
        "dockerssi": [scenarios.docker_ssi],
        "graphql": [scenarios.graphql_appsec],
        "libinjection": [
            scenarios.k8s_lib_injection,
            scenarios.k8s_lib_injection_no_ac,
            scenarios.k8s_lib_injection_no_ac_uds,
            scenarios.k8s_lib_injection_operator,
            scenarios.k8s_lib_injection_profiling_disabled,
            scenarios.k8s_lib_injection_profiling_enabled,
            scenarios.k8s_lib_injection_profiling_override,
            scenarios.k8s_lib_injection_spark_djm,
            scenarios.k8s_lib_injection_uds,
        ],
        "testthetest": [],
        "opentelemetry": [scenarios.otel_integrations],
        "parametric": [scenarios.parametric],
    }

    get_endtoend_definitions(
        "ruby",
        m,
        [],
        "dev",
        desired_execution_time=400,
        maximum_parallel_jobs=256,
        binaries_artifact="",
        unique_id="000",
    )
