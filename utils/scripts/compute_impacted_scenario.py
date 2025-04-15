from collections import defaultdict
import json
import os
import re
from manifests.parser.core import load as load_manifests
from utils._context._scenarios import ScenarioGroup, scenarios, Scenario


class Result:
    def __init__(self) -> None:
        self.scenarios = {"DEFAULT"}  # always run the default scenario
        self.scenarios_groups: set[str] = set()

    def add_scenario_requirement(
        self, scenario_requirement: Scenario | ScenarioGroup | list[Scenario | ScenarioGroup] | None
    ) -> None:
        if scenario_requirement is None:
            pass
        elif isinstance(scenario_requirement, list):
            for req in scenario_requirement:
                self.add_scenario_requirement(req)
        elif isinstance(scenario_requirement, Scenario):
            self.add_scenario(scenario_requirement.name)
        elif isinstance(scenario_requirement, ScenarioGroup):
            self.add_scenario_group(scenario_requirement.value)
        else:
            raise TypeError(f"Unknown scenario requirement: {scenario_requirement}.")

    def add_scenario(self, scenario: str) -> None:
        if scenario == "EndToEndScenario":
            self.add_scenario_group(ScenarioGroup.END_TO_END.value)
        else:
            self.scenarios.add(scenario)

    def add_scenario_group(self, scenario_group: str) -> None:
        self.scenarios_groups.add(scenario_group)

    def add_scenarios(self, scenarios: set[str] | list[str]) -> None:
        for scenario in scenarios:
            self.add_scenario(scenario)

    def handle_labels(self, labels: list[str]) -> None:
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
                self.add_scenario(scenarios.parametric.name)
            if "run-graphql-scenarios" in labels:
                self.add_scenario_group(ScenarioGroup.GRAPHQL.value)
            if "run-docker-ssi-scenarios" in labels:
                self.add_scenario_group(ScenarioGroup.DOCKER_SSI.value)
            if "run-external-processing-scenarios" in labels:
                self.add_scenario_group(ScenarioGroup.EXTERNAL_PROCESSING.value)


