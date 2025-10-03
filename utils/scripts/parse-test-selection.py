import unittest
import yaml
from typing import Any, TextIO, TYPE_CHECKING
from manifests.parser.core import load as load_manifests
from collections import defaultdict, OrderedDict
import sys
import argparse
import re
import json
import os
from utils._context._scenarios import scenarios, Scenario, scenario_groups
from utils._context._scenarios.core import ScenarioGroup
if TYPE_CHECKING:
    from collections.abc import Iterable


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


def parse(inputs) -> dict[str, Param]:
    try:
        ret = OrderedDict()
        for raw_pattern, param in inputs.raw_impacts.items():
            # pattern, param = next(iter(entry.items()))
            pattern = transform_pattern(raw_pattern)
            libraries = param.get("libraries", "ALL") or set()
            scenarios = param.get("scenario_groups", "ALL") or set()

            if pattern not in ret:
                ret[pattern] = Param()

            if libraries != "ALL":
                if check_libraries(libraries):
                    if isinstance(libraries, str):
                        ret[pattern].libraries = {libraries}
                    else:
                        ret[pattern].libraries = set(libraries)
                else:
                    raise Exception(f"One or more of the libraries does not exist: {libraries}")  # noqa: TRY002

            if scenarios != "ALL":
                if check_scenario(scenarios):
                    if isinstance(scenarios, str):
                        ret[pattern].scenarios = {scenarios}
                    else:
                        ret[pattern].scenarios = set(scenarios)
                else:
                    raise Exception(f"One or more of the scenario groups does not exist: {scenarios}")  # noqa: TRY002

        return ret

    except AttributeError:
        raise Exception("Error in the test selection file") from None  # noqa: TRY002


def library_processing(impacts: dict[str, Param], inputs) -> None:

    libraries = "|".join(ALL_LIBRARIES)

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

    def main_library_processing(impacts: dict[str, Param], inputs) -> None:
        result = set()

        if inputs.event_name != "pull_request":
            print("Not in PR => run all libraries")
            result |= set(LIBRARIES)

        else:
            match = re.search(rf"^\[({libraries})(?:@([^\]]+))?\]", inputs.pr_title)
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

            for file in inputs.modified_files:
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
                        raise Exception(
                            f"""File {file} is modified, and it may impact {', '.join(impacted_libraries)}.
                            Please remove the PR title prefix [{user_choice}]"""
                        )

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

        return outputs

    return main_library_processing(impacts, inputs)


def scenario_processing(impacts: dict[str, Param], inputs) -> None:
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

    def main_scenario_processing(impacts: dict[str, Param], inputs) -> None:
        result = Result()

        if inputs.is_gitlab:
            print("CI_PIPELINE_SOURCE=" + inputs.event_name)
            print("CI_COMMIT_REF_NAME=" + inputs.ref)

        if inputs.event_name == "schedule" or inputs.ref == "refs/heads/main":
            result.add_scenario_group(scenario_groups.all)

        elif inputs.event_name in ("pull_request", "push"):
            modified_nodeids = set()

            for nodeid in set(list(inputs.new_manifests.keys()) + list(inputs.old_manifests.keys())):
                if (
                    nodeid not in inputs.old_manifests
                    or nodeid not in inputs.new_manifests
                    or inputs.new_manifests[nodeid] != inputs.old_manifests[nodeid]
                ):
                    modified_nodeids.add(nodeid)

            scenarios_by_files: dict[str, set[str]] = defaultdict(set)
            scenario_names: Iterable[str]
            for nodeid, scenario_names in inputs.scenario_map.items():
                file = nodeid.split(":", 1)[0]
                for scenario_name in scenario_names:
                    scenarios_by_files[file].add(scenario_name)

                for modified_nodeid in modified_nodeids:
                    if nodeid.startswith(modified_nodeid):
                        result.add_scenario_names(scenario_names)
                        break

            for file in inputs.modified_files:
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
                        result.add_scenario_group(scenario_groups.all)

                # now get known scenarios executed in this file
                if file in scenarios_by_files:
                    result.add_scenario_names(scenarios_by_files[file])

        outputs = {
                "scenarios": ",".join(sorted(list(result.scenarios))),
                "scenarios_groups": ",".join(sorted(list(result.scenarios_groups)))
                }
        return outputs

    return main_scenario_processing(impacts, inputs)

