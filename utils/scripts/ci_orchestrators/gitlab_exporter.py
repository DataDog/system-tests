import os
import yaml
import hashlib
import json
from utils._context._scenarios import get_all_scenarios
from utils._context._scenarios.core import Scenario
from utils.k8s.k8s_components_parser import K8sComponentsParser


def _generate_unique_prefix(scenario_specs_matrix: dict, prefix_length: int = 3) -> dict:
    """Generate a unique prefix for each scenario name/stage
    collect all the possible scenarios to generate unique prefixes for each scenario
    we will add the prefix to the job name to avoid jobs with the same name and different stages
    """

    scenarios_prefix_names = {}
    for scenario, _weblogs in scenario_specs_matrix.items():  # noqa: PERF102
        scenarios_prefix_names[scenario] = ""

    scenario_names = scenarios_prefix_names.keys()
    unique_prefixes = {}
    used_prefixes = set()

    for scenario in scenario_names:
        # Take the first `prefix_length` letters as the initial prefix
        prefix = scenario[:prefix_length].upper()

        # If the prefix is already used, generate a new one
        if prefix in used_prefixes:
            # Use a short hash as a backup unique identifier
            hash_suffix = hashlib.md5(scenario.encode()).hexdigest()[:2].upper()
            prefix = prefix[: prefix_length - 1] + hash_suffix  # Ensure total length is 3-4

        # Store the unique prefix
        unique_prefixes[scenario] = prefix
        used_prefixes.add(prefix)

    return unique_prefixes


def should_run_only_defaults_vm() -> bool:
    """Default rules to run only default VMs or all VMs"""
    # Get gitlab variables from the environment
    ci_commit_tag = os.getenv("CI_COMMIT_TAG")
    ci_commit_branch = os.getenv("CI_COMMIT_BRANCH")
    ci_project_name = os.getenv("CI_PROJECT_NAME")
    ci_pipeline_source = os.getenv("CI_PIPELINE_SOURCE")

    # If it is a scheduled pipeline or tag generation, we should run all the VMs always
    # it doesn't matter the project pipeline
    if ci_pipeline_source == "schedule" or ci_commit_tag:
        return False

    # if we run on system-tests repository and it's the main branch, we should run all the VMs
    return not (ci_project_name == "system-tests" and ci_commit_branch == "main")


def is_default_machine(raw_data_virtual_machines: list[dict], vm: str) -> bool:
    return any(vm_data["name"] == vm and vm_data["default_vm"] for vm_data in raw_data_virtual_machines)


def print_gitlab_pipeline(language: str, matrix_data: dict[str, dict], ci_environment: str) -> None:
    # Print all supported pipelines
    print_ssi_gitlab_pipeline(language, matrix_data, ci_environment)


