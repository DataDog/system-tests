import os
import yaml
import hashlib
import json

def _generate_unique_prefix(scenario_specs_matrix, prefix_length=3):
    """Generate a unique prefix for each scenario name/stage
     collect all the possible scenarios to generate unique prefixes for each scenario
     we will add the prefix to the job name to avoid jobs with the same name and different stages """
     
    scenarios_prefix_names = {}
    for scenario, weblogs in scenario_specs_matrix.items():
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
    k8s_available_images = {"dev":"gcr.io/datadoghq/apm-inject:latest", "prod":"ghcr.io/datadog/apm-inject:latest_snapshot"}
    
    if cluster_agent_versions:
        if os.getenv("K8S_INJECTOR_IMG"):
            k8s_injector_img = os.getenv("K8S_INJECTOR_IMG")
        elif "dev" == ci_environment:
            k8s_injector_img = k8s_available_images["dev"]
        else:
            k8s_injector_img = k8s_available_images["prod"]
            
    if not k8s_lib_init_img:
        language_img_name = "js" if language == "nodejs" else language
        if "dev" == ci_environment:
            language_repo_name = "js" if language == "nodejs" else language
            language_repo_name = "py" if language == "python" else language_repo_name
            language_repo_name = "rb" if language == "ruby" else language_repo_name
            k8s_lib_init_img = f"ghcr.io/datadog/dd-trace-{language_repo_name}/dd-lib-{language_img_name}-init:latest_snapshot"
        else:
            k8s_lib_init_img = f"gcr.io/datadoghq/dd-lib-{language_img_name}-init:latest"
    
    return k8s_lib_init_img, k8s_injector_img
 
def should_run_only_defaults_vm():
    """Default rules to run only default VMs or all VMs"""
    # Get gitlab variables from the environment
    CI_COMMIT_TAG = os.getenv("CI_COMMIT_TAG")
    CI_COMMIT_BRANCH = os.getenv("CI_COMMIT_BRANCH")
    CI_PROJECT_NAME = os.getenv("CI_PROJECT_NAME")
    CI_PIPELINE_SOURCE = os.getenv("CI_PIPELINE_SOURCE")

    # If it is a scheduled pipeline or tag generation, we should run all the VMs always
    # it doesn't matter the project pipeline
    if CI_PIPELINE_SOURCE == "schedule" or CI_COMMIT_TAG:
        return False

    # if we run on system-tests repository and it's the main branch, we should run all the VMs
    if CI_PROJECT_NAME == "system-tests" and CI_COMMIT_BRANCH == "main":
        return False
    # if the commit is on different repository run default vms
    # if the is on system-tests and it's not the main branch, run default vms
    return True


def is_default_machine(raw_data_virtual_machines, vm):
    for vm_data in raw_data_virtual_machines:
        if vm_data["name"] == vm and vm_data["default_vm"]:
            return True
    return False

def print_gitlab_pipeline(language, matrix_data, ci_environment) -> None:

    result_pipeline = {}  # type: dict
    result_pipeline["include"] = []
    result_pipeline["stages"] = []
    pipeline_file = ".gitlab/aws_gitlab-ci.yml"
    pipeline_data = None

    with open(pipeline_file, encoding="utf-8") as f:
        pipeline_data = yaml.load(f, Loader=yaml.FullLoader)  # noqa: S506
    result_pipeline["include"] = pipeline_data["include"]
    
    if not matrix_data["aws_ssi_scenario_defs"] and not matrix_data["dockerssi_scenario_defs"] and not matrix_data["libinjection_scenario_defs"]:
        result_pipeline["stages"].append("SSI_TESTS")
        result_pipeline["ssi_tests"] = pipeline_data["ssi_tests"]
    
    if matrix_data["aws_ssi_scenario_defs"]:
        # Copy the base job for the onboarding system tests
        result_pipeline[".base_job_onboarding_system_tests"] = pipeline_data[".base_job_onboarding_system_tests"]
        print_aws_gitlab_pipeline(language, matrix_data["aws_ssi_scenario_defs"], ci_environment, result_pipeline)
    if matrix_data["dockerssi_scenario_defs"]:
        # Copy the base job for the docker ssi system tests
        result_pipeline[".base_docker_ssi_job"] = pipeline_data[".base_docker_ssi_job"]
        print_docker_ssi_gitlab_pipeline(language, matrix_data["dockerssi_scenario_defs"], ci_environment, result_pipeline)
    if matrix_data["libinjection_scenario_defs"]:
        # Copy the base job for the k8s lib injection system tests
        result_pipeline[".k8s_lib_injection_base"] = pipeline_data[".k8s_lib_injection_base"]
        print_k8s_gitlab_pipeline(language, matrix_data["libinjection_scenario_defs"], ci_environment, result_pipeline)


    pipeline_yml = yaml.dump(result_pipeline, sort_keys=False, default_flow_style=False)
    print(pipeline_yml)