class Inputs:
    def __init__(self, mock = False):
        self.output = None
        self.event_name = None
        self.ref = None
        self.is_gitlab = False
        self.pr_title = None
        self.raw_impacts = None
        self.modified_files = None
        self.scenario_map = None
        self.new_manifests = None
        self.old_manifests = None
        if not mock:
            self.populate()

    def populate(self):
        self.get_output()
        self.get_git_info()
        self.get_raw_impacts()
        self.get_modified_files()
        self.get_scenario_mappings()
        self.get_manifests()

    def get_output(self):
        # Get output file (different for Gitlab and Github)
        parser = argparse.ArgumentParser(description="AWS SSI Registration Tool")
        parser.add_argument(
            "--output",
            "-o",
            type=str,
            default="",
            help="Output file. If not provided, output to stdout",
        )
        args = parser.parse_args()

        self.output = args.output

    def get_git_info(self):
        # Get all relevant environment variables.
        if "GITLAB_CI" in os.environ:
            self.event_name = os.environ.get("CI_PIPELINE_SOURCE", "push")
            self.ref = os.environ.get("CI_COMMIT_REF_NAME", "")
            self.is_gitlab = True
            # print("CI_PIPELINE_SOURCE=" + event_name)
            # print("CI_COMMIT_REF_NAME=" + ref)
        else:
            self.event_name = os.environ.get("GITHUB_EVENT_NAME", "pull_request")
            self.ref = os.environ.get("GITHUB_REF", "fake-branch-name")
            self.pr_title = os.environ.get("GITHUB_PR_TITLE", "").lower()

    def get_raw_impacts(self):
        # Gets the raw pattern matching data that maps file to impacted 
        # libraries/scenario groups
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # noqa: PTH120, PTH100
        yml_path = os.path.join(root_dir, "test-selection.yml")
        with open(yml_path, "r") as file:
            self.raw_impacts = yaml.safe_load(file)["patterns"]

    def get_modified_files(self):
        # Gets the modified files. Computed with gh in a previous ci step.
        with open("modified_files.txt", "r", encoding="utf-8") as f:
            self.modified_files: list[str] = [line.strip() for line in f]

    def get_scenario_mappings(self):
        if self.event_name in ("pull_request", "push"):
            # Get the mappings used to compute impacted scenarios by file, especially
            # test files
            # This file is generated with
            # ./run.sh MOCK_THE_TEST --collect-only --scenario-report
            with open("logs_mock_the_test/scenarios.json", encoding="utf-8") as f:
                self.scenario_map: dict[str, list[str]] = json.load(f)

    def get_manifests(self):
            # Collects old and new manifests, used to make a diff
            self.new_manifests = load_manifests("manifests/")
            self.old_manifests = load_manifests("original/manifests/")

def stringify_outputs(outputs: dict[str, Any]) -> None:
    ret = []
    for name, value in outputs.items():
        ret.append(f"{name}={json.dumps(value)}")
    return ret

def print_outputs(strings_out, inputs):
    def print_ci_outputs(strings_out, f):
        for s in strings_out:
            print(s, file=f)
    if inputs.output:
        with open(inputs.output, "w", encoding="utf-8") as f:
            print_ci_outputs(strings_out, f)
    else:
        print_ci_outputs(strings_out, sys.stdout)

def process(inputs):
    outputs = {}

    impacts = parse(inputs)
    if not inputs.is_gitlab:
        outputs |= library_processing(impacts, inputs)
    outputs |= scenario_processing(impacts, inputs)

    strings_out = stringify_outputs(outputs)

    return strings_out



