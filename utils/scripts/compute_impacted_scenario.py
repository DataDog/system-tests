from collections import defaultdict
import json
import os
import re
from typing import TYPE_CHECKING
from manifests.parser.core import load as load_manifests
from utils._context._scenarios import scenarios, Scenario, scenario_groups
from utils._context._scenarios.core import ScenarioGroup

if TYPE_CHECKING:
    from collections.abc import Iterable


class Result:
    def __init__(self) -> None:
        self.scenarios: set[str] = {scenarios.default.name}  # always run the default scenario
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
            self.add_scenario(scenario_requirement)
        elif isinstance(scenario_requirement, ScenarioGroup):
            self.add_scenario_group(scenario_requirement)
        else:
            raise TypeError(f"Unknown scenario requirement: {scenario_requirement}.")

    def add_scenario(self, scenario: Scenario) -> None:
        self.scenarios.add(scenario.name)

    def add_scenario_group(self, scenario_group: ScenarioGroup) -> None:
        self.scenarios_groups.add(scenario_group.name)

    def add_scenarios(self, scenarios: set[Scenario] | list[Scenario]) -> None:
        for scenario in scenarios:
            self.add_scenario(scenario)

    def add_scenario_names(self, scenario_names: set[str] | list[str]) -> None:
        for name in scenario_names:
            self.scenarios.add(name)


