import os
import yaml
import hashlib
import json
from collections.abc import Callable


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


def _get_k8s_injector_image_refs(language: str, ci_environment: str, cluster_agent_versions: str | None):
    """Get the k8s injector  and lib init image references"""
    k8s_lib_init_img = os.getenv("K8S_LIB_INIT_IMG")
    k8s_injector_img = None
    k8s_available_images = {
        "prod": "235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/apm-inject:latest",
        "dev": "235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/apm-inject:latest_snapshot",
    }

    if cluster_agent_versions:
        if os.getenv("K8S_INJECTOR_IMG"):
            k8s_injector_img = os.getenv("K8S_INJECTOR_IMG")
        elif ci_environment == "dev":
            k8s_injector_img = k8s_available_images["dev"]
        else:
            k8s_injector_img = k8s_available_images["prod"]

    if not k8s_lib_init_img:
        language_img_name = "js" if language == "nodejs" else language
        if ci_environment == "dev":
            k8s_lib_init_img = (
                f"235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/dd-lib-{language_img_name}-init:latest_snapshot"
            )
        else:
            k8s_lib_init_img = (
                f"235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/dd-lib-{language_img_name}-init:latest"
            )

    return k8s_lib_init_img, k8s_injector_img


def should_run_fast_mode() -> bool:
    """Default rules to run only a part of the full pipeline.

    For example we only run the default vms if it's a commit in a PR, but we run all the vms
    if it's a scheduled pipeline or a tag generation.
    Other example, K8s tests are only run the cluster agent dev version for scheduled pipelines
    or a tag generation.
    """

    # Get gitlab variables from the environment
    ci_commit_tag = os.getenv("CI_COMMIT_TAG")
    ci_commit_branch = os.getenv("CI_COMMIT_BRANCH")
    ci_project_name = os.getenv("CI_PROJECT_NAME")
    ci_pipeline_source = os.getenv("CI_PIPELINE_SOURCE")

    # If it is a scheduled pipeline or tag generation, we should run the full pipeline
    # it doesn't matter the project pipeline
    if ci_pipeline_source == "schedule" or ci_commit_tag:
        return False

    # if we run on system-tests repository and it's the main branch, we should run the full pipeline
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

    if False and matrix_data["aws_ssi_scenario_defs"]:
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
    if False and matrix_data["dockerssi_scenario_defs"]:
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


def filter_k8s_components(components_list: list[dict], should_keep_key: Callable[[str, str], bool]) -> list[dict]:
    """Filters K8s components based on their keys and component types.

    Args:
        components_list: List of component dictionaries from k8s matrix
                        Example: [{"cluster_agents": [{"prod": "img:1"}, {"nightly_dev": "img:2"}]}, ...]
        should_keep_key: Function that takes (key, component_type) and returns True if it should be kept
                        - key: The version key (e.g., "prod", "nightly_dev", "dev")
                        - component_type: The component type (e.g., "cluster_agents", "lib_inits")

    Returns:
        Filtered components list with the same structure

    """
    filtered_components = []

    for component_dict in components_list:
        for component_type, version_list in component_dict.items():
            # Filter version dicts based on their keys AND component type
            filtered_versions = [
                version_dict
                for version_dict in version_list
                if all(should_keep_key(key, component_type) for key in version_dict)
            ]
            filtered_components.append({component_type: filtered_versions})

    return filtered_components


def _remove_component_and_add_custom(components_list: list[dict], component_type: str, custom_image: str) -> list[dict]:
    """Remove a specific component type from the list and add a custom version.

    This helper removes all nightly and dev versions from all components,
    then removes the specified component entirely, and adds a custom dev version.

    Args:
        components_list: Original list of component dictionaries
        component_type: Type of component to replace (e.g., "lib_inits", "injectors")
        custom_image: Custom image URL to use

    Returns:
        Filtered components list with custom component added

    """
    # Filter out nightly and dev versions from all components
    filtered = filter_k8s_components(components_list, lambda key, _: not (key.startswith("nightly") or key == "dev"))

    # Remove the target component type entirely
    filtered = [comp for comp in filtered if component_type not in comp]

    # Add the custom component with dev tag
    filtered.append({component_type: [{"dev": custom_image}]})

    return filtered