def main() -> None:
    inputs = Inputs()
    strings_out = process(inputs)
    print_outputs(strings_out, inputs)








class Tests(unittest.TestCase):
    maxDiff = None
    all_lib_matrix = 'library_matrix=[{"library": "cpp", "version": "prod"}, {"library": "cpp_httpd", "version": "prod"}, {"library": "cpp_nginx", "version": "prod"}, {"library": "dotnet", "version": "prod"}, {"library": "golang", "version": "prod"}, {"library": "java", "version": "prod"}, {"library": "nodejs", "version": "prod"}, {"library": "php", "version": "prod"}, {"library": "python", "version": "prod"}, {"library": "python_lambda", "version": "prod"}, {"library": "ruby", "version": "prod"}, {"library": "rust", "version": "prod"}, {"library": "cpp", "version": "dev"}, {"library": "cpp_httpd", "version": "dev"}, {"library": "cpp_nginx", "version": "dev"}, {"library": "dotnet", "version": "dev"}, {"library": "golang", "version": "dev"}, {"library": "java", "version": "dev"}, {"library": "nodejs", "version": "dev"}, {"library": "php", "version": "dev"}, {"library": "python", "version": "dev"}, {"library": "python_lambda", "version": "dev"}, {"library": "ruby", "version": "dev"}, {"library": "rust", "version": "dev"}]'
    all_lib_with_dev = 'libraries_with_dev=["cpp", "cpp_httpd", "cpp_nginx", "dotnet", "golang", "java", "nodejs", "php", "python", "python_lambda", "ruby", "rust"]'

    def test_regex(self):
        inputs = Inputs(mock=True)
        inputs.event_name = "pull_request"
        inputs.ref = "some_branch"
        inputs.is_gitlab = False
        inputs.pr_title = "Some title"
        inputs.get_raw_impacts()
        inputs.modified_files = [".github/workflows/run-docker-ssi.yml"]
        inputs.get_scenario_mappings()
        inputs.new_manifests = {}
        inputs.old_manifests = {}

        strings_out = process(inputs)

        # print_outputs(strings_out, inputs)
        self.assertEqual(strings_out, [
                self.all_lib_matrix,
                self.all_lib_with_dev,
                'desired_execution_time=3600',
                'rebuild_lambda_proxy=false',
                'scenarios="DEFAULT"',
                'scenarios_groups="docker_ssi"',
                ])

    def test_docker_file(self):
        inputs = Inputs(mock=True)
        inputs.event_name = "pull_request"
        inputs.ref = "some_branch"
        inputs.is_gitlab = False
        inputs.pr_title = "Some title"
        inputs.get_raw_impacts()
        inputs.modified_files = ["utils/build/docker/python/test.Dockerfile"]
        inputs.get_scenario_mappings()
        inputs.new_manifests = {}
        inputs.old_manifests = {}

        strings_out = process(inputs)

        # print_outputs(strings_out, inputs)
        self.assertEqual(strings_out, [
                'library_matrix=[{"library": "python", "version": "prod"}, {"library": "python", "version": "dev"}]',
                'libraries_with_dev=["python"]',
                'desired_execution_time=600',
                'rebuild_lambda_proxy=false',
                'scenarios="DEFAULT"',
                'scenarios_groups="end_to_end,open_telemetry"',
                ])

    def test_main(self):
        inputs = Inputs(mock=True)
        inputs.event_name = "pull_request"
        inputs.ref = "refs/heads/main"
        inputs.is_gitlab = False
        inputs.pr_title = "Some title"
        inputs.get_raw_impacts()
        inputs.modified_files = ["utils/build/docker/python/test.Dockerfile"]
        inputs.get_scenario_mappings()
        inputs.new_manifests = {}
        inputs.old_manifests = {}

        strings_out = process(inputs)

        # print_outputs(strings_out, inputs)
        self.assertEqual(strings_out,  [
                'library_matrix=[{"library": "python", "version": "prod"}, {"library": "python", "version": "dev"}]',
                'libraries_with_dev=["python"]',
                'desired_execution_time=600',
                'rebuild_lambda_proxy=false',
                'scenarios="DEFAULT"',
                'scenarios_groups="all"',
                ])

    # To setup copy the manifests directory and edit the python manifest, depending
    # on your edit you may have to change the scenarios line in the output.
    def test_manifest(self):
        inputs = Inputs(mock=True)
        inputs.event_name = "pull_request"
        inputs.ref = "some_branch"
        inputs.is_gitlab = False
        inputs.pr_title = "Some title"
        inputs.get_raw_impacts()
        inputs.modified_files = ["manifests/python.yml"]
        inputs.get_scenario_mappings()
        inputs.new_manifests = load_manifests("manifests_test/")
        inputs.old_manifests = load_manifests("manifests/")

        strings_out = process(inputs)

        # print_outputs(strings_out, inputs)
        self.assertEqual(strings_out,  [
                'library_matrix=[{"library": "python", "version": "prod"}, {"library": "python", "version": "dev"}]',
                'libraries_with_dev=["python"]',
                'desired_execution_time=600',
                'rebuild_lambda_proxy=false',
                'scenarios="DEFAULT"',
                'scenarios_groups=""',
                ])

    # To setup copy the manifests directory and edit the agent manifest, depending
    # on your edit you may have to change the scenarios line in the output.
    def test_manifest_agent(self):
        inputs = Inputs(mock=True)
        inputs.event_name = "pull_request"
        inputs.ref = "some_branch"
        inputs.is_gitlab = False
        inputs.pr_title = "Some title"
        inputs.get_raw_impacts()
        inputs.modified_files = ["manifests/agent.yml"]
        inputs.get_scenario_mappings()
        inputs.new_manifests = load_manifests("manifests_test1/")
        inputs.old_manifests = load_manifests("manifests/")

        strings_out = process(inputs)

        # print_outputs(strings_out, inputs)
        self.assertEqual(strings_out,  [
                self.all_lib_matrix,
                self.all_lib_with_dev,
                'desired_execution_time=3600',
                'rebuild_lambda_proxy=false',
                'scenarios="DEFAULT,OTEL_LOG_E2E"',
                'scenarios_groups=""',
                ])

    def test_test_file(self):
        inputs = Inputs(mock=True)
        inputs.event_name = "pull_request"
        inputs.ref = "some_branch"
        inputs.is_gitlab = False
        inputs.pr_title = "Some title"
        inputs.get_raw_impacts()
        inputs.modified_files = ["tests/auto_inject/test_auto_inject_guardrail.py"]
        inputs.get_scenario_mappings()
        inputs.new_manifests = {}
        inputs.old_manifests = {}

        strings_out = process(inputs)

        # print_outputs(strings_out, inputs)
        self.assertEqual(strings_out,  [
                self.all_lib_matrix,
                self.all_lib_with_dev,
                'desired_execution_time=3600',
                'rebuild_lambda_proxy=false',
                'scenarios="DEFAULT,INSTALLER_NOT_SUPPORTED_AUTO_INJECTION"',
                'scenarios_groups=""',
                ])
        
    def test_wrong_library_tag(self):
        inputs = Inputs(mock=True)
        inputs.event_name = "pull_request"
        inputs.ref = "some_branch"
        inputs.is_gitlab = False
        inputs.pr_title = "[java] Some title"
        inputs.get_raw_impacts()
        inputs.modified_files = ["utils/build/docker/python/test.Dockerfile"]
        inputs.get_scenario_mappings()
        inputs.new_manifests = {}
        inputs.old_manifests = {}

        self.assertRaises(Exception, process, inputs)

    def test_wrong_library_tag_with_branch(self):
        inputs = Inputs(mock=True)
        inputs.event_name = "pull_request"
        inputs.ref = "some_branch"
        inputs.is_gitlab = False
        inputs.pr_title = "[java@main] Some title"
        inputs.get_raw_impacts()
        inputs.modified_files = ["utils/build/docker/python/test.Dockerfile"]
        inputs.get_scenario_mappings()
        inputs.new_manifests = {}
        inputs.old_manifests = {}

        strings_out = process(inputs)

        # print_outputs(strings_out, inputs)
        self.assertEqual(strings_out,  [
                'library_matrix=[{"library": "java", "version": "prod"}, {"library": "java", "version": "dev"}]',
                'libraries_with_dev=["java"]',
                'desired_execution_time=600',
                'rebuild_lambda_proxy=false',
                'scenarios="DEFAULT"',
                'scenarios_groups="end_to_end,open_telemetry"',
                ])

    def test_wrong_library_tag_with_test_file(self):
        inputs = Inputs(mock=True)
        inputs.event_name = "pull_request"
        inputs.ref = "some_branch"
        inputs.is_gitlab = False
        inputs.pr_title = "[java] Some title"
        inputs.get_raw_impacts()
        inputs.modified_files = ["tests/auto_inject/test_auto_inject_guardrail.py"]
        inputs.get_scenario_mappings()
        inputs.new_manifests = {}
        inputs.old_manifests = {}

        strings_out = process(inputs)

        # print_outputs(strings_out, inputs)
        self.assertEqual(strings_out,  [
                'library_matrix=[{"library": "java", "version": "prod"}, {"library": "java", "version": "dev"}]',
                'libraries_with_dev=["java"]',
                'desired_execution_time=600',
                'rebuild_lambda_proxy=false',
                'scenarios="DEFAULT,INSTALLER_NOT_SUPPORTED_AUTO_INJECTION"',
                'scenarios_groups=""',
                ])

    def test_lambda_proxy(self):
        inputs = Inputs(mock=True)
        inputs.event_name = "pull_request"
        inputs.ref = "some_branch"
        inputs.is_gitlab = False
        inputs.pr_title = "Some title"
        inputs.get_raw_impacts()
        inputs.modified_files = ["utils/build/docker/lambda_proxy/pyproject.toml"]
        inputs.get_scenario_mappings()
        inputs.new_manifests = {}
        inputs.old_manifests = {}

        strings_out = process(inputs)

        # print_outputs(strings_out, inputs)
        self.assertEqual(strings_out,  [
                'library_matrix=[{"library": "python_lambda", "version": "prod"}, {"library": "python_lambda", "version": "dev"}]',
                'libraries_with_dev=["python_lambda"]',
                'desired_execution_time=600',
                'rebuild_lambda_proxy=true',
                'scenarios="DEFAULT"',
                'scenarios_groups="lambda_end_to_end"',
                ])

    def test_doc(self):
        inputs = Inputs(mock=True)
        inputs.event_name = "pull_request"
        inputs.ref = "some_branch"
        inputs.is_gitlab = False
        inputs.pr_title = "Some title"
        inputs.get_raw_impacts()
        inputs.modified_files = ["README.md"]
        inputs.get_scenario_mappings()
        inputs.new_manifests = {}
        inputs.old_manifests = {}

        strings_out = process(inputs)

        # print_outputs(strings_out, inputs)
        self.assertEqual(strings_out,  [
                'library_matrix=[]',
                'libraries_with_dev=[]',
                'desired_execution_time=3600',
                'rebuild_lambda_proxy=false',
                'scenarios="DEFAULT"',
                'scenarios_groups=""',
                ])

    def test_gitlab(self):
        inputs = Inputs(mock=True)
        inputs.event_name = "pull_request"
        inputs.ref = "some_branch"
        inputs.is_gitlab = True
        inputs.pr_title = "Some title"
        inputs.get_raw_impacts()
        inputs.modified_files = ["README.md"]
        inputs.get_scenario_mappings()
        inputs.new_manifests = {}
        inputs.old_manifests = {}

        strings_out = process(inputs)

        # print_outputs(strings_out, inputs)
        self.assertEqual(strings_out,  [
                'scenarios="DEFAULT"',
                'scenarios_groups=""',
                ])


if __name__ == "__main__":
    main()