def print_ssi_gitlab_pipeline(language: str, matrix_data: dict[str, dict], ci_environment: str) -> None:
    result_pipeline = {}  # type: dict
    result_pipeline["include"] = []
    result_pipeline["stages"] = []
    pipeline_file = ".gitlab/ssi_gitlab-ci.yml"
    pipeline_data = None

    with open(pipeline_file, encoding="utf-8") as f:
        pipeline_data = yaml.load(f, Loader=yaml.FullLoader)  # noqa: S506
    result_pipeline["include"] = pipeline_data["include"]
    result_pipeline["variables"] = pipeline_data["variables"]
    if (
        not matrix_data["aws_ssi_scenario_defs"]
        and not matrix_data["dockerssi_scenario_defs"]
        and not matrix_data["libinjection_scenario_defs"]
    ):
        result_pipeline["stages"].append("SSI_TESTS")
        result_pipeline["ssi_tests"] = pipeline_data["ssi_tests"]

    if matrix_data["aws_ssi_scenario_defs"]:
        # Copy the base job for the onboarding system tests
        result_pipeline[".base_job_onboarding_system_tests"] = pipeline_data[".base_job_onboarding_system_tests"]
        if os.getenv("CI_PROJECT_NAME") != "system-tests":
            if os.getenv("SYSTEM_TESTS_REF"):
                result_pipeline[".base_job_onboarding_system_tests"]["script"].insert(
                    0, f"git checkout {os.getenv('SYSTEM_TESTS_REF')}"
                )
            result_pipeline[".base_job_onboarding_system_tests"]["script"].insert(0, "cd system-tests")
            result_pipeline[".base_job_onboarding_system_tests"]["script"].insert(
                0, "git clone https://git@github.com/DataDog/system-tests.git system-tests"
            )
        print_aws_gitlab_pipeline(language, matrix_data["aws_ssi_scenario_defs"], ci_environment, result_pipeline)
    if matrix_data["dockerssi_scenario_defs"]:
        # Copy the base job for the docker ssi system tests
        result_pipeline[".base_docker_ssi_job"] = pipeline_data[".base_docker_ssi_job"]
        print_docker_ssi_gitlab_pipeline(
            language, matrix_data["dockerssi_scenario_defs"], ci_environment, result_pipeline
        )
    if matrix_data["libinjection_scenario_defs"]:
        # Copy the base job for the k8s lib injection system tests
        result_pipeline[".k8s_lib_injection_base"] = pipeline_data[".k8s_lib_injection_base"]
        if os.getenv("CI_PROJECT_NAME") != "system-tests":
            if os.getenv("SYSTEM_TESTS_REF"):
                result_pipeline[".k8s_lib_injection_base"]["script"].insert(
                    0, f"git checkout {os.getenv('SYSTEM_TESTS_REF')}"
                )
                result_pipeline[".k8s_lib_injection_base"]["script"].insert(0, "git pull")
            result_pipeline[".k8s_lib_injection_base"]["script"].insert(0, "cd /system-tests")

        print_k8s_gitlab_pipeline(language, matrix_data["libinjection_scenario_defs"], ci_environment, result_pipeline)

    pipeline_yml = yaml.dump(result_pipeline, sort_keys=False, default_flow_style=False)
    output_file = f"{language}_ssi_gitlab_pipeline.yml"
    with open(output_file, "w") as file:
        file.write(pipeline_yml)
    print("Pipeline file generated: ", output_file)


