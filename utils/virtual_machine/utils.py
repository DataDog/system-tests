import os
from copy import deepcopy


def get_tested_apps_vms(vm):
    """Workaround for multicontainer apps. We are going duplicate the machines for each runtime inside of docker compose.
    This means, if I have a multicontainer app with 3 containers (runtimes) running on 1 vm, I will have 3 machines with the same configuration but with different runtimes.
    NOTE: On AWS we only run 1 vm. We duplicate the vms for test isolation.
    """
    vms_by_runtime = []
    vms_by_runtime_ids = []
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
    """Parse the nginx config file and return the apps in the return block of the location block of the server block of the http block.
    TODO: Improve this uggly code
    """
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


def generate_gitlab_pipeline(
    language,
    weblog_name,
    scenario_name,
    env,
    vms,
    installer_library_version,
    installer_injector_version,
    is_one_pipeline,
):
    pipeline = {
        "include": [
            {
                "remote": "https://gitlab-templates.ddbuild.io/libdatadog/include-wip/robertomonteromiguel/onboarding_tests_new_aws_account/single-step-instrumentation-tests.yml"
            }
        ],
        "variables": {
            "KUBERNETES_SERVICE_ACCOUNT_OVERWRITE": "system-tests",
            "TEST": "1",
            "KUBERNETES_CPU_REQUEST": "6",
            "KUBERNETES_CPU_LIMIT": "6",
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
                'cp logs_"${SCENARIO_SUFIX}"/feature_parity.json "$REPORTS_PATH"/"${SCENARIO_SUFIX}".json || true',
                'mv "$REPORTS_PATH"/logs_"${SCENARIO_SUFIX}" "$REPORTS_PATH"/logs_"${TEST_LIBRARY}"_"${ONBOARDING_FILTER_WEBLOG}"_"${SCENARIO_SUFIX}_${DEFAULT_VMS}" || true',
            ],
            "retry": {
                "max": "2",
                "when": [
                    "unknown_failure",
                    "data_integrity_failure",
                    "runner_system_failure",
                    "scheduler_failure",
                    "api_failure",
                ],
                "exit_codes": [3],
            },
            "artifacts": {"when": "always", "paths": ["reports/"]},
        },
        ".base_job_onboarding_one_pipeline": {
            "extends": ".base_job_onboarding",
            "after_script": [
                "cd system-tests",
                'SCENARIO_SUFIX=$(echo "$SCENARIO" | tr "[:upper:]" "[:lower:]")',
                'REPORTS_PATH="reports/"',
                'mkdir -p "$REPORTS_PATH"',
                'cp -R logs_"${SCENARIO_SUFIX}" $REPORTS_PATH/',
                'cp logs_"${SCENARIO_SUFIX}"/feature_parity.json "$REPORTS_PATH"/"${SCENARIO_SUFIX}".json || true',
                'mv "$REPORTS_PATH"/logs_"${SCENARIO_SUFIX}" "$REPORTS_PATH"/logs_"${TEST_LIBRARY}"_"${ONBOARDING_FILTER_WEBLOG}"_"${SCENARIO_SUFIX}_${DEFAULT_VMS}" || true',
            ],
            "retry": {
                "max": "2",
                "when": [
                    "unknown_failure",
                    "data_integrity_failure",
                    "runner_system_failure",
                    "scheduler_failure",
                    "api_failure",
                ],
                "exit_codes": [3],
            },
            "artifacts": {"when": "always", "paths": ["system-tests/reports/"]},
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
                "extends": ".base_job_onboarding_one_pipeline"
                if is_one_pipeline
                else ".base_job_onboarding_system_tests",
                "stage": scenario_name,
                "allow_failure": False,
                "needs": [],
                "variables": {
                    # Force gitlab to keep the exit code as 3 if the job fails with exit code 3
                    "FF_USE_NEW_BASH_EVAL_STRATEGY": "true",
                    "TEST_LIBRARY": language,
                    "SCENARIO": scenario_name,
                    "WEBLOG": weblog_name,
                    "ONBOARDING_FILTER_ENV": env,
                    "DD_INSTALLER_LIBRARY_VERSION": installer_library_version,
                    "DD_INSTALLER_INJECTOR_VERSION": installer_injector_version,
                },
                # Remove rules if you want to run the jobs when you clic on the execute button of the child pipeline
                "rules": [rule_run, {"when": "manual", "allow_failure": True}],
                "script": [
                    "cat ~/.aws/config",
                    "echo $AWS_PROFILE",
                    "echo '--------AWS_VAULT--------'",
                    "echo $AWS_VAULT",
                    "echo 'AWS DONE'",
                    "./build.sh -i runner",
                    "timeout 3000 ./run.sh $SCENARIO --vm-weblog $WEBLOG --vm-env $ONBOARDING_FILTER_ENV --vm-library $TEST_LIBRARY --vm-provider aws --report-run-url $CI_JOB_URL --report-environment $ONBOARDING_FILTER_ENV --vm-default-vms All --vm-only "
                    + vm.name,
                ],
            }
            if is_one_pipeline:
                # If it's a one pipeline, we need to clone the system-tests repo and the job is going to be executed automatically
                pipeline[f"{vm.name}_{weblog_name}_{scenario_name}"]["rules"] = [{"when": "always"}]
                pipeline[f"{vm.name}_{weblog_name}_{scenario_name}"]["script"].insert(
                    0, "git clone https://git@github.com/DataDog/system-tests.git system-tests"
                )
                pipeline[f"{vm.name}_{weblog_name}_{scenario_name}"]["script"].insert(1, "cd system-tests")

        if not is_one_pipeline:
            # Cache management for the system-tests pipeline
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
            # Remove rules if you want to run the jobs when you clic on the execute button of the child pipeline.
            "rules": [{"when": "manual", "allow_failure": True}],
            "script": [
                "./build.sh -i runner",
                "./run.sh $SCENARIO --vm-weblog $WEBLOG --vm-env prod --vm-library $TEST_LIBRARY --vm-provider aws --vm-default-vms All --vm-only "
                + vm.name,
            ],
        }
    return pipeline


def _generate_fpd_gitlab_script():
    fpd_push_script = [
        'if [ "$CI_COMMIT_BRANCH" = "main" ]; then',
        'export FP_IMPORT_URL=$(aws ssm get-parameter --region us-east-1 --name ci.system-tests.fp-import-url --with-decryption --query "Parameter.Value" --out text)',
        'export FP_API_KEY=$(aws ssm get-parameter --region us-east-1 --name ci.system-tests.fp-api-key --with-decryption --query "Parameter.Value" --out text)',
        "for folder in reports/logs*/ ; do",
        '  echo "Checking folder: ${folder}"',
        "  for filename in ./${folder}*_feature_parity.json; do",
        "    if [ -e ${filename} ]",
        "    then",
        '      echo "Processing report: ${filename}"',
        '      curl -X POST ${FP_IMPORT_URL} --fail --header "Content-Type: application/json" --header "FP_API_KEY: ${FP_API_KEY}" --data "@${filename}" --include',
        "    fi",
        "  done",
        "done",
        "fi",
    ]
    return fpd_push_script
