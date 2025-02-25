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

def get_k8s_matrix(k8s_ssi_file, scenarios: list[str], language: str) -> dict:
    """ Computes the matrix "scenario" - "weblog" - "cluster agent" given a list of scenarios and a language.
    """
    k8s_ssi = _load_json(k8s_ssi_file)
    cluster_agent_specs = k8s_ssi["cluster_agent_spec"]
    
    results = defaultdict(lambda: defaultdict(list))  # type: dict
    scenario_matrix = k8s_ssi["scenario_matrix"]
    for entry in scenario_matrix:
        applicable_scenarios = entry["scenarios"]
        weblogs = entry["weblogs"]
        supported_cluster_agents = entry["cluster_agents"] if "cluster_agents" in entry else []
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
                                results[scenario][weblog].append([])
    return results
    
    
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


def get_docker_ssi_matrix(images_file, runtimes_file, docker_ssi_file, scenarios: list[str], language: str) -> dict:
    """Load the JSON files (the docker images and runtimes supported by the system and the scenario-weblog definition)
    """
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

                                image_reference,image_arch_reference = next(
                                    (
                                        (img["image"],img["architecture"])
                                        for img in images["docker_ssi_images"]
                                        if img["name"] == supported_image["name"]
                                    ),
                                    None,
                                )

                                if not image_reference:
                                    raise ValueError(f"Image {supported_image['name']} not found in the images file")

                                results[scenario][weblog].append({image_reference: allowed_runtimes, "arch":image_arch_reference})

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