def main() -> None:
    result = Result()

    if "GITLAB_CI" in os.environ:
        event_name = os.environ.get("CI_PIPELINE_SOURCE", "push")
        ref = os.environ.get("CI_COMMIT_REF_NAME", "")
        print("CI_PIPELINE_SOURCE=" + event_name)
        print("CI_COMMIT_REF_NAME=" + ref)
    else:
        event_name = os.environ.get("GITHUB_EVENT_NAME", "pull_request")
        ref = os.environ.get("GITHUB_REF", "fake-branch-name")

    if event_name == "schedule" or ref == "refs/heads/main":
        result.add_scenario_group(scenario_groups.all)

    elif event_name in ("pull_request", "push"):
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

        scenarios_by_files: dict[str, set[str]] = defaultdict(set)
        scenario_names: Iterable[str]
        for nodeid, scenario_names in scenario_map.items():
            file = nodeid.split(":", 1)[0]
            for scenario_name in scenario_names:
                scenarios_by_files[file].add(scenario_name)

            for modified_nodeid in modified_nodeids:
                if nodeid.startswith(modified_nodeid):
                    result.add_scenario_names(scenario_names)
                    break

        # this file is generated with
        #   git fetch origin ${{ github.event.pull_request.base.sha || github.sha }}
        #   git diff --name-only HEAD ${{ github.event.pull_request.base.sha || github.sha }} >> modified_files.txt

        with open("modified_files.txt", encoding="utf-8") as f:
            modified_files = [line.strip() for line in f]

        for file in modified_files:
            if file.startswith("tests/"):
                if file.endswith(("/utils.py", "/conftest.py", ".json")):
                    # particular use case for modification in tests/ of a file utils.py or conftest.py
                    # in that situation, takes all scenarios executed in tests/<path>/

                    # same for any json file

                    folder = "/".join(file.split("/")[:-1]) + "/"  # python trickery to remove last element

                    for sub_file, scenario_names in scenarios_by_files.items():
                        if sub_file.startswith(folder):
                            result.add_scenario_names(scenario_names)

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
                    r"\.cursor/rules/.*": None,
                    r"\.circleci/.*": None,
                    r"\.vscode/.*": None,
                    r"\.github/actions/pull_images/action.yml": scenario_groups.end_to_end,
                    r"\.github/CODEOWNERS": None,
                    r"\.github/workflows/run-docker-ssi\.yml": scenario_groups.docker_ssi,
                    r"\.github/workflows/run-end-to-end\.yml": scenario_groups.end_to_end,
                    r"\.github/workflows/run-graphql\.yml": scenario_groups.graphql,
                    r"\.github/workflows/run-lib-injection\.yml": scenario_groups.lib_injection,
                    r"\.github/workflows/run-open-telemetry\.yml": scenario_groups.open_telemetry,
                    r"\.github/workflows/run-parametric\.yml": scenarios.parametric,
                    r"\.github/workflows/run-exotics\.yml": scenario_groups.exotics,
                    r"\.github/.*": None,
                    r"\.gitlab/ssi_gitlab-ci.yml": [
                        scenario_groups.onboarding,
                        scenario_groups.lib_injection,
                        scenario_groups.docker_ssi,
                    ],
                    r"\.promptfoo/.*": None,
                    r"binaries/.*": None,
                    r"docs/.*": None,
                    r"lib-injection/.*": scenario_groups.lib_injection,
                    r"manifests/.*": None,  # already handled by the manifest comparison
                    r"repository\.datadog\.yml": None,
                    r"utils/_context/_scenarios/appsec_low_waf_timeout\.py": scenarios.appsec_low_waf_timeout,
                    r"utils/_context/_scenarios/aws_lambda\.py": scenarios.appsec_lambda_default,
                    r"utils/_context/_scenarios/auto_injection\.py": scenario_groups.onboarding,
                    r"utils/_context/_scenarios/default\.py": scenarios.default,
                    r"utils/_context/_scenarios/integrations\.py": scenario_groups.integrations,
                    r"utils/_context/_scenarios/ipv6\.py": scenario_groups.ipv6,
                    r"utils/_context/_scenarios/open_telemetry\.py": scenario_groups.open_telemetry,
                    r"utils/_context/_scenarios/parametric\.py": scenarios.parametric,
                    r"utils/_context/_scenarios/profiling\.py": scenario_groups.profiling,
                    r"utils/_context/virtual_machine\.py": scenario_groups.onboarding,
                    r"utils/build/docker/java_otel/.*": scenario_groups.open_telemetry,
                    r"utils/build/docker/nodejs_otel/.*": scenario_groups.open_telemetry,
                    r"utils/build/docker/python_otel/.*": scenario_groups.open_telemetry,
                    r"utils/build/docker/python_lambda/.*": scenarios.appsec_lambda_default,
                    r"utils/build/docker/\w+/parametric/.*": scenarios.parametric,
                    r"utils/build/docker/.*": [
                        scenario_groups.end_to_end,
                        scenario_groups.open_telemetry,
                    ],
                    r"utils/build/ssi/.*": scenario_groups.docker_ssi,
                    r"utils/build/virtual_machine/.*": scenario_groups.onboarding,
                    r"utils/docker_ssi/.*": scenario_groups.docker_ssi,
                    r"utils/_features\.py": scenarios.default,
                    r"utils/interfaces/schemas.*": scenario_groups.end_to_end,
                    r"utils/k8s_lib_injection.*": scenario_groups.lib_injection,
                    r"utils/onboarding.*": scenario_groups.onboarding,
                    r"utils/parametric/.*": scenarios.parametric,
                    r"utils/telemetry/.*": scenario_groups.telemetry,
                    r"utils/proxy/.*": [
                        scenario_groups.end_to_end,
                        scenario_groups.open_telemetry,
                        scenario_groups.external_processing,
                    ],
                    r"utils/scripts/add-system-tests-label-on-known-tickets\.py": None,
                    r"utils/scripts/ai/.*": None,
                    r"utils/scripts/check_version\.sh": None,
                    r"utils/scripts/compute_impacted_scenario\.py": None,
                    r"utils/scripts/get-nightly-logs\.py": None,
                    r"utils/scripts/get-workflow-summary\.py": None,
                    r"utils/scripts/grep-nightly-logs.py\.py": None,
                    r"utils/scripts/parametric/.*": scenarios.parametric,
                    r"utils/scripts/replay_scenarios\.sh": None,
                    r"utils/scripts/ssi_wizards/.*": None,
                    r"utils/scripts/update_protobuf\.sh": None,
                    r"utils/virtual_machine/.*": scenario_groups.onboarding,
                    r"utils/.*": scenario_groups.all,
                    r"\.cursorrules": None,
                    r"\.dockerignore": None,
                    r"\.gitattributes": None,
                    r"\.gitignore": None,
                    r"\.gitlab-ci\.yml": None,
                    r"\.shellcheck": None,
                    r"\.shellcheckrc": None,
                    r"\.yamlfmt": None,
                    r"\.yamllint": None,
                    r"conftest\.py": scenario_groups.all,
                    r"CHANGELOG\.md": None,
                    r"flake\.lock": None,
                    r"format\.sh": None,
                    r"LICENSE": None,
                    r"LICENSE-3rdparty\.csv": None,
                    r"NOTICE": None,
                    r"promptfooconfig\.yaml": None,
                    r"Pulumi\.yaml": None,
                    r"pyproject\.toml": None,
                    r"static-analysis\.datadog\.yml": None,
                    r"README\.md": None,
                    r"requirements\.txt": scenario_groups.all,
                    r"run\.sh": scenario_groups.all,
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
                result.add_scenario_names(scenarios_by_files[file])

    print("scenarios=" + ",".join(result.scenarios))
    print("scenarios_groups=" + ",".join(result.scenarios_groups))


if __name__ == "__main__":
    main()