def print_k8s_gitlab_pipeline(language, k8s_matrix, ci_environment, result_pipeline) -> None:
    result_pipeline["stages"].append("K8S_LIB_INJECTION")
    # Create the jobs by scenario.
    for scenario, weblogs in k8s_matrix.items():
        job = scenario
        result_pipeline[job] = {}
        result_pipeline[job]["stage"] = scenario
        result_pipeline[job]["extends"] = ".k8s_lib_injection_base"
        # Job variables
        result_pipeline[job]["variables"] = {}
        result_pipeline[job]["variables"]["TEST_LIBRARY"] = language
        result_pipeline[job]["variables"]["K8S_SCENARIO"] = scenario
        
        result_pipeline[job]["parallel"] = {"matrix": []}
        cluster_agent_versions_scenario = None
        for weblog_name, cluster_agent_versions in weblogs.items():
            K8S_WEBLOG_IMG = os.getenv("K8S_WEBLOG_IMG", f"ghcr.io/datadog/system-tests/{weblog_name}:latest")
            if cluster_agent_versions:  
                result_pipeline[job]["parallel"]["matrix"].append({"K8S_WEBLOG": weblog_name,"K8S_WEBLOG_IMG":K8S_WEBLOG_IMG, "K8S_CLUSTER_IMG": cluster_agent_versions})
                cluster_agent_versions_scenario = cluster_agent_versions
            else:
                result_pipeline[job]["parallel"]["matrix"].append({"K8S_WEBLOG": weblog_name,"K8S_WEBLOG_IMG":K8S_WEBLOG_IMG})

        # Job variables: injector and lib_init
        k8s_lib_init_img,k8s_injector_img = _get_k8s_injector_image_refs(language, ci_environment, cluster_agent_versions_scenario )
        result_pipeline[job]["variables"]["K8S_LIB_INIT_IMG"] = k8s_lib_init_img
        if k8s_injector_img:
            #In the no admission controller scenarios we don't use the injector
            result_pipeline[job]["variables"]["K8S_INJECTOR_IMG"] = k8s_injector_img
       

