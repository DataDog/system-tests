import os
import yaml
import hashlib
import json


class GitLabReferenceYAMLTag:
    """Custom class to represent YAML references that should not be quoted"""
    def __init__(self, reference):
        self.reference = reference

    def __str__(self):
        return self.reference


class NoQuoteDumper(yaml.SafeDumper):
    """Custom YAML dumper that avoids quoting only GitLabReferenceYAMLTag objects"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._gitlab_references = set()

    def represent_data(self, data):
        # Track GitLabReferenceYAMLTag objects
        if isinstance(data, GitLabReferenceYAMLTag):
            self._gitlab_references.add(str(data))
        return super().represent_data(data)

    def choose_scalar_style(self):
        # Only affect scalars that are from GitLabReferenceYAMLTag objects
        if (hasattr(self.event, 'value') and
            self.event.value in self._gitlab_references):
            return None  # Plain style, no quotes
        return super().choose_scalar_style()

def yaml_reference_representer(dumper, data):
    """Custom YAML representer to output GitLabReferenceYAMLTag without quotes"""
    return dumper.represent_scalar('tag:yaml.org,2002:str', str(data))

NoQuoteDumper.add_representer(GitLabReferenceYAMLTag, yaml_reference_representer)


def _generate_unique_prefix(scenario_specs_matrix, prefix_length=3):
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


def _get_k8s_injector_image_refs(language, ci_environment, cluster_agent_versions):
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


def is_default_machine(raw_data_virtual_machines, vm) -> bool:
    return any(vm_data["name"] == vm and vm_data["default_vm"] for vm_data in raw_data_virtual_machines)


def print_gitlab_pipeline(language, matrix_data, ci_environment) -> None:
    # Print all supported pipelines
    print_ssi_gitlab_pipeline(language, matrix_data, ci_environment)


def print_ssi_gitlab_pipeline(language, matrix_data, ci_environment) -> None:
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
        # Copy the base job templates for the k8s lib injection system tests
        result_pipeline[".k8s_lib_injection_base"] = pipeline_data[".k8s_lib_injection_base"]
        result_pipeline[".k8s_lib_injection_weblog_build_base"] = pipeline_data[".k8s_lib_injection_weblog_build_base"]
        if os.getenv("CI_PROJECT_NAME") != "system-tests":
            if os.getenv("SYSTEM_TESTS_REF"):
                result_pipeline[".k8s_lib_injection_base"]["script"].insert(
                    0, f"git checkout {os.getenv('SYSTEM_TESTS_REF')}"
                )
                result_pipeline[".k8s_lib_injection_base"]["script"].insert(0, "git pull")
                result_pipeline[".k8s_lib_injection_weblog_build_base"]["script"].insert(
                    0, f"git checkout {os.getenv('SYSTEM_TESTS_REF')}"
                )
                result_pipeline[".k8s_lib_injection_weblog_build_base"]["script"].insert(0, "git pull")
            result_pipeline[".k8s_lib_injection_base"]["script"].insert(0, "cd /system-tests")
            result_pipeline[".k8s_lib_injection_weblog_build_base"]["script"].insert(0, "cd /system-tests")

        print_k8s_gitlab_pipeline(language, matrix_data["libinjection_scenario_defs"], ci_environment, result_pipeline)

    pipeline_yml = yaml.dump(result_pipeline, Dumper=NoQuoteDumper, sort_keys=False, default_flow_style=False)

    output_file = f"{language}_ssi_gitlab_pipeline.yml"
    with open(output_file, "w") as file:
        file.write(pipeline_yml)
    print("Pipeline file generated: ", output_file)


def print_k8s_gitlab_pipeline(language, k8s_matrix, ci_environment, result_pipeline) -> None:
    result_pipeline["stages"].append("K8S_LIB_INJECTION")

    # Step 1: Collect all unique weblogs and generate shared matrix
    all_weblogs = set()
    for scenario, weblogs in k8s_matrix.items():
        for weblog_name in weblogs.keys():
            all_weblogs.add(weblog_name)

    # Step 2: Generate two matrices - one for build (weblog only), one for test (weblog + cluster)
    test_matrix = []    # Full matrix for K8S lib injection test jobs (includes cluster images)
    build_matrix = []   # Simplified matrix for builds (weblog only)
    cluster_agent_versions_scenario = None
    weblog_seen = set()  # Track which weblogs we've already added to avoid duplicates

    for scenario, weblogs in k8s_matrix.items():
        for weblog_name, cluster_agent_versions in weblogs.items():
            if weblog_name in weblog_seen:
                continue  # Skip duplicate weblogs from multiple scenarios
            weblog_seen.add(weblog_name)
            k8s_weblog_img = os.getenv("K8S_WEBLOG_IMG", "${PRIVATE_DOCKER_REGISTRY}" + f"/system-tests/{weblog_name}")

            # Add to build matrix (no cluster images needed)
            build_matrix.append({
                "K8S_WEBLOG": weblog_name,
            })

            # Add to test matrix (with cluster images)
            if cluster_agent_versions:
                test_matrix.append({
                    "K8S_WEBLOG": weblog_name,
                    "K8S_WEBLOG_IMG": k8s_weblog_img,
                    "K8S_CLUSTER_IMG": cluster_agent_versions,
                })
                cluster_agent_versions_scenario = cluster_agent_versions
            else:
                test_matrix.append({
                    "K8S_WEBLOG": weblog_name,
                    "K8S_WEBLOG_IMG": k8s_weblog_img,
                    "K8S_CLUSTER_IMG": "None"
                })

    # Step 3: Create the matrix references
    matrix_ref_name = ".k8s_lib_injection_matrix"
    build_matrix_ref_name = ".k8s_lib_injection_build_matrix"

    result_pipeline[matrix_ref_name] = {
        "matrix": test_matrix
    }
    result_pipeline[build_matrix_ref_name] = {
        "matrix": build_matrix
    }

    # Step 4: Create a single build job with parallel matrix reference
    if all_weblogs:
        build_job_name = f"k8s_build_weblogs_{language}"
        # Get the scenario name from the first scenario (they should all be the same)
        scenario_name = next(iter(k8s_matrix.keys()))
        result_pipeline[build_job_name] = {
            "extends": ".k8s_lib_injection_weblog_build_base",
            "variables": {
                "TEST_LIBRARY": language,
                "K8S_SCENARIO": scenario_name
            },
            "parallel": GitLabReferenceYAMLTag(f"!reference [ {build_matrix_ref_name} ]")
        }

    # Step 5: Create the test jobs by scenario
    for scenario, weblogs in k8s_matrix.items():
        job = scenario
        result_pipeline[job] = {}
        result_pipeline[job]["extends"] = ".k8s_lib_injection_base"

        # Job variables
        result_pipeline[job]["variables"] = {}
        result_pipeline[job]["variables"]["TEST_LIBRARY"] = language
        result_pipeline[job]["variables"]["K8S_SCENARIO"] = scenario
        result_pipeline[job]["variables"]["REPORT_ENVIRONMENT"] = ci_environment

        # Use the shared matrix reference
        result_pipeline[job]["parallel"] = GitLabReferenceYAMLTag(f"!reference [ {matrix_ref_name} ]")

        # Add matrix dependency on build job
        if all_weblogs:
            result_pipeline[job]["needs"] = [{
                "job": build_job_name,
                "parallel": GitLabReferenceYAMLTag(f"!reference [ {build_matrix_ref_name} ]")
            }]

        # Set injector and lib_init images (existing logic)
        k8s_lib_init_img, k8s_injector_img = _get_k8s_injector_image_refs(
            language, ci_environment, cluster_agent_versions_scenario
        )
        result_pipeline[job]["variables"]["K8S_LIB_INIT_IMG"] = k8s_lib_init_img
        result_pipeline[job]["variables"]["K8S_INJECTOR_IMG"] = k8s_injector_img if k8s_injector_img else "None"


def print_docker_ssi_gitlab_pipeline(language, docker_ssi_matrix, ci_environment, result_pipeline) -> None:
    # Special filters from env variables
    dd_installer_library_version = os.getenv("DD_INSTALLER_LIBRARY_VERSION")
    dd_installer_injector_version = os.getenv("DD_INSTALLER_INJECTOR_VERSION")

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


def print_aws_gitlab_pipeline(language, aws_matrix, ci_environment, result_pipeline) -> None:
    with open("utils/virtual_machine/virtual_machines.json", "r") as file:
        raw_data_virtual_machines = json.load(file)["virtual_machines"]

    only_defaults = should_run_only_defaults_vm()

    # Special filters from env variables
    dd_installer_library_version = os.getenv("DD_INSTALLER_LIBRARY_VERSION")
    dd_installer_injector_version = os.getenv("DD_INSTALLER_INJECTOR_VERSION")

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

            # Job weblog matrix for a virtaul machine
            result_pipeline[vm_job]["parallel"] = {"matrix": []}
            for weblog in weblogs.keys():  # noqa: SIM118
                if vm in weblogs[weblog]:
                    result_pipeline[vm_job]["parallel"]["matrix"].append({"WEBLOG": weblog})
