from ruamel.yaml import YAML
from typing import Any, TextIO
from utils._context._scenarios import scenario_groups
from manifests.parser.core import load as load_manifests
from collections import defaultdict
import os
import sys
import argparse
import re
import json


# do not include otel in system-tests CI by default, as the staging backend is not stable enough
LIBRARIES = {
    "cpp",
    "cpp_httpd",
    "cpp_nginx",
    "dotnet",
    "golang",
    "java",
    "nodejs",
    "php",
    "python",
    "ruby",
    "python_lambda",
    "rust",
}


def transform_pattern(pattern: str) -> str:
    return pattern.replace(".", r"\.").replace("*", ".*")


def check_scenario(val: Any) -> bool:  # noqa: ANN401
    match val:
        case set():
            return True
        case str():
            return hasattr(scenario_groups, val)
        case list():
            return all(hasattr(scenario_groups, scenario) for scenario in val)
        case _:
            return False


def check_libraries(val: Any) -> bool:  # noqa: ANN401
    match val:
        case set():
            return True
        case str():
            return val in LIBRARIES
        case list():
            return all(library in LIBRARIES for library in val)
        case _:
            return False


class Param:
    def __init__(self):
        self.libraries: set[str] = LIBRARIES
        self.scenarios: set[str] = {scenario_groups.all.name}


def parse() -> dict[str, Param]:
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # noqa: PTH120, PTH100
    yml_path = os.path.join(root_dir, "test-selection.yml")

    yaml = YAML()
    with open(yml_path, "r") as file:
        data = yaml.load(file)["patterns"]

    try:
        ret = {}
        for entry in data:
            pattern, param = next(iter(entry.items()))
            pattern = transform_pattern(pattern)
            libraries = param.get("libraries", "ALL") or set()
            scenarios = param.get("scenario_groups", "ALL") or set()

            if pattern not in ret:
                ret[pattern] = Param()

            if libraries != "ALL":
                if check_libraries(libraries):
                    ret[pattern].libraries = set(libraries)
                else:
                    raise Exception(f"One or more of the libraries does not exist: {libraries}")  # noqa: TRY002

            if scenarios != "ALL":
                if check_scenario(scenarios):
                    ret[pattern].scenarios = set(scenarios)
                else:
                    raise Exception(f"One or more of the scenario groups does not exist: {scenarios}")  # noqa: TRY002

        return ret

    except AttributeError:
        raise Exception("Error in the test selection file") from None  # noqa: TRY002