def print_docker_ssi_gitlab_pipeline(language, docker_ssi_matrix, ci_environment, result_pipeline) -> None:
    # Special filters from env variables
    DD_INSTALLER_LIBRARY_VERSION = os.getenv("DD_INSTALLER_LIBRARY_VERSION")
    DD_INSTALLER_INJECTOR_VERSION = os.getenv("DD_INSTALLER_INJECTOR_VERSION")
    
    scenarios_prefix_names = _generate_unique_prefix(docker_ssi_matrix)
    # Create the jobs by scenario.
    for scenario, weblogs in docker_ssi_matrix.items():
        result_pipeline["stages"].append(scenario)
        for weblog_name, images in weblogs.items():
            #Get the different architectures
            architectures = set()
            for image in images:
                architectures.add(image["arch"])
                
            for architecture in architectures:
            
                vm_job = weblog_name + "." + architecture.replace("linux/","")  + "." + scenarios_prefix_names[scenario]
                result_pipeline[vm_job] = {}
                result_pipeline[vm_job]["stage"] = scenario
                result_pipeline[vm_job]["extends"] = ".base_docker_ssi_job"
                result_pipeline[vm_job]["tags"]=[f"runner:{'docker' if architecture == 'linux/amd64' else 'docker-arm'}"]
                # Job variables
                result_pipeline[vm_job]["variables"] = {}
                result_pipeline[vm_job]["variables"]["TEST_LIBRARY"] = language
                result_pipeline[vm_job]["variables"]["SCENARIO"] = scenario
                result_pipeline[vm_job]["variables"]["ONBOARDING_FILTER_ENV"] = ci_environment
                result_pipeline[vm_job]["variables"]["WEBLOG"] = weblog_name
                custom_extra_params = ""      
                if DD_INSTALLER_LIBRARY_VERSION:
                    result_pipeline[vm_job]["variables"]["DD_INSTALLER_LIBRARY_VERSION"] = DD_INSTALLER_LIBRARY_VERSION
                    custom_extra_params = f"--ssi-library-version {DD_INSTALLER_LIBRARY_VERSION}"
                if DD_INSTALLER_INJECTOR_VERSION:
                    result_pipeline[vm_job]["variables"]["DD_INSTALLER_INJECTOR_VERSION"] = DD_INSTALLER_INJECTOR_VERSION
                    custom_extra_params = custom_extra_params + f"--ssi-injector-version {DD_INSTALLER_INJECTOR_VERSION}"
                result_pipeline[vm_job]["parallel"] = {"matrix": []}       
                for image in images:
                    if image["arch"] != architecture:
                        continue
                    image_name = next(iter(image))
                    runtimes = [runtine for runtine in image[image_name]]
                    result_pipeline[vm_job]["parallel"]["matrix"].append({"IMAGE": image_name, "ARCH": image["arch"], "RUNTIME": runtimes})

                result_pipeline[vm_job]["script"]= [
                    "./build.sh -i runner",
                    "source venv/bin/activate",
                    "echo 'Running SSI tests'",
                    'timeout 2700s ./run.sh $SCENARIO --ssi-weblog "$WEBLOG" --ssi-library "$TEST_LIBRARY" --ssi-base-image "$IMAGE" --ssi-arch "$ARCH" --ssi-installable-runtime "$RUNTIME" --ssi-env $ONBOARDING_FILTER_ENV' + custom_extra_params + ' --report-run-url ${CI_JOB_URL} --report-environment prod'
                ]
                   
def print_aws_gitlab_pipeline(language, aws_matrix, ci_environment, result_pipeline) -> None:
    with open("utils/virtual_machine/virtual_machines.json", "r") as file:
        raw_data_virtual_machines = json.load(file)["virtual_machines"]   
        
    only_defaults = should_run_only_defaults_vm()
    # Special filters from env variables
    DD_INSTALLER_LIBRARY_VERSION = os.getenv("DD_INSTALLER_LIBRARY_VERSION")
    DD_INSTALLER_INJECTOR_VERSION = os.getenv("DD_INSTALLER_INJECTOR_VERSION")

    scenarios_prefix_names = _generate_unique_prefix(aws_matrix)

    # Create the jobs by scenario. Each job (vm) will have a parallel matrix with the weblogs
    for scenario, weblogs in aws_matrix.items():
        if scenario == "DEMO_AWS":  # Skip the demo scenario on the ci
            continue
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

            # Job variables
            result_pipeline[vm_job]["variables"] = {}
            result_pipeline[vm_job]["variables"]["TEST_LIBRARY"] = language
            result_pipeline[vm_job]["variables"]["SCENARIO"] = scenario
            result_pipeline[vm_job]["variables"]["VM"] = vm
            result_pipeline[vm_job]["variables"]["ONBOARDING_FILTER_ENV"] = ci_environment
            if DD_INSTALLER_LIBRARY_VERSION:
                result_pipeline[vm_job]["variables"]["DD_INSTALLER_LIBRARY_VERSION"] = DD_INSTALLER_LIBRARY_VERSION
            if DD_INSTALLER_INJECTOR_VERSION:
                result_pipeline[vm_job]["variables"]["DD_INSTALLER_INJECTOR_VERSION"] = DD_INSTALLER_INJECTOR_VERSION

            # Job weblog matrix for a virtaul machine
            result_pipeline[vm_job]["parallel"] = {"matrix": []}
            for weblog in weblogs.keys():
                if vm in weblogs[weblog]:
                    result_pipeline[vm_job]["parallel"]["matrix"].append({"WEBLOG": weblog})
