import os
import pytest
from utils import context
from utils._decorators import is_jira_ticket
from copy import deepcopy


def parametrize_virtual_machines(bugs: list[dict] = None):
    """ You can set multiple bugs for a single test case. 
    If you want to set a bug for a specific VM, you can set the vm_name or vm_cpu or weblog_variant in the bug dictionary (using one or more fields). 
    ie: 
    - Marks as bug for vm with name "vm1" and weblog_variant "app1"
    *     @parametrize_virtual_machines(bugs=[{"vm_name":"vm1", "weblog_variant":"app1", "reason": "APMON-1576"}])
    - Marks as bug for vm with cpu type "amd64" and weblog_variant "app1"
    *     @parametrize_virtual_machines(bugs=[{"vm_cpu":"amd64", "weblog_variant":"app1", "reason": "APMON-1576"}])
    - Marks as bug for all vm with cpu type "amd64" and all weblogs
    *     @parametrize_virtual_machines(bugs=[{"vm_cpu":"amd64","reason": "APMON-1576"}])
    - Marks as bug for all vms that belong to "debian" and all weblogs
    *     @parametrize_virtual_machines(bugs=[{"vm_branch":"debian","reason": "APMON-1576"}])
    Reason is mandatory for each bug and it MUST reference to a JIRA ticket.
    """
    if callable(bugs):
        # here, bugs is not the bug list, but the decorated method
        raise TypeError(f"Typo in {bugs}'s decorator, you forgot parenthesis. Please use `@decorator()`")

    def decorator(func):
        # We group the parameters/vms. We want to execute in same worker the tests for one machine. We need to control the test order for each machine.
        # https://github.com/pytest-dev/pytest-xdist/issues/58
        parameters = []
        count = 0

        # We need to group the vms by runtime. We can't have multiple weblogs in the same vm (muticontainer apps or multicontainer alpine).
        vms_by_runtime, vms_by_runtime_ids = get_tested_apps_vms()

        # Mark the test with bug marker if we need
        # Setting groups for xdist
        for vm in vms_by_runtime:
            bug_found = False
            if bugs:
                for bug in bugs:
                    if (
                        (not "vm_name" in bug or vm.name == bug["vm_name"])
                        and (not "vm_branch" in bug or vm.os_branch == bug["vm_branch"])
                        and (not "vm_cpu" in bug or vm.os_cpu == bug["vm_cpu"])
                        and (not "weblog_variant" in bug or context.weblog_variant == bug["weblog_variant"])
                        and (not "library" in bug or context.library == bug["library"])
                        and (
                            not "runtime_version" in bug
                            or vm.get_deployed_weblog().runtime_version == bug["runtime_version"]
                        )
                    ):
                        if "reason" in bug and is_jira_ticket(bug["reason"]):
                            parameters.append(
                                pytest.param(
                                    vm,
                                    marks=[
                                        pytest.mark.xfail(reason=f"bug: {bug['reason']}"),
                                        pytest.mark.xdist_group(f"group{count}"),
                                    ],
                                )
                            )
                            bug_found = True
                            break
                        else:
                            raise ValueError(f"Invalid bug reason for {vm.name} {bug}. Please use a valid JIRA ticket.")

            if bug_found == False:
                parameters.append(pytest.param(vm, marks=pytest.mark.xdist_group(f"group{count}")))
            count += 1
        return pytest.mark.parametrize("virtual_machine", parameters, ids=vms_by_runtime_ids)(func)

    return decorator


def get_tested_apps_vms():
    """ This method is a workaround for multicontainer apps. We are going duplicate the machines for each runtime inside of docker compose.
    This means, if I have a multicontainer app with 3 containers (runtimes) running on 1 vm, I will have 3 machines with the same configuration but with different runtimes.
    NOTE: On AWS we only run 1 vm. We duplicate the vms for test isolation.
    """
    vms_by_runtime = []
    vms_by_runtime_ids = []
    for vm in getattr(context.scenario, "required_vms", []):
        deployed_weblog = vm.get_provision().get_deployed_weblog()
        if deployed_weblog.app_type == "multicontainer":
            for weblog in deployed_weblog.multicontainer_apps:
                vm_by_runtime = deepcopy(vm)
                vm_by_runtime.set_deployed_weblog(weblog)
                vms_by_runtime.append(vm_by_runtime)
                vms_by_runtime_ids.append(vm_by_runtime.get_vm_unique_id())
        else:
            vms_by_runtime.append(vm)
            vms_by_runtime_ids.append(vm.get_vm_unique_id())

    return vms_by_runtime, vms_by_runtime_ids