def get_k8s_scenario_components(
    scenario: str, all_system_tests_scenarios: list[Scenario], language: str
) -> dict[str, str | list[str]]:
    """Determine K8s component versions for a given scenario and CI context.

    This method selects the appropriate component versions based on:
    - The scenario requirements (operator, cluster agent)
    - The CI pipeline context (system-tests (scheduled or pr/commit) or tracer repo or injector repo)
    - Custom image overrides from environment variables

    Version Selection Logic:
    ========================

    For each component, versions are selected based on pipeline context:

    1. **Custom Image (Highest Priority)**
       - If K8S_LIB_INIT_IMG or K8S_INJECTOR_IMG env vars are set
       - Uses the custom image directly (injector/tracer repo testing)
       - The rest of the components are the pinned/default versions

    2. **System-Tests Scheduled Pipeline**
       - Tests ALL available versions (prod, dev, pinned)

    3. **System-Tests PR/Commit**
       - Tests ALL available versions (for injector and lib init)
       - Tests only the pinned versions for the rest of the components


    Component Versions Returned:
    ============================
    - K8S_HELM_CHART_OPERATOR: Datadog operator helm chart version (if with_datadog_operator)
    - K8S_CLUSTER_IMG: Cluster agent image (if with_cluster_agent)
    - K8S_INJECTOR_IMG: APM injector image (if with_cluster_agent)
    - K8S_HELM_CHART: Datadog helm chart version (if cluster agent without operator)
    - K8S_LIB_INIT_IMG: Library init container image (always included)

    Args:
        scenario: Scenario name (must exist in utils/_context/_scenarios/__init__.py)
        all_system_tests_scenarios: List of all available scenarios
        language: Programming language (java, python, nodejs, etc.)

    Returns:
        Dictionary with component version assignments for GitLab CI matrix

    """
    # Load all valid scenarios from the scenarios module
    all_valid_scenarios = {s.name for s in all_system_tests_scenarios}

    if scenario not in all_valid_scenarios:
        raise ValueError(
            f"Scenario '{scenario}' not found in utils/_context/_scenarios/__init__.py. "
            f"Please ensure the scenario is properly defined."
        )

    # Extract environment variables for CI context
    ci_project_name = os.getenv("CI_PROJECT_NAME")
    ci_pipeline_source = os.getenv("CI_PIPELINE_SOURCE")
    k8s_injector_img = os.getenv("K8S_INJECTOR_IMG")
    k8s_lib_init_img = os.getenv("K8S_LIB_INIT_IMG")

    # Determine CI context
    is_system_tests = ci_project_name == "system-tests"
    is_system_tests_scheduled = is_system_tests and ci_pipeline_source == "schedule"

    # Get scenario configuration
    scenario_obj = next((s for s in all_system_tests_scenarios if s.name == scenario), None)
    with_datadog_operator = getattr(scenario_obj, "with_datadog_operator", False)
    with_cluster_agent = getattr(scenario_obj, "with_cluster_agent", False)

    # Initialize component parser and result
    parser = K8sComponentsParser()
    components = {}

    # Datadog Operator scenario: requires operator helm chart
    if with_datadog_operator:
        components["K8S_HELM_CHART_OPERATOR"] = (
            parser.get_all_component_versions("helm_chart_operator")
            if is_system_tests_scheduled
            else parser.get_default_component_version("helm_chart_operator")
        )

    # Cluster Agent scenarios: require cluster agent and injector
    if with_cluster_agent:
        components["K8S_CLUSTER_IMG"] = (
            parser.get_all_component_versions("cluster_agent")
            if is_system_tests_scheduled
            else parser.get_default_component_version("cluster_agent")
        )

        components["K8S_INJECTOR_IMG"] = k8s_injector_img or (
            parser.get_all_component_versions("injector")
            if is_system_tests
            else parser.get_default_component_version("injector")
        )

    # Non-operator cluster scenarios: require standard helm chart
    if with_cluster_agent and not with_datadog_operator:
        components["K8S_HELM_CHART"] = (
            parser.get_all_component_versions("helm_chart")
            if is_system_tests_scheduled
            else parser.get_default_component_version("helm_chart")
        )

    # Library init: required for all scenarios
    components["K8S_LIB_INIT_IMG"] = k8s_lib_init_img or (
        parser.get_all_component_versions("lib_init", language)
        if is_system_tests
        else parser.get_default_component_version("lib_init", language)
    )

    return components


def print_k8s_gitlab_pipeline(
    language: str, k8s_matrix: dict[str, dict], ci_environment: str, result_pipeline: dict
) -> None:
    result_pipeline["stages"].append("K8S_LIB_INJECTION")
    all_system_tests_scenarios = get_all_scenarios()
    # Create the jobs by scenario.
    for scenario, weblogs in k8s_matrix.items():
        job = scenario
        result_pipeline[job] = {}
        result_pipeline[job]["extends"] = ".k8s_lib_injection_base"
        # Job variables
        result_pipeline[job]["variables"] = {}
        result_pipeline[job]["variables"]["TEST_LIBRARY"] = language
        result_pipeline[job]["variables"]["K8S_SCENARIO"] = scenario
        result_pipeline[job]["variables"]["REPORT_ENVIRONMENT"] = ci_environment

        result_pipeline[job]["parallel"] = {"matrix": []}
        for weblog_name in weblogs:
            k8s_weblog_img = os.getenv("K8S_WEBLOG_IMG", "${PRIVATE_DOCKER_REGISTRY}" + f"/system-tests/{weblog_name}")

            # Build matrix entry - only include components that have values
            matrix_entry = {
                "K8S_WEBLOG": weblog_name,
                "K8S_WEBLOG_IMG": k8s_weblog_img,
            }
            matrix_entry.update(get_k8s_scenario_components(scenario, all_system_tests_scenarios, language))

            result_pipeline[job]["parallel"]["matrix"].append(matrix_entry)


