from collections import defaultdict
import json
import os
import re
from manifests.parser.core import load as load_manifests
from utils._context._scenarios import ScenarioGroup


class Result:
    def __init__(self) -> None:
        self.scenarios = {"DEFAULT"}  # always run the default scenario
        self.scenarios_groups = set()

    def add_scenario(self, scenario: str):
        if scenario == "EndToEndScenario":
            self.add_scenario_group(ScenarioGroup.END_TO_END.value)
        else:
            self.scenarios.add(scenario)

    def add_scenario_group(self, scenario_group: str):
        self.scenarios_groups.add(scenario_group)

    def add_scenarios(self, scenarios: set[str]):
        for scenario in scenarios:
            self.add_scenario(scenario)

    def handle_labels(self, labels: list[str]):
        if "run-all-scenarios" in labels:
            self.add_scenario_group(ScenarioGroup.ALL.value)
        else:
            if "run-integration-scenarios" in labels:
                self.add_scenario_group(ScenarioGroup.INTEGRATIONS.value)
            if "run-sampling-scenario" in labels:
                self.add_scenario_group(ScenarioGroup.SAMPLING.value)
            if "run-profiling-scenario" in labels:
                self.add_scenario_group(ScenarioGroup.PROFILING.value)
            if "run-debugger-scenarios" in labels:
                self.add_scenario_group(ScenarioGroup.DEBUGGER.value)
            if "run-appsec-scenarios" in labels:
                self.add_scenario_group(ScenarioGroup.APPSEC.value)
            if "run-open-telemetry-scenarios" in labels:
                self.add_scenario_group(ScenarioGroup.OPEN_TELEMETRY.value)
            if "run-parametric-scenario" in labels:
                self.add_scenario_group(ScenarioGroup.PARAMETRIC.value)
            if "run-graphql-scenarios" in labels:
                self.add_scenario_group(ScenarioGroup.GRAPHQL.value)
            if "run-libinjection-scenarios" in labels:
                self.add_scenario_group(ScenarioGroup.LIB_INJECTION.value)
            if "run-docker-ssi-scenarios" in labels:
                self.add_scenario_group(ScenarioGroup.DOCKER_SSI.value)