def apply_k8s_ci_filters(components_list: list[dict]) -> list[dict]:
    """Apply CI-based filters to K8s components based on environment and custom images.

    This method applies filtering rules in the following priority order:
    1. Custom lib_init image (K8S_LIB_INIT_IMG) - Uses only prod versions + custom lib_init
    2. Custom injector image (K8S_INJECTOR_IMG) - Uses only prod versions + custom injector
    3. System-tests scheduled pipeline - Uses full component matrix (no filtering)
    4. System-tests repository - Filters out nightly versions (keeps prod and dev)
    5. Default - No filtering applied

    Args:
        components_list: List of component dictionaries from k8s matrix
                        Example: [{"cluster_agents": [{"prod": "img:1"}]}, {"lib_inits": [...]}, ...]

    Returns:
        Filtered components list maintaining the same structure

    """
    # Extract environment variables
    ci_project_name = os.getenv("CI_PROJECT_NAME")
    ci_pipeline_source = os.getenv("CI_PIPELINE_SOURCE")
    k8s_lib_init_img = os.getenv("K8S_LIB_INIT_IMG")
    k8s_injector_img = os.getenv("K8S_INJECTOR_IMG")
    is_system_tests_scheduled_pipeline = ci_project_name == "system-tests" and ci_pipeline_source == "schedule"
    is_system_tests_pr_or_commit = ci_project_name == "system-tests"

    # Priority 1: Custom lib_init image overrides all other filters
    if k8s_lib_init_img:
        return _remove_component_and_add_custom(components_list, "lib_inits", k8s_lib_init_img)

    # Priority 2: Custom injector image overrides remaining filters
    if k8s_injector_img:
        return _remove_component_and_add_custom(components_list, "injectors", k8s_injector_img)

    # Priority 3: System-tests scheduled pipeline runs full matrix
    if is_system_tests_scheduled_pipeline:
        return components_list

    # Priority 4: System-tests repository filters nightly versions
    if is_system_tests_pr_or_commit:
        return filter_k8s_components(components_list, lambda key, _: not key.startswith("nightly"))

    # Priority 5: Default - no filtering
    return components_list


def print_k8s_gitlab_pipeline(
    language: str, k8s_matrix: dict[str, dict], ci_environment: str, result_pipeline: dict
) -> None:
    result_pipeline["stages"].append("K8S_LIB_INJECTION")
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
        for weblog_name, components_list in weblogs.items():
            k8s_weblog_img = os.getenv("K8S_WEBLOG_IMG", "${PRIVATE_DOCKER_REGISTRY}" + f"/system-tests/{weblog_name}")

            # Apply all CI-based filters to components
            filtered_components = apply_k8s_ci_filters(components_list)

            # Extract all component types from the components list
            cluster_agents_dict: dict = next((comp for comp in filtered_components if "cluster_agents" in comp), {})
            cluster_agent_versions = [
                version
                for agent_dict in cluster_agents_dict.get("cluster_agents", [])
                for version in agent_dict.values()
            ]

            lib_inits_dict: dict = next((comp for comp in filtered_components if "lib_inits" in comp), {})
            lib_init_versions = [
                version for init_dict in lib_inits_dict.get("lib_inits", []) for version in init_dict.values()
            ]

            injectors_dict: dict = next((comp for comp in filtered_components if "injectors" in comp), {})
            injector_versions = [
                version for injector_dict in injectors_dict.get("injectors", []) for version in injector_dict.values()
            ]

            helm_charts_dict: dict = next((comp for comp in filtered_components if "helm_charts" in comp), {})
            helm_chart_versions = [
                version for chart_dict in helm_charts_dict.get("helm_charts", []) for version in chart_dict.values()
            ]

            helm_chart_operators_dict: dict = next(
                (comp for comp in filtered_components if "helm_chart_operators" in comp), {}
            )
            helm_chart_operator_versions = [
                version
                for operator_dict in helm_chart_operators_dict.get("helm_chart_operators", [])
                for version in operator_dict.values()
            ]

            # Build matrix entry - only include components that have values
            matrix_entry = {
                "K8S_WEBLOG": weblog_name,
                "K8S_WEBLOG_IMG": k8s_weblog_img,
            }

            if cluster_agent_versions:
                matrix_entry["K8S_CLUSTER_IMG"] = cluster_agent_versions
            else:
                # Use empty array for scenarios without cluster agents (e.g., K8S_LIB_INJECTION_NO_AC)
                # GitLab CI requires array values for parallel matrix variables
                matrix_entry["K8S_CLUSTER_IMG"] = [""]
            if lib_init_versions:
                matrix_entry["K8S_LIB_INIT_IMG"] = lib_init_versions
            if injector_versions:
                matrix_entry["K8S_INJECTOR_IMG"] = injector_versions
            if helm_chart_versions:
                matrix_entry["K8S_HELM_CHART"] = helm_chart_versions
            if helm_chart_operator_versions:
                matrix_entry["K8S_HELM_CHART_OPERATOR"] = helm_chart_operator_versions

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
                    f"{'docker-in-docker:amd64' if architecture == 'linux/amd64' else 'docker-in-docker:arm64'}"
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

    only_defaults = should_run_fast_mode()

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