def nginx_parser(nginx_config_file):
    """ This function is used to parse the nginx config file and return the apps in the return block of the location block of the server block of the http block. 
    TODO: Improve this uggly code """
    import crossplane
    import json

    nginx_config = crossplane.parse(nginx_config_file)
    config_endpoints = nginx_config["config"]
    for config_endpoint in config_endpoints:
        parsed_data = config_endpoint["parsed"]
        for parsed in parsed_data:
            if "http" == parsed["directive"]:
                parsed_blocks = parsed["block"]
                for parsed_block in parsed_blocks:
                    if "server" in parsed_block["directive"]:
                        parsed_server_blocks = parsed_block["block"]
                        for parsed_server_block in parsed_server_blocks:
                            if "location" in parsed_server_block["directive"] and parsed_server_block["args"][0] == "/":
                                parsed_server_location_blocks = parsed_server_block["block"]
                                for parsed_server_location_block in parsed_server_location_blocks:
                                    if "return" in parsed_server_location_block["directive"]:
                                        return_args = parsed_server_location_block["args"]
                                        # convert string to  object
                                        json_object = json.loads(return_args[1].replace("'", '"'))
                                        return json_object["apps"]


def generate_gitlab_pipeline(language, weblog_name, scenario_name, env, vms):
    pipeline = {
        "include": [
            {"remote": "https://gitlab-templates.ddbuild.io/libdatadog/include/single-step-instrumentation-tests.yml"}
        ],
        "variables": {
            "KUBERNETES_SERVICE_ACCOUNT_OVERWRITE": "system-tests",
            "TEST": "1",
            "KUBERNETES_CPU_REQUEST": "6",
            "KUBERNETES_CPU_LIMIT": "6",
            "AMI_UPDATE": {"description": "Set to true to force the update the AMIs used in the system-tests"},
            # "ONBOARDING_FILTER_ENV": f"{env}",
            "ONLY_TEST_LIBRARY": "",
            # "DD_INSTALLER_LIBRARY_VERSION": {
            #    "description": "Set the version of the library to be installed. Use the pipeline id pipeline-${CI_PIPELINE_ID}"
            # },
            # "DD_INSTALLER_INJECTOR_VERSION": {
            #    "description": "Set the version of the injector to be installed. Use the pipeline id pipeline-${CI_PIPELINE_ID}"
            # },
        },
        "stages": ["dummy"],
        # A dummy job is necessary for cases where all of the test jobs are manual
        # The child pipeline shows as failed until at least 1 job is run
        "dummy": {
            "image": "registry.ddbuild.io/docker:20.10.13-gbi-focal",
            "tags": ["arch:amd64"],
            "stage": "dummy",
            "dependencies": [],
            "script": ["echo 'DONE'"],
        },
        ".base_job_onboarding_system_tests": {
            "extends": ".base_job_onboarding",
            "after_script": [
                'SCENARIO_SUFIX=$(echo "$SCENARIO" | tr "[:upper:]" "[:lower:]")',
                'REPORTS_PATH="reports/"',
                'mkdir -p "$REPORTS_PATH"',
                'cp -R logs_"${SCENARIO_SUFIX}" $REPORTS_PATH/',
                'cp logs_"${SCENARIO_SUFIX}"/feature_parity.json "$REPORTS_PATH"/"${SCENARIO_SUFIX}".json',
                'mv "$REPORTS_PATH"/logs_"${SCENARIO_SUFIX}" "$REPORTS_PATH"/logs_"${TEST_LIBRARY}"_"${ONBOARDING_FILTER_WEBLOG}"_"${SCENARIO_SUFIX}_${DEFAULT_VMS}"',
            ],
            "artifacts": {"when": "always", "paths": ["reports/"]},
        },
    }
    # Add FPD push script
    pipeline[".base_job_onboarding_system_tests"]["after_script"].extend(_generate_fpd_gitlab_script())

    # if we execute the pipeline manually, we want don't want to run the child jobs by default
    # if we execute the pipeline by schedule, we want to run the child jobs by default
    rule_run = {"if": '$CI_PIPELINE_SOURCE == "schedule"', "when": "always"}
    if os.getenv("CI_PIPELINE_SOURCE", "") == "schedule":
        rule_run = {"if": '$CI_PIPELINE_SOURCE == "parent_pipeline"', "when": "always"}

    # Generate a job per machine
    if vms:
        pipeline["stages"].append(scenario_name)

        for vm in vms:
            pipeline[f"{vm.name}_{weblog_name}_{scenario_name}"] = {
                "extends": ".base_job_onboarding_system_tests",
                "stage": scenario_name,
                "allow_failure": True,
                "needs": [],
                "variables": {
                    "TEST_LIBRARY": language,
                    "SCENARIO": scenario_name,
                    "WEBLOG": weblog_name,
                    "ONBOARDING_FILTER_ENV": env,
                },
                # Remove rules if you want to run the jobs when you clic on the execute button of the child pipeline
                "rules": [rule_run, {"when": "manual", "allow_failure": True},],
                "script": [
                    'echo "Running onboarding system tests for env: ${ONBOARDING_FILTER_ENV}"',
                    'echo "Running onboarding system tests forr DD_INSTALLER_LIBRARY_VERSION: ${DD_INSTALLER_LIBRARY_VERSION}"',
                    'echo "Running onboarding system tests for DD_INSTALLER_INJECTOR_VERSION: ${DD_INSTALLER_INJECTOR_VERSION}"',
                    #  "./build.sh -i runner",
                    #  "./run.sh $SCENARIO --vm-weblog $WEBLOG --vm-env $ONBOARDING_FILTER_ENV --vm-library $TEST_LIBRARY --vm-provider aws --report-run-url $CI_PIPELINE_URL --report-environment $ONBOARDING_FILTER_ENV --vm-default-vms All --vm-only "
                    #  + vm.name,
                ],
            }
    # Cache management for the pipeline
    pipeline["stages"].append("Cache")
    pipeline.update(_generate_cache_jobs(language, weblog_name, scenario_name, vms))

    return pipeline


