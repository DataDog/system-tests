import json
import yaml
import argparse


def generate_gitlab_pipeline(languages):
    pipeline = {
        "stages": ["K8S_LIB_INJECTION"],
        ".k8s_lib_injection_base": {
            "image": "registry.ddbuild.io/ci/libdatadog-build/system-tests:48436362",
            "tags": ["runner:docker"],
            "stage": "K8S_LIB_INJECTION",
            "script": [
                "./build.sh -i runner",
                "source venv/bin/activate",
                "echo 'Running K8s Library Injection tests'",
                " ./run.sh ${K8S_SCENARIO} --k8s-library ${TEST_LIBRARY} --k8s-weblog ${K8S_WEBLOG} --k8s-weblog-img ${K8S_WEBLOG_IMG} --k8s-lib-init-img ${K8S_LIB_INIT_IMG} --k8s-cluster-version ${K8S_CLUSTER_VERSION}",
            ],
            "rules": [
                {"if": '$PARENT_PIPELINE_SOURCE == "schedule"', "when": "always"},
                {"when": "manual", "allow_failure": True},
            ],
            "after_script": [
                'SCENARIO_SUFIX=$(echo "${SCENARIO}" | tr "[:upper:]" "[:lower:]")',
                'REPORTS_PATH="reports/"',
                'mkdir -p "$REPORTS_PATH"',
                'cp -R logs_"${SCENARIO_SUFIX}" $REPORTS_PATH/',
                'mv "$REPORTS_PATH"/logs_"${SCENARIO_SUFIX}" "$REPORTS_PATH"/logs_"${TEST_LIBRARY}"_"${K8S_WEBLOG}"_"${SCENARIO_SUFIX}"',
            ],
            "dependencies": [],
            "artifacts": {"when": "always", "paths": ["reports/"]},
        },
    }

    for language in languages:
        pipeline["k8s_" + language] = {
            "extends": ".k8s_lib_injection_base",
            "variables": {"TEST_LIBRARY": language},
            "parallel": {
                "matrix": [
                    {
                        "K8S_WEBLOG": ["dd-djm-spark-test-app"],
                        "K8S_WEBLOG_IMG": ["ghcr.io/datadog/system-tests/dd-djm-spark-test-app:latest"],
                        "K8S_SCENARIO": ["K8S_LIB_INJECTION_SPARK_DJM"],
                        "K8S_LIB_INIT_IMG": [
                            "gcr.io/datadoghq/dd-lib-java-init:latest",
                            "ghcr.io/datadog/dd-trace-java/dd-lib-java-init:latest_snapshot",
                        ],
                        "K8S_CLUSTER_VERSION": ["7.57.0", "7.59.0"],
                    },
                    {
                        "K8S_WEBLOG": ["dd-lib-java-init-test-app"],
                        "K8S_WEBLOG_IMG": ["ghcr.io/datadog/system-tests/dd-lib-java-init-test-app:latest"],
                        "K8S_SCENARIO": [
                            "K8S_LIB_INJECTION",
                            "K8S_LIB_INJECTION_UDS",
                            "K8S_LIB_INJECTION_NO_AC",
                            "K8S_LIB_INJECTION_NO_AC_UDS",
                            "K8S_LIB_INJECTION_PROFILING_DISABLED",
                            "K8S_LIB_INJECTION_PROFILING_ENABLED",
                            "K8S_LIB_INJECTION_PROFILING_OVERRIDE",
                        ],
                        "K8S_LIB_INIT_IMG": [
                            "gcr.io/datadoghq/dd-lib-java-init:latest",
                            "ghcr.io/datadog/dd-trace-java/dd-lib-java-init:latest_snapshot",
                        ],
                        "K8S_CLUSTER_VERSION": ["7.56.2", "7.57.0", "7.59.0"],
                    },
                ]
            },
        }

    # .k8s_lib_injection_base:
    # image: registry.ddbuild.io/ci/libdatadog-build/system-tests:48436362
    # tags: [ "runner:docker" ]
    # stage: k8s_lib_injection
    # rules:
    # - if: $CI_PIPELINE_SOURCE == "schedule"
    #  when: always
    # - when: manual
    # variables:
    #   TEST_LIBRARY: "xyz"
    #   K8S_WEBLOG: "xyz"
    #   K8S_WEBLOG_IMG: "xyz"
    #   K8S_SCENARIO: "xyz"
    #   K8S_LIB_INIT_IMG: "xyz"
    #   K8S_CLUSTER_VERSION: "xyz"
    # script:
    #   - ./build.sh -i runner # rebuild runner in case there were changes
    #   - source venv/bin/activate
    #   - python --version
    #   - pip freeze
    #   - ./run.sh ${K8S_SCENARIO} --k8s-library ${TEST_LIBRARY} --k8s-weblog ${K8S_WEBLOG} --k8s-weblog-img ${K8S_WEBLOG_IMG} --k8s-lib-init-img ${K8S_LIB_INIT_IMG} --k8s-cluster-version ${K8S_CLUSTER_VERSION}
    # after_script:
    #   - mkdir -p reports
    #   - cp -R logs_*/ reports/
    #   - kind delete clusters --all || true
    # artifacts:
    #   when: always
    #   paths:
    #     - reports/

    # Add FPD push script
    # pipeline[".base_ssi_job"]["after_script"].extend(_generate_fpd_gitlab_script())

    return pipeline


def _generate_fpd_gitlab_script():
    return [
        'if [ "$CI_COMMIT_BRANCH" = "main" ]; then',
        "for folder in reports/logs*/ ; do",
        '  echo "Checking folder: ${folder}"',
        "  for filename in ./${folder}feature_parity.json; do",
        "    if [ -e ${filename} ]",
        "    then",
        '      echo "Processing report: ${filename}"',
        '      curl -X POST ${FP_IMPORT_URL} --fail --header "Content-Type: application/json" --header "FP_API_KEY: ${FP_API_KEY}" --data "@${filename}" --include',
        "    fi",
        "  done",
        "done",
        "fi",
    ]
    # return fpd_push_script


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", required=True, type=str, choices=["json", "yaml"], help="json or yaml")
    parser.add_argument("--output-file", required=False, type=str)
    parser.add_argument("--language", required=False, type=str, help="Only generate config for single language")

    args = parser.parse_args()
    if args.language:
        languages = [args.language]
    else:
        languages = ["java", "python", "nodejs", "dotnet", "ruby", "php"]

    pipeline = generate_gitlab_pipeline(languages)

    output = (
        json.dumps(pipeline, sort_keys=False)
        if args.format == "json"
        else yaml.dump(pipeline, sort_keys=False, default_flow_style=False)
    )
    if args.output_file is not None:
        with open(args.output_file, "w") as f:
            f.write(output)


if __name__ == "__main__":
    main()
