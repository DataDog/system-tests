import os
import yaml
import hashlib


def _generate_unique_prefix(scenario_names, prefix_length=3):
    """ Generate a unique prefix for each scenario name/stage  """
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

def should_run_only_defaults_vm():
    """ Default rules to run only default VMs or all VMs"""
    #Get gitlab variables from the environment
    CI_COMMIT_TAG=os.getenv("CI_COMMIT_TAG")
    CI_COMMIT_BRANCH=os.getenv("CI_COMMIT_BRANCH")
    CI_PROJECT_NAME=os.getenv("CI_PROJECT_NAME")
    CI_PIPELINE_SOURCE= os.getenv("CI_PIPELINE_SOURCE")
    
    #If it is a scheduled pipeline or tag generation, we should run all the VMs always
    #it doesn't matter the project pipeline
    if CI_PIPELINE_SOURCE == "schedule" or CI_COMMIT_TAG:
        return False

    #if we run on system-tests repository and it's the main branch, we should run all the VMs
    if CI_PROJECT_NAME == "system-tests" and CI_COMMIT_BRANCH == "main":
        return False
    else:
        #if the commit is on different repository run default vms
        #if the is on system-tests and it's not the main branch, run default vms
        return True 

def is_default_machine(raw_data_virtual_machines, vm):
    for vm_data in raw_data_virtual_machines:
        if vm_data["name"] == vm and vm_data["default_vm"]:
            return True
    return False

def print_aws_gitlab_pipeline(language, aws_matrix, ci_environment, raw_data_virtual_machines) -> None:
    result_pipeline = {}  # type: dict
    result_pipeline["include"] = []
    result_pipeline["stages"] = []
    pipeline_file = ".gitlab/aws_gitlab-ci.yml"
    pipeline_data = None
    only_defaults=should_run_only_defaults_vm()
    # Special filters from env variables
    DD_INSTALLER_LIBRARY_VERSION = os.getenv("DD_INSTALLER_LIBRARY_VERSION")
    DD_INSTALLER_INJECTOR_VERSION = os.getenv("DD_INSTALLER_INJECTOR_VERSION")
  
    with open(pipeline_file, encoding="utf-8") as f:
        pipeline_data = yaml.load(f, Loader=yaml.FullLoader)  # noqa: S506

    result_pipeline["include"] = pipeline_data["include"]
    if not aws_matrix:
        result_pipeline["stages"].append("AWS_SSI")
        result_pipeline["ssi_tests"] = pipeline_data["ssi_tests"]    
    # Copy the base job and default job
    result_pipeline[".base_job_onboarding_system_tests"] = pipeline_data[".base_job_onboarding_system_tests"]
    

    # collect all the possible scenarios to generate unique prefixes for each scenario
    # we will add the prefix to the job name to avoid jobs with the same name and different stages
    scenarios_prefix_names = {}
    for scenario, weblogs in aws_matrix.items():
        scenarios_prefix_names[scenario] = ""
    scenarios_prefix_names = _generate_unique_prefix(scenarios_prefix_names.keys())

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
            
            #Job variables       
            result_pipeline[vm_job]["variables"] = {}
            result_pipeline[vm_job]["variables"]["TEST_LIBRARY"] = language
            result_pipeline[vm_job]["variables"]["SCENARIO"] = scenario
            result_pipeline[vm_job]["variables"]["VM"] = vm
            result_pipeline[vm_job]["variables"]["ONBOARDING_FILTER_ENV"] = ci_environment
            if DD_INSTALLER_LIBRARY_VERSION:
                result_pipeline[vm_job]["variables"]["DD_INSTALLER_LIBRARY_VERSION"] = DD_INSTALLER_LIBRARY_VERSION
            if DD_INSTALLER_INJECTOR_VERSION:
                result_pipeline[vm_job]["variables"]["DD_INSTALLER_INJECTOR_VERSION"] = DD_INSTALLER_INJECTOR_VERSION
                
            #Job weblog matrix for a virtaul machine
            result_pipeline[vm_job]["parallel"] = {"matrix": []}
            for weblog in weblogs.keys():
                if vm in weblogs[weblog]:
                    result_pipeline[vm_job]["parallel"]["matrix"].append({"WEBLOG": weblog})

    pipeline_yml = yaml.dump(result_pipeline, sort_keys=False, default_flow_style=False)
    print(pipeline_yml)