def library_processing(impacts: dict[str, Param], output: str) -> None:
    import json
    import os
    import re

    lambda_libraries = ["python_lambda"]
    otel_libraries = ["java_otel", "python_otel"]  # , "nodejs_otel"]

    # nodejs_otel is broken: dependancy needs to be pinned
    # libraries = "cpp|cpp_httpd|cpp_nginx|dotnet|golang|java|nodejs|php|python|ruby|java_otel|python_otel|nodejs_otel|python_lambda|rust"  # noqa: E501
    libraries = "|".join(list(LIBRARIES) + lambda_libraries + otel_libraries)

    def get_impacted_libraries(modified_file: str, impacts: dict[str, Param]) -> list[str]:
        # """Return the list of impacted libraries by this file"""
        # if modified_file.endswith((".md", ".rdoc", ".txt")):
        #     # modification in documentation file
        #     return []
        #
        # files_with_no_impact = [
        #     "utils/scripts/activate-easy-wins.py",
        #     "utils/scripts/compute-impacted-libraries.py",
        #     ".github/workflows/compute-impacted-libraries.yml",
        #     ".github/workflows/debug-harness.yml",
        # ]
        # if modified_file in files_with_no_impact:
        #     return []
        #
        # lambda_proxy_patterns = [
        #     "utils/build/docker/lambda_proxy/.+",
        #     "utils/build/docker/lambda-proxy.Dockerfile",
        # ]
        # for pattern in lambda_proxy_patterns:
        #     if re.match(pattern, modified_file):
        #         return lambda_libraries
        #
        # if modified_file in ("utils/_context/_scenarios/open_telemetry.py",):
        #     return otel_libraries
        #
        patterns = [
            rf"^manifests/({libraries})\.",
            rf"^utils/build/docker/({libraries})/",
            rf"^lib-injection/build/docker/({libraries})/",
            rf"^utils/build/build_({libraries})_base_images.sh",
        ]

        for pattern in patterns:
            if match := re.search(pattern, modified_file):
                return [match[1]]

        for pattern, requirement in impacts.items():
            if re.fullmatch(pattern, modified_file):
                if requirement.libraries:
                    return list(requirement.libraries)
                break

        return list(LIBRARIES)

    def main_library_processing(impacts: dict[str, Param], output: str) -> None:
        result = set()

        if os.environ.get("GITHUB_EVENT_NAME", "pull_request") != "pull_request":
            print("Not in PR => run all libraries")
            result |= set(LIBRARIES)

        else:
            pr_title = os.environ.get("GITHUB_PR_TITLE", "").lower()
            match = re.search(rf"^\[({libraries})(?:@([^\]]+))?\]", pr_title)
            user_choice = None
            branch_selector = None
            prevent_library_selector_mismatch = True
            rebuild_lambda_proxy = False
            if match:
                print(f"PR title matchs => run {match[1]}")
                user_choice = match[1]
                result.add(user_choice)

                # if users specified a branch, another job will prevent the merge
                # so let user do what he/she wants :
                branch_selector = match[2]
                prevent_library_selector_mismatch = branch_selector is None

            print("Inspect modified files to determine impacted libraries...")

            with open("modified_files.txt", "r", encoding="utf-8") as f:
                modified_files: list[str] = [line.strip() for line in f]

            for file in modified_files:
                impacted_libraries = get_impacted_libraries(file, impacts)

                if file.endswith((".md", ".rdoc", ".txt")):
                    # modification in documentation file
                    continue

                if file in (
                    "utils/build/docker/lambda_proxy/pyproject.toml",
                    "utils/build/docker/lambda-proxy.Dockerfile",
                ):
                    rebuild_lambda_proxy = True

                if user_choice is None:
                    # user let the script pick impacted libraries
                    result |= set(impacted_libraries)
                elif prevent_library_selector_mismatch and len(impacted_libraries) > 0:
                    # user specified a library in the PR title
                    # and there are some impacted libraries
                    if file.startswith("tests/"):
                        # modification in tests files are complex, trust user
                        ...
                    elif impacted_libraries != [user_choice]:
                        # only acceptable use case : impacted library exactly matches user choice
                        print(
                            f"""File {file} is modified, and it may impact {', '.join(impacted_libraries)}.
                            Please remove the PR title prefix [{user_choice}]"""
                        )
                        sys.exit(1)

        populated_result = [
            {
                "library": library,
                "version": "prod",
            }
            for library in sorted(result)
        ] + [
            {
                "library": library,
                "version": "dev",
            }
            for library in sorted(result)
            if "otel" not in library
        ]

        libraries_with_dev = [item["library"] for item in populated_result if item["version"] == "dev"]
        outputs = {
            "library_matrix": populated_result,
            "libraries_with_dev": libraries_with_dev,
            "desired_execution_time": 600 if len(result) == 1 else 3600,
            "rebuild_lambda_proxy": rebuild_lambda_proxy,
        }

        if output:
            with open(output, "w", encoding="utf-8") as f:
                print_github_outputs(outputs, f)
        else:
            print_github_outputs(outputs, sys.stdout)

    def print_github_outputs(outputs: dict[str, Any], f: TextIO) -> None:
        for name, value in outputs.items():
            print(f"{name}={json.dumps(value)}", file=f)

    main_library_processing(impacts, output)