def main() -> None:
    result = Result()

    if "GITLAB_CI" in os.environ:
        event_name = os.environ["CI_PIPELINE_SOURCE"]
        ref = os.environ["CI_COMMIT_REF_NAME"]
        print("CI_PIPELINE_SOURCE=" + event_name)
        print("CI_COMMIT_REF_NAME=" + ref)
        is_gilab = True
    else:
        event_name = os.environ.get("GITHUB_EVENT_NAME", "pull_request")
        ref = os.environ.get("GITHUB_REF", "fake-branch-name")
        is_gilab = False

    if event_name == "schedule" or ref == "refs/heads/main":
        result.add_scenario_group(ScenarioGroup.ALL.value)

    elif event_name in ("pull_request", "push"):
        if not is_gilab and "GITHUB_PULL_REQUEST_LABELS" in os.environ:
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
        for nodeid, scenario_names in scenario_map.items():
            file = nodeid.split(":", 1)[0]
            for scenario_name in scenario_names:
                scenarios_by_files[file].add(scenario_name)

            for modified_nodeid in modified_nodeids:
                if nodeid.startswith(modified_nodeid):
                    result.add_scenarios(scenario_names)
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

            else:
                # Map of file patterns -> scenario requirement:
                #
                # * The first matching pattern is applied
                # * Others are ignored (so order is important)
                # * If no pattern matches -> error
                #
                # requirement can be:
                #
                # * None: no scenario will be run
                # * a member of ScenarioGroup: the scenario group will be run
                # * a Scenario: the scenario will be run
                # * a list of ScenarioGroup or Scenario: all elements will be run
                #
                # please keep this keys sorted as they would have been in a file explorer
                files_map: dict[str, ScenarioGroup | Scenario | list[ScenarioGroup | Scenario] | None] = {
                    r"\.circleci/.*": None,
                    r"\.vscode/.*": None,
                    r"\.github/CODEOWNERS": None,
                    r"\.github/workflows/run-docker-ssi\.yml": ScenarioGroup.DOCKER_SSI,
                    r"\.github/workflows/run-end-to-end\.yml": ScenarioGroup.END_TO_END,
                    r"\.github/workflows/run-graphql\.yml": ScenarioGroup.GRAPHQL,
                    r"\.github/workflows/run-lib-injection\.yml": ScenarioGroup.LIB_INJECTION,
                    r"\.github/workflows/run-open-telemetry\.yml": ScenarioGroup.OPEN_TELEMETRY,
                    r"\.github/workflows/run-parametric\.yml": scenarios.parametric,
                    r"\.github/.*": None,
                    r"\.gitlab/aws_gitlab-ci.yml": ScenarioGroup.ONBOARDING,
                    r"\.gitlab/k8s_gitlab-ci.yml": ScenarioGroup.LIB_INJECTION,
                    r"\.gitlab/ssi_gitlab-ci.yml": ScenarioGroup.ONBOARDING,
                    r"binaries/.*": None,
                    r"docs/.*": None,
                    r"lib-injection/.*": ScenarioGroup.LIB_INJECTION,
                    r"manifests/.*": None,  # already handled by the manifest comparison
                    r"utils/_context/_scenarios/appsec_low_waf_timeout\.py": scenarios.appsec_low_waf_timeout,
                    r"utils/_context/_scenarios/auto_injection\.py": ScenarioGroup.ONBOARDING,
                    r"utils/_context/_scenarios/default\.py": scenarios.default,
                    r"utils/_context/_scenarios/integrations\.py": ScenarioGroup.INTEGRATIONS,
                    r"utils/_context/_scenarios/ipv6\.py": ScenarioGroup.IPV6,
                    r"utils/_context/_scenarios/open_telemetry\.py": ScenarioGroup.OPEN_TELEMETRY,
                    r"utils/_context/_scenarios/parametric\.py": scenarios.parametric,
                    r"utils/_context/_scenarios/profiling\.py": ScenarioGroup.PROFILING,
                    r"utils/_context/virtual_machine\.py": ScenarioGroup.ONBOARDING,
                    r"utils/build/docker/java_otel/.*": ScenarioGroup.OPEN_TELEMETRY,
                    r"utils/build/docker/nodejs_otel/.*": ScenarioGroup.OPEN_TELEMETRY,
                    r"utils/build/docker/python_otel/.*": ScenarioGroup.OPEN_TELEMETRY,
                    r"utils/build/docker/\w+/parametric/.*": scenarios.parametric,
                    r"utils/build/docker/.*": [
                        ScenarioGroup.END_TO_END,
                        ScenarioGroup.OPEN_TELEMETRY,
                    ],
                    r"utils/build/ssi/.*": ScenarioGroup.DOCKER_SSI,
                    r"utils/build/virtual_machine/.*": ScenarioGroup.ONBOARDING,
                    r"utils/docker_ssi/.*": ScenarioGroup.DOCKER_SSI,
                    r"utils/interfaces/schemas.*": ScenarioGroup.END_TO_END,
                    r"utils/k8s_lib_injection.*": ScenarioGroup.LIB_INJECTION,
                    r"utils/onboarding.*": ScenarioGroup.ONBOARDING,
                    r"utils/parametric/.*": scenarios.parametric,
                    r"utils/telemetry/.*": ScenarioGroup.TELEMETRY,
                    r"utils/proxy/.*": [
                        ScenarioGroup.END_TO_END,
                        ScenarioGroup.OPEN_TELEMETRY,
                        ScenarioGroup.EXTERNAL_PROCESSING,
                    ],
                    r"utils/scripts/check_version\.sh": None,
                    r"utils/scripts/compute_impacted_scenario\.py": None,
                    r"utils/scripts/get-nightly-logs\.py": None,
                    r"utils/scripts/get-workflow-summary\.py": None,
                    r"utils/scripts/parametric/.*": scenarios.parametric,
                    r"utils/virtual_machine/.*": ScenarioGroup.ONBOARDING,
                    r"utils/.*": ScenarioGroup.ALL,
                    r"\.dockerignore": None,
                    r"\.gitattributes": None,
                    r"\.gitignore": None,
                    r"\.gitlab-ci\.yml": None,
                    r"\.shellcheck": None,
                    r"\.shellcheckrc": None,
                    r"\.yamlfmt": None,
                    r"\.yamllint": None,
                    r"conftest\.py": ScenarioGroup.ALL,
                    r"CHANGELOG\.md": None,
                    r"flake\.lock": None,
                    r"format\.sh": None,
                    r"LICENSE": None,
                    r"LICENSE-3rdparty\.csv": None,
                    r"NOTICE": None,
                    r"Pulumi\.yaml": None,
                    r"pyproject\.toml": None,
                    r"README\.md": None,
                    r"requirements\.txt": ScenarioGroup.ALL,
                    r"run\.sh": ScenarioGroup.ALL,
                    r".*\.nix": None,
                }

                for pattern, scenario_requirement in files_map.items():
                    if re.fullmatch(pattern, file):
                        result.add_scenario_requirement(scenario_requirement)
                        # on first matching pattern, stop the loop
                        break
                else:
                    raise ValueError(
                        f"Unknown file: {file}. Please add it in this file, with the correct scenario requirement."
                    )

            # now get known scenarios executed in this file
            if file in scenarios_by_files:
                result.add_scenarios(scenarios_by_files[file])

    print("scenarios=" + ",".join(result.scenarios))
    print("scenarios_groups=" + ",".join(result.scenarios_groups))


if __name__ == "__main__":
    main()
