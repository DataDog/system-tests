from collections import defaultdict
import json
import yaml


def load_json(file_path) -> dict:
    with open(file_path, "r") as file:
        return json.load(file)


def get_weblog_spec(weblogs_spec, weblog_name) -> dict:
    for entry in weblogs_spec:
        if weblog_name == entry["name"]:
            return entry
    raise ValueError(f"Weblog variant {weblog_name} not found (please aws_ssi.json)")


def generate_aws_matrix(virtual_machines_file, aws_ssi_file, scenarios, language) -> dict:
    """Load the json files (the virtual_machine supported by the system  and the scenario-weblog definition)
    and calculates the matrix "scenario" - "weblog" - "virtual machine" given a list of scenarios and a language.
    """

    # Load the supported vms and the aws matrix definition
    raw_data_virtual_machines = load_json(virtual_machines_file)["virtual_machines"]
    aws_ssi = load_json(aws_ssi_file)
    # Remove items where "disabled" is set to True
    virtual_machines = [item for item in raw_data_virtual_machines if item.get("disabled") is not True]

    scenario_matrix = aws_ssi["scenario_matrix"]
    weblogs_spec = aws_ssi["weblogs_spec"][language]
    results = defaultdict(lambda: defaultdict(list))  # type: dict

    for entry in scenario_matrix:
        applicable_scenarios = entry["scenarios"]
        weblogs = entry["weblogs"]

        for scenario in scenarios:
            if scenario in applicable_scenarios:
                for weblog_entry in weblogs:
                    if language in weblog_entry:
                        for weblog in weblog_entry[language]:
                            weblog_spec = get_weblog_spec(weblogs_spec, weblog)
                            excluded = set(weblog_spec.get("excluded_os_branches", []))
                            exact = set(weblog_spec.get("exact_os_branches", []))

                            for vm in virtual_machines:
                                os_branch = vm["os_branch"]
                                if exact:
                                    if os_branch in exact:
                                        results[scenario][weblog].append(vm["name"])
                                elif os_branch not in excluded or (not excluded and not exact):
                                    results[scenario][weblog].append(vm["name"])
    return results


def generate_job_unique_name(dictionary, key, value) -> str:
    new_key = key
    while new_key in dictionary:
        new_key += "."
    dictionary[new_key] = value
    return new_key


def generate_aws_gitlab_pipeline(language, aws_matrix, ci_environment) -> dict:
    result_pipeline = {}  # type: dict
    result_pipeline["stages"] = []
    pipeline_file = ".gitlab/aws_gitlab-ci.yml"
    pipeline_data = None
    with open(pipeline_file, encoding="utf-8") as f:
        pipeline_data = yaml.load(f, Loader=yaml.FullLoader)  # noqa: S506
    # Copy the base job
    result_pipeline[".base_job_aws"] = pipeline_data[".base_job_aws"]
    # Create the jobs by scenario. Each job (scenario-weblog) will have a parallel matrix with the virtual machines
    for scenario, weblogs in aws_matrix.items():
        result_pipeline["stages"].append(scenario)
        for weblog, vms in weblogs.items():
            weblog_job = generate_job_unique_name(result_pipeline, weblog, {})
            result_pipeline[weblog_job]["stage"] = scenario
            result_pipeline[weblog_job]["extends"] = ".base_job_aws"
            result_pipeline[weblog_job]["variables"] = {}
            result_pipeline[weblog_job]["variables"]["TEST_LIBRARY"] = language
            result_pipeline[weblog_job]["variables"]["SCENARIO"] = scenario
            result_pipeline[weblog_job]["variables"]["WEBLOG"] = weblog
            result_pipeline[weblog_job]["variables"]["ONBOARDING_FILTER_ENV"] = ci_environment
            result_pipeline[weblog_job]["parallel"] = {"matrix": vms}
    return result_pipeline