def print_docker_ssi_gitlab_pipeline(
    language: str, docker_ssi_matrix: dict, ci_environment: str, result_pipeline: dict
) -> None:
    # Special filters from env variables
    dd_installer_library_version = os.getenv("DD_INSTALLER_LIBRARY_VERSION")
    dd_installer_injector_version = os.getenv("DD_INSTALLER_INJECTOR_VERSION")
    if not dd_installer_library_version:
        dd_installer_library_version = os.getenv(f"DD_INSTALLER_LIBRARY_VERSION_{language.upper()}")
    scenarios_prefix_names = _generate_unique_prefix(docker_ssi_matrix)
    # Create the jobs by scenario.
    for scenario, weblogs in docker_ssi_matrix.items():
        result_pipeline["stages"].append(scenario)
        for weblog_name, images in weblogs.items():
            # Get the different architectures
            architectures = set()
            for image in images:
                architectures.add(image["arch"])

            for architecture in architectures:
                vm_job = weblog_name + "." + architecture.replace("linux/", "") + "." + scenarios_prefix_names[scenario]
                result_pipeline[vm_job] = {}
                result_pipeline[vm_job]["stage"] = scenario
                result_pipeline[vm_job]["extends"] = ".base_docker_ssi_job"
                result_pipeline[vm_job]["tags"] = [
                    f"{'docker-in-docker:amd64' if architecture == 'linux/amd64' else 'docker-in-docker:microvm-arm64'}"
                ]
                # Job variables
                result_pipeline[vm_job]["variables"] = {}
                result_pipeline[vm_job]["variables"]["KIND_EXPERIMENTAL_DOCKER_NETWORK"] = "bridge"
                result_pipeline[vm_job]["variables"]["TEST_LIBRARY"] = language
                result_pipeline[vm_job]["variables"]["SCENARIO"] = scenario
                result_pipeline[vm_job]["variables"]["ONBOARDING_FILTER_ENV"] = ci_environment
                result_pipeline[vm_job]["variables"]["WEBLOG"] = weblog_name
                custom_extra_params = ""
                if dd_installer_library_version:
                    result_pipeline[vm_job]["variables"]["DD_INSTALLER_LIBRARY_VERSION"] = dd_installer_library_version
                    custom_extra_params = f" --ssi-library-version {dd_installer_library_version}"
                if dd_installer_injector_version:
                    result_pipeline[vm_job]["variables"]["DD_INSTALLER_INJECTOR_VERSION"] = (
                        dd_installer_injector_version
                    )
                    custom_extra_params = (
                        custom_extra_params + f" --ssi-injector-version {dd_installer_injector_version}"
                    )
                result_pipeline[vm_job]["parallel"] = {"matrix": []}
                for image in images:
                    if image["arch"] != architecture:
                        continue
                    image_name = next(iter(image))
                    runtimes = [runtine for runtine in image[image_name]]  # noqa: C416
                    result_pipeline[vm_job]["parallel"]["matrix"].append(
                        {"IMAGE": image_name, "ARCH": image["arch"], "RUNTIME": runtimes}
                    )

                result_pipeline[vm_job]["script"] = [
                    "aws ecr get-login-password | docker login --username ${PRIVATE_DOCKER_REGISTRY_USER} --password-stdin ${PRIVATE_DOCKER_REGISTRY}",  # noqa: E501
                    "./build.sh -i runner",
                    "source venv/bin/activate",
                    "echo 'Running SSI tests'",
                    (
                        'timeout 1200s ./run.sh $SCENARIO --ssi-weblog "$WEBLOG" '
                        '--ssi-library "$TEST_LIBRARY" --ssi-base-image "$IMAGE" '
                        '--ssi-arch "$ARCH" --ssi-installable-runtime "$RUNTIME" '
                        "--ssi-env $ONBOARDING_FILTER_ENV"
                        + custom_extra_params
                        + " --report-run-url ${CI_JOB_URL} --report-environment "
                        + ci_environment
                    ),
                ]
                if os.getenv("CI_PROJECT_NAME") != "system-tests":
                    if os.getenv("SYSTEM_TESTS_REF"):
                        result_pipeline[vm_job]["script"].insert(0, f"git checkout {os.getenv('SYSTEM_TESTS_REF')}")
                        result_pipeline[vm_job]["script"].insert(0, "git pull")
                    result_pipeline[vm_job]["script"].insert(0, "cd /system-tests")


