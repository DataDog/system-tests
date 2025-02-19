import yaml


def generate_job_unique_name(dictionary, key, value) -> str:
    new_key = key
    while new_key in dictionary:
        new_key += "."
    dictionary[new_key] = value
    return new_key


def print_aws_gitlab_pipeline(language, aws_matrix, ci_environment) -> None:
    result_pipeline = {}  # type: dict
    result_pipeline["include"] = []
    result_pipeline["stages"] = []
    pipeline_file = ".gitlab/aws_gitlab-ci.yml"
    pipeline_data = None
    with open(pipeline_file, encoding="utf-8") as f:
        pipeline_data = yaml.load(f, Loader=yaml.FullLoader)  # noqa: S506

    result_pipeline["include"] = pipeline_data["include"]
    # Copy the base job
    result_pipeline[".base_job_onboarding_system_tests"] = pipeline_data[".base_job_onboarding_system_tests"]
    # Create the jobs by scenario. Each job (scenario-weblog) will have a parallel matrix with the virtual machines
    for scenario, weblogs in aws_matrix.items():
        result_pipeline["stages"].append(scenario)
        for weblog, vms in weblogs.items():
            weblog_job = generate_job_unique_name(result_pipeline, weblog, {})
            result_pipeline[weblog_job]["stage"] = scenario
            result_pipeline[weblog_job]["extends"] = ".base_job_onboarding_system_tests"
            result_pipeline[weblog_job]["variables"] = {}
            result_pipeline[weblog_job]["variables"]["TEST_LIBRARY"] = language
            result_pipeline[weblog_job]["variables"]["SCENARIO"] = scenario
            result_pipeline[weblog_job]["variables"]["WEBLOG"] = weblog
            result_pipeline[weblog_job]["variables"]["ONBOARDING_FILTER_ENV"] = ci_environment
            result_pipeline[weblog_job]["parallel"] = {"matrix": []}
            for vm in vms:
                result_pipeline[weblog_job]["parallel"]["matrix"].append(
                    {
                        "VIRTUAL_MACHINE": vm,
                    }
                )

    # TODO: write the gitlab pipeline
    pipeline_yml = yaml.dump(result_pipeline, sort_keys=False, default_flow_style=False)
    print(pipeline_yml)