def main():
    result = Result()

    event_name = os.environ["GITHUB_EVENT_NAME"]
    ref = os.environ["GITHUB_REF"]

    if event_name == "schedule" or ref == "refs/heads/main":
        result.add_scenario_group(ScenarioGroup.ALL.value)

    elif event_name == "pull_request":
        labels = json.loads(os.environ["GITHUB_PULL_REQUEST_LABELS"])
        label_names = [label["name"] for label in labels]
        result.handle_labels(label_names)

        # this file is generated with
        # ./run.sh MOCK_THE_TEST --collect-only --scenario-report
        with open("logs_mock_the_test/scenarios.json", encoding="utf-8") as f:
            scenario_map: dict[str, list[str]] = json.load(f)

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
        for nodeid, scenarios in scenario_map.items():
            file = nodeid.split(":", 1)[0]
            for scenario in scenarios:
                scenarios_by_files[file].add(scenario)

            for modified_nodeid in modified_nodeids:
                if nodeid.startswith(modified_nodeid):
                    result.add_scenarios(scenarios)
                    break

        # this file is generated with
        #   git fetch origin ${{ github.event.pull_request.base.sha || github.sha }}
        #   git diff --name-only HEAD ${{ github.event.pull_request.base.sha || github.sha }} >> modified_files.txt

        with open("modified_files.txt", encoding="utf-8") as f:
            modified_files = [line.strip() for line in f]

        for file in modified_files:
            if file.startswith("tests/"):
                if file.startswith("tests/auto_inject"):
                    # Nothing to do, onboarding test run on gitlab nightly or manually
                    pass
                elif file.endswith(("/utils.py", "/conftest.py", ".json")):
                    # particular use case for modification in tests/ of a file utils.py or conftest.py
                    # in that situation, takes all scenarios executed in tests/<path>/

                    # same for any json file

                    folder = "/".join(file.split("/")[:-1]) + "/"  # python trickery to remove last element

                    for sub_file in scenarios_by_files:
                        if sub_file.startswith(folder):
                            result.add_scenarios(scenarios_by_files[sub_file])

            elif file.startswith("utils/"):
                if file.startswith("utils/interfaces/schemas"):
                    result.add_scenario_group(ScenarioGroup.END_TO_END.value)
                else:
                    result.add_scenario_group(ScenarioGroup.ALL.value)

            elif file in (".dockerignore", ".gitignore", ".gitlab-ci.yml", "CHANGELOG.md",):
                # nothing to do
                pass

            elif file in ("LICENSE", "LICENSE-3rdparty.csv", "NOTICE", "Pulumi.yaml", "README.md", "build.sh"):
                # nothing to do
                pass

            elif file == "conftest.py":
                result.add_scenario_group(ScenarioGroup.ALL.value)

            elif file in ("format.sh", "pyproject.toml"):
                # nothing to do
                pass

            elif file in ("requirements.txt", "run.sh"):
                result.add_scenario_group(ScenarioGroup.ALL.value)

            elif file in ("scenario_groups.yml", "shell.nix", "flake.nix", "flake.lock", "treefmt.nix"):
                # nothing to do
                pass

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
                    r"\.github/workflows/run-lib-injection\.yml": ScenarioGroup.LIB_INJECTION.value,
                    r"\.github/workflows/run-docker-ssi\.yml": ScenarioGroup.DOCKER_SSI.value,
                    r"\.github/workflows/run-graphql\.yml": ScenarioGroup.GRAPHQL.value,
                    r"\.github/workflows/run-open-telemetry\.yml": ScenarioGroup.OPEN_TELEMETRY.value,
                    r"\.github/.*": None,  # nothing to do??
                    ## utils/ folder
                    r"utils/interfaces/schemas.*": ScenarioGroup.END_TO_END.value,
                    r"utils/_context/_scenarios/open_telemetry\.py": ScenarioGroup.OPEN_TELEMETRY.value,
                    r"utils/scripts/compute_impacted_scenario\.py": None,
                    r"utils/scripts/get-nightly-logs\.py": None,
                    #### Default scenario
                    r"utils/_context/_scenarios/default\.py": None,  # the default scenario is always executed
                    #### Onboarding cases
                    r"utils/onboarding.*": None,
                    r"utils/virtual_machine.*": None,
                    r"utils/build/virtual_machine.*": None,
                    r"utils/_context/_scenarios/auto_injection\.py": None,
                    r"utils/_context/virtual_machine\.py": None,
                    #### Parametric case
                    r"utils/build/docker/\w+/parametric/.*": ScenarioGroup.PARAMETRIC.value,
                    r"utils/_context/_scenarios/parametric\.py": ScenarioGroup.PARAMETRIC.value,
                    r"utils/parametric/.*": ScenarioGroup.PARAMETRIC.value,
                    r"utils/scripts/parametric/.*": ScenarioGroup.PARAMETRIC.value,
                    #### Integrations case
                    r"utils/_context/_scenarios/integrations\.py": ScenarioGroup.INTEGRATIONS.value,
                    #### Docker SSI case
                    r"utils/docker_ssi/.*": ScenarioGroup.DOCKER_SSI.value,
                    ### Profiling case
                    r"utils/_context/_scenarios/profiling\.py": ScenarioGroup.PROFILING.value,
                    ### IPv6
                    r"utils/_context/_scenarios/ipv6\.py": ScenarioGroup.IPV6.value,
                    ### otel weblog
                    r"utils/build/docker/nodejs_otel/.*": ScenarioGroup.OPEN_TELEMETRY.value,
                    ### else, run all
                    r"utils/.*": ScenarioGroup.ALL.value,
                    ## few files with no effect
                    r"\.github/CODEOWNERS": None,
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
                    ## Nix
                    r".*\.nix": None,
                    r"flake\.lock": None,
                    ## few files with lot of effect
                    r"requirements\.txt": ScenarioGroup.ALL.value,
                    r"run\.sh": ScenarioGroup.ALL.value,
                    r"conftest\.py": ScenarioGroup.ALL.value,
                }

                for pattern, scenario_group in files_map.items():
                    if re.fullmatch(pattern, file):
                        if scenario_group is not None:
                            result.add_scenario_group(scenario_group)
                        break
                else:
                    raise ValueError(
                        f"Unknown file: {file}. Please add it in this file, with the correct scenario group."
                    )

            # now get known scenarios executed in this file
            if file in scenarios_by_files:
                result.add_scenarios(scenarios_by_files[file])

    print("scenarios=" + ",".join(result.scenarios))
    print("scenarios_groups=" + ",".join(result.scenarios_groups))


if __name__ == "__main__":
    main()