def print_aws_gitlab_pipeline(language: str, aws_matrix: dict, ci_environment: str, result_pipeline: dict) -> None:
    with open("utils/virtual_machine/virtual_machines.json", "r") as file:
        raw_data_virtual_machines = json.load(file)["virtual_machines"]

    only_defaults = should_run_only_defaults_vm()

    # Special filters from env variables
    dd_install_script_version = os.getenv("DD_INSTALL_SCRIPT_VERSION")
    dd_installer_library_version = os.getenv("DD_INSTALLER_LIBRARY_VERSION")
    dd_installer_injector_version = os.getenv("DD_INSTALLER_INJECTOR_VERSION")
    if not dd_installer_library_version:
        dd_installer_library_version = os.getenv(f"DD_INSTALLER_LIBRARY_VERSION_{language.upper()}")

    scenarios_prefix_names = _generate_unique_prefix(aws_matrix)

    # Create the jobs by scenario. Each job (vm) will have a parallel matrix with the weblogs
    for scenario, weblogs in aws_matrix.items():
        result_pipeline["stages"].append(scenario)

        # Collect all unique VMs for this scenario
        vm_set = set()
        for vms in weblogs.values():
            vm_set.update(vms)

        for vm in vm_set:
            vm_job = vm + "." + scenarios_prefix_names[scenario]
            result_pipeline[vm_job] = {}
            result_pipeline[vm_job]["stage"] = scenario
            result_pipeline[vm_job]["extends"] = ".base_job_onboarding_system_tests"

            # If only_defaults is True, we will set the job to manual if it's not a default VM
            if only_defaults and not is_default_machine(raw_data_virtual_machines, vm):
                result_pipeline[vm_job]["when"] = "manual"
                # Avoid the pipeline marked as blocked
                result_pipeline[vm_job]["allow_failure"] = True

            # Job variables
            result_pipeline[vm_job]["variables"] = {}
            result_pipeline[vm_job]["variables"]["TEST_LIBRARY"] = language
            result_pipeline[vm_job]["variables"]["SCENARIO"] = scenario
            result_pipeline[vm_job]["variables"]["VM"] = vm
            result_pipeline[vm_job]["variables"]["ONBOARDING_FILTER_ENV"] = ci_environment
            if dd_installer_library_version:
                result_pipeline[vm_job]["variables"]["DD_INSTALLER_LIBRARY_VERSION"] = dd_installer_library_version
            if dd_installer_injector_version:
                result_pipeline[vm_job]["variables"]["DD_INSTALLER_INJECTOR_VERSION"] = dd_installer_injector_version
            if dd_install_script_version:
                result_pipeline[vm_job]["variables"]["DD_INSTALL_SCRIPT_VERSION"] = dd_install_script_version
            # Job weblog matrix for a virtaul machine
            result_pipeline[vm_job]["parallel"] = {"matrix": []}
            for weblog in weblogs.keys():  # noqa: SIM118
                if vm in weblogs[weblog]:
                    result_pipeline[vm_job]["parallel"]["matrix"].append({"WEBLOG": weblog})