def _generate_cache_jobs(language, weblog_name, scenario_name, vms):
    pipeline = {}
    # Generate a job per machine
    for vm in vms:
        pipeline[f"{vm.get_cache_name()}"] = {
            "extends": ".base_job_onboarding_system_tests",
            "stage": "Cache",
            "allow_failure": True,
            "needs": [],
            "variables": {
                "TEST_LIBRARY": language,
                "SCENARIO": scenario_name,
                "WEBLOG": weblog_name,
                "AMI_UPDATE": "true",
            },
            # Remove rules if you want to run the jobs when you clic on the execute button of the child pipeline
            "rules": [{"when": "manual", "allow_failure": True},],
            "script": [
                "./build.sh -i runner",
                "./run.sh $SCENARIO --vm-weblog $WEBLOG --vm-env $ONBOARDING_FILTER_ENV --vm-library $TEST_LIBRARY --vm-provider aws --vm-default-vms All --vm-only "
                + vm.name,
            ],
        }
    return pipeline


def _generate_fpd_gitlab_script():
    fpd_push_script = [
        'if [ "$CI_COMMIT_BRANCH" = "robertomonteromiguel/onboarding_parallel_ci" ]; then',
        'export FP_IMPORT_URL=$(aws ssm get-parameter --region us-east-1 --name ci.system-tests.fp-import-url --with-decryption --query "Parameter.Value" --out text)',
        'export FP_API_KEY=$(aws ssm get-parameter --region us-east-1 --name ci.system-tests.fp-api-key --with-decryption --query "Parameter.Value" --out text)',
        "for folder in reports/logs*/ ; do",
        '  echo "Checking folder: ${folder}"',
        "  for filename in ./${folder}*_feature_parity.json; do",
        "    if [ -e ${filename} ]",
        "    then",
        '      echo "Processing report: ${filename}"',
        '      #curl -X POST ${FP_IMPORT_URL} --fail --header "Content-Type: application/json" --header "FP_API_KEY: ${FP_API_KEY}" --data "@${filename}" --include',
        "    fi",
        "  done",
        "done",
        "fi",
    ]
    return fpd_push_script
