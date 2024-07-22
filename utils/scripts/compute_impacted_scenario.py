from collections import defaultdict
import json
import os
import re
from manifests.parser.core import load as load_manifests
from utils._context._scenarios import ScenarioGroup


def handle_labels(labels: list[str], scenarios_groups: set[str]):

    if "run-all-scenarios" in labels:
        scenarios_groups.add(ScenarioGroup.ALL.value)
    else:
        if "run-integration-scenarios" in labels:
            scenarios_groups.add(ScenarioGroup.INTEGRATIONS.value)
        if "run-sampling-scenario" in labels:
            scenarios_groups.add(ScenarioGroup.SAMPLING.value)
        if "run-profiling-scenario" in labels:
            scenarios_groups.add(ScenarioGroup.PROFILING.value)
        if "run-debugger-scenarios" in labels:
            scenarios_groups.add(ScenarioGroup.DEBUGGER.value)
        if "run-appsec-scenarios" in labels:
            scenarios_groups.add(ScenarioGroup.APPSEC.value)
        if "run-open-telemetry-scenarios" in labels:
            scenarios_groups.add(ScenarioGroup.OPEN_TELEMETRY.value)
        if "run-parametric-scenario" in labels:
            scenarios_groups.add(ScenarioGroup.PARAMETRIC.value)
        if "run-graphql-scenarios" in labels:
            scenarios_groups.add(ScenarioGroup.GRAPHQL.value)
        if "run-libinjection-scenarios" in labels:
            scenarios_groups.add(ScenarioGroup.LIB_INJECTION.value)


def main():
    scenarios = set(["DEFAULT"])  # always run the default scenario
    scenarios_groups = set()

    event_name = os.environ["GITHUB_EVENT_NAME"]
    ref = os.environ["GITHUB_REF"]

    if event_name == "schedule" or ref == "refs/heads/main":
        scenarios_groups.add(ScenarioGroup.ALL.value)

    elif event_name == "pull_request":
        labels = json.loads(os.environ["GITHUB_PULL_REQUEST_LABELS"])
        label_names = [label["name"] for label in labels]
        handle_labels(label_names, scenarios_groups)

        # this file is generated with
        # ./run.sh MOCK_THE_TEST --collect-only --scenario-report
        with open("logs_mock_the_test/scenarios.json", "r", encoding="utf-8") as f:
            scenario_map = json.load(f)

        modified_nodeids = set()

        new_manifests = load_manifests("manifests/")
        old_manifests = load_manifests("original/manifests/")

        for nodeid in set(list(new_manifests.keys()) + list(old_manifests.keys())):
            if (
                nodeid not in old_manifests
                or nodeid not in new_manifests
                or new_manifests[nodeid] != old_manifests[nodeid]
            ):
                modified_nodeids.add(nodeid)

        scenarios_by_files = defaultdict(set)
        for nodeid in scenario_map:
            file = nodeid.split(":", 1)[0]
            scenarios_by_files[file].add(scenario_map[nodeid])

            for modified_nodeid in modified_nodeids:
                if nodeid.startswith(modified_nodeid):
                    scenarios.add(scenario_map[nodeid])
                    break

        # this file is generated with
        #   git fetch origin ${{ github.event.pull_request.base.sha || github.sha }}
        #   git diff --name-only HEAD ${{ github.event.pull_request.base.sha || github.sha }} >> modified_files.txt

        with open("modified_files.txt", "r", encoding="utf-8") as f:
            modified_files = [line.strip() for line in f.readlines()]

        for file in modified_files:

            if file.startswith("tests/"):
                if file == "tests/test_schemas.py":
                    # this file is tested in all end-to-end scenarios
                    scenarios_groups.add(ScenarioGroup.END_TO_END.value)
                elif file.startswith("tests/auto_inject"):
                    # Nothing to do, onboarding test run on gitlab nightly or manually
                    pass
                elif file.endswith("/utils.py") or file.endswith("/conftest.py"):
                    # particular use case for modification in tests/ of a file utils.py or conftest.py
                    # in that situation, takes all scenarios executed in tests/<path>/

                    folder = "/".join(file.split("/")[:-1]) + "/"  # python trickery to remove last element

                    for sub_file in scenarios_by_files:
                        if sub_file.startswith(folder):
                            scenarios.update(scenarios_by_files[sub_file])

            else:
                # Map of file patterns -> scenario group:
                #
                # * The first matching pattern is applied
                # * Others are ignored (so order is important)
                # * If no pattern matches -> error
                files_map = {
                    ## scenarios specific folder
                    r"parametric/.*": None,  # Legacy folder
                    r"lib-injection/.*": ScenarioGroup.LIB_INJECTION.value,
                    ## nothing to do folders
                    r"manifests/.*": None,  # already handled by the manifest comparison
                    r"docs/.*": None,  # nothing to do
                    r"binaries/.*": None,  # nothing to do
                    r"\.circleci/.*": None,  # nothing to do
                    r"\.vscode/.*": None,  # nothing to do
                    ## .github folder
                    r"\.github/workflows/run-parametric\.yml": ScenarioGroup.PARAMETRIC.value,
                    r"\.github/.*": None,  # nothing to do??
                    ## utils/ folder
                    r"utils/interfaces/schemas.*": ScenarioGroup.END_TO_END.value,
                    r"utils/_context/_scenarios/open_telemetry\.py": ScenarioGroup.OPEN_TELEMETRY.value,
                    r"utils/scripts/compute_impacted_scenario\.py": None,
                    #### Onboarding cases
                    r"utils/onboarding.*": None,
                    r"utils/virtual_machine.*": None,
                    r"utils/build/virtual_machine.*": None,
                    r"utils/_context/_scenarios/auto_injection\.py": None,
                    r"utils/_context/virtual_machine\.py": None,
                    #### Parametric case
                    r"utils/_context/_scenarios/parametric\.py": ScenarioGroup.PARAMETRIC.value,
                    r"utils/parametric/.*": ScenarioGroup.PARAMETRIC.value,
                    ### else, run all
                    r"utils/.*": ScenarioGroup.ALL.value,
                    ## few files with no effect
                    r"\.dockerignore": None,
                    r"\.gitattributes": None,
                    r"\.gitignore": None,
                    r"\.gitlab-ci\.yml": None,
                    r"\.shellcheck": None,
                    r"\.shellcheckrc": None,
                    r"CHANGELOG\.md": None,
                    r"LICENSE": None,
                    r"LICENSE-3rdparty\.csv": None,
                    r"NOTICE": None,
                    r"Pulumi\.yaml": None,
                    r"README\.md": None,
                    r"format\.sh": None,
                    r"pyproject\.toml": None,
                    r"scenario_groups\.yml": None,
                    r"shell\.nix": None,
                    ## few files with lot of effect
                    r"requirements\.txt": ScenarioGroup.ALL.value,
                    r"run\.sh": ScenarioGroup.ALL.value,
                    r"conftest\.py": ScenarioGroup.ALL.value,
                }

                for pattern, scenario_group in files_map.items():
                    if re.fullmatch(pattern, file):
                        if scenario_group is not None:
                            scenarios_groups.add(scenario_group)
                        break
                else:
                    raise ValueError(
                        f"Unknown file: {file}. Please add it in this file, with the correct scenario group."
                    )

            # now get known scenarios executed in this file
            if file in scenarios_by_files:
                scenarios.update(scenarios_by_files[file])

    print("scenarios=" + ",".join(scenarios))
    print("scenarios_groups=" + ",".join(scenarios_groups))


if __name__ == "__main__":
    main()
