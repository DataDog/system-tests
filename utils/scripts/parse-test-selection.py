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

LAMBDA_LIBRARIES = {"python_lambda"}
OTEL_LIBRARIES = {"java_otel", "python_otel"}  # , "nodejs_otel"]

ALL_LIBRARIES = LIBRARIES | LAMBDA_LIBRARIES | OTEL_LIBRARIES


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
            return val in ALL_LIBRARIES
        case list():
            return all(library in ALL_LIBRARIES for library in val)
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
        for pattern, param in data.items():
            # pattern, param = next(iter(entry.items()))
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
    libraries = "|".join(list(LIBRARIES) + lambda_libraries + otel_libraries)

    def get_impacted_libraries(modified_file: str, impacts: dict[str, Param]) -> list[str]:
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
                    for pattern, requirement in impacts.items():
                        if re.fullmatch(pattern, file):
                            result.scenarios_groups |= requirement.scenarios
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
