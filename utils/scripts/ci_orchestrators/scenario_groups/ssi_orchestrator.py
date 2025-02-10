from collections import defaultdict
import json


def load_json(file_path) -> dict:
    with open(file_path, "r") as file:
        return json.load(file)


def get_weblog_spec(weblogs_spec, weblog_name) -> dict:
    for entry in weblogs_spec:
        if weblog_name == entry["name"]:
            return entry
    raise ValueError(f"Weblog variant {weblog_name} not found (please aws_ssi.json)")


def get_aws_matrix(virtual_machines_file, aws_ssi_file, scenarios, language) -> dict:
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