def scenario_processing(impacts: dict[str, Param], output: str) -> None:
    import os
    from typing import TYPE_CHECKING
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

    def main_scenario_processing(impacts: dict[str, Param], output: str) -> None:
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
                    # files_map: dict[str, ScenarioGroup | Scenario | list[ScenarioGroup | Scenario] | None] = {
                    #     r"\.cursor/rules/.*": None,
                    #     r"\.circleci/.*": None,
                    #     r"\.vscode/.*": None,
                    #     r"\.github/actions/pull_images/action.yml": scenario_groups.end_to_end,
                    #     r"\.github/CODEOWNERS": None,
                    #     r"\.github/workflows/daily-tag\.yml": None,
                    #     r"\.github/workflows/debug-harness\.yml": None,
                    #     r"\.github/workflows/run-docker-ssi\.yml": scenario_groups.docker_ssi,
                    #     r"\.github/workflows/run-end-to-end\.yml": scenario_groups.end_to_end,
                    #     r"\.github/workflows/run-graphql\.yml": scenario_groups.graphql,
                    #     r"\.github/workflows/run-lib-injection\.yml": scenario_groups.lib_injection,
                    #     r"\.github/workflows/run-open-telemetry\.yml": scenario_groups.open_telemetry,
                    #     r"\.github/workflows/run-parametric\.yml": scenarios.parametric,
                    #     r"\.github/workflows/run-exotics\.yml": scenario_groups.exotics,
                    #     r"\.github/.*": None,
                    #     r"\.gitlab/ssi_gitlab-ci.yml": [
                    #         scenario_groups.onboarding,
                    #         scenario_groups.lib_injection,
                    #         scenario_groups.docker_ssi,
                    #     ],
                    #     r"\.promptfoo/.*": None,
                    #     r"binaries/.*": None,
                    #     r"docs/.*": None,
                    #     r"lib-injection/.*": scenario_groups.lib_injection,
                    #     r"manifests/.*": None,  # already handled by the manifest comparison
                    #     r"repository\.datadog\.yml": None,
                    #     r"utils/_context/_scenarios/appsec_low_waf_timeout\.py": scenarios.appsec_low_waf_timeout,
                    #     r"utils/_context/_scenarios/aws_lambda\.py": scenario_groups.lambda_end_to_end,
                    #     r"utils/_context/_scenarios/auto_injection\.py": scenario_groups.onboarding,
                    #     r"utils/_context/_scenarios/default\.py": scenarios.default,
                    #     r"utils/_context/_scenarios/appsec_rasp\.py": scenarios.appsec_rasp,
                    #     r"utils/_context/_scenarios/endtoend\.py": scenario_groups.end_to_end,
                    #     r"utils/_context/_scenarios/integrations\.py": scenario_groups.integrations,
                    #     r"utils/_context/_scenarios/ipv6\.py": scenario_groups.ipv6,
                    #     r"utils/_context/_scenarios/open_telemetry\.py": scenario_groups.open_telemetry,
                    #     r"utils/_context/_scenarios/parametric\.py": scenarios.parametric,
                    #     r"utils/_context/_scenarios/profiling\.py": scenario_groups.profiling,
                    #     r"utils/_context/_scenarios/stream_processing_offload\.py": scenario_groups.stream_processing_offload,  # noqa: E501
                    #     r"utils/_context/virtual_machine\.py": scenario_groups.onboarding,
                    #     r"utils/build/docker/java_otel/.*": scenario_groups.open_telemetry,
                    #     r"utils/build/docker/lambda_proxy/.*": scenario_groups.lambda_end_to_end,
                    #     r"utils/build/docker/nodejs_otel/.*": scenario_groups.open_telemetry,
                    #     r"utils/build/docker/python_otel/.*": scenario_groups.open_telemetry,
                    #     r"utils/build/docker/python_lambda/.*": scenario_groups.appsec_lambda,
                    #     r"utils/build/docker/\w+/parametric/.*": scenarios.parametric,
                    #     r"utils/build/docker/.*": [
                    #         scenario_groups.end_to_end,
                    #         scenario_groups.open_telemetry,
                    #     ],
                    #     r"utils/build/ssi/.*": scenario_groups.docker_ssi,
                    #     r"utils/build/virtual_machine/.*": scenario_groups.onboarding,
                    #     r"utils/docker_ssi/.*": scenario_groups.docker_ssi,
                    #     r"utils/_features\.py": scenarios.default,
                    #     r"utils/interfaces/schemas.*": scenario_groups.end_to_end,
                    #     r"utils/k8s_lib_injection.*": scenario_groups.lib_injection,
                    #     r"utils/onboarding.*": scenario_groups.onboarding,
                    #     r"utils/parametric/.*": scenarios.parametric,
                    #     r"utils/telemetry/.*": scenario_groups.telemetry,
                    #     r"utils/proxy/.*": [
                    #         scenario_groups.end_to_end,
                    #         scenario_groups.open_telemetry,
                    #         scenario_groups.external_processing,
                    #         scenario_groups.stream_processing_offload,
                    #     ],
                    #     r"utils/scripts/activate-easy-wins\.py": None,
                    #     r"utils/scripts/add-system-tests-label-on-known-tickets\.py": None,
                    #     r"utils/scripts/ai/.*": None,
                    #     r"utils/scripts/check_version\.sh": None,
                    #     r"utils/scripts/compute_impacted_scenario\.py": None,
                    #     r"utils/scripts/get-nightly-logs\.py": None,
                    #     r"utils/scripts/get-workflow-summary\.py": None,
                    #     r"utils/scripts/grep-nightly-logs.py\.py": None,
                    #     r"utils/scripts/parametric/.*": scenarios.parametric,
                    #     r"utils/scripts/replay_scenarios\.sh": None,
                    #     r"utils/scripts/ssi_wizards/.*": None,
                    #     r"utils/scripts/update_protobuf\.sh": None,
                    #     r"utils/virtual_machine/.*": scenario_groups.onboarding,
                    #     r"utils/.*": scenario_groups.all,
                    #     r"\.cursorrules": None,
                    #     r"\.dockerignore": None,
                    #     r"\.gitattributes": None,
                    #     r"\.gitignore": None,
                    #     r"\.gitlab-ci\.yml": None,
                    #     r"\.shellcheck": None,
                    #     r"\.shellcheckrc": None,
                    #     r"\.yamlfmt": None,
                    #     r"\.yamllint": None,
                    #     r"conftest\.py": scenario_groups.all,
                    #     r"CHANGELOG\.md": None,
                    #     r"flake\.lock": None,
                    #     r"format\.sh": None,
                    #     r"LICENSE": None,
                    #     r"LICENSE-3rdparty\.csv": None,
                    #     r"NOTICE": None,
                    #     r"promptfooconfig\.yaml": None,
                    #     r"Pulumi\.yaml": None,
                    #     r"pyproject\.toml": None,
                    #     r"static-analysis\.datadog\.yml": None,
                    #     r"README\.md": None,
                    #     r"requirements\.txt": scenario_groups.all,
                    #     r"run\.sh": scenario_groups.all,
                    #     r".*\.nix": None,
                    # }

                    for pattern, requirement in impacts.items():
                        if re.fullmatch(pattern, file):
                            result.add_scenario_names(requirement.scenarios)
                            # on first matching pattern, stop the loop
                            break
                    else:
                        # raise ValueError(
                        #     f"Unknown file: {file}. Please add it in this file, with the correct scenario "
                        #     "requirement."
                        # )
                        result.add_scenario_group(scenario_groups.all)

                # now get known scenarios executed in this file
                if file in scenarios_by_files:
                    result.add_scenario_names(scenarios_by_files[file])

        if output:
            with open(output, "a", encoding="utf-8") as f:
                print("scenarios=" + ",".join(result.scenarios), file=f)
                print("scenarios_groups=" + ",".join(result.scenarios_groups), file=f)
        else:
            print("scenarios=" + ",".join(result.scenarios))
            print("scenarios_groups=" + ",".join(result.scenarios_groups))

    main_scenario_processing(impacts, output)


def main() -> None:
    parser = argparse.ArgumentParser(description="AWS SSI Registration Tool")
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="",
        help="Output file. If not provided, output to stdout",
    )

    args = parser.parse_args()
    output = args.output

    impacts = parse()
    if "GITLAB_CI" not in os.environ:
        library_processing(impacts, output)
    scenario_processing(impacts, output)


if __name__ == "__main__":
    main()
