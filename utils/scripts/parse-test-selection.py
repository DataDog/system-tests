import unittest
import yaml
from typing import Any, TYPE_CHECKING
from manifests.parser.core import load as load_manifests
from collections import defaultdict, OrderedDict
import sys
import argparse
import re
from fnmatch import fnmatch
import json
import os
import logging
from utils._context._scenarios import scenarios, Scenario, scenario_groups
if TYPE_CHECKING:
    from collections.abc import Iterable

logger = logging.getLogger(__name__)


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
        self.scenario_groups: set[str] = {scenario_groups.all.name}


def parse(inputs) -> dict[str, Param]:
    try:
        ret = OrderedDict()
        for pattern, param in inputs.raw_impacts.items():
            libraries = param.get("libraries", LIBRARIES) or set()
            scenario_group_set = param.get("scenario_groups", scenario_groups.all.name) or set()

            if pattern not in ret:
                ret[pattern] = Param()

            if check_libraries(libraries):
                if isinstance(libraries, str):
                    ret[pattern].libraries = {libraries}
                else:
                    ret[pattern].libraries = set(libraries)
            else:
                raise ValueError(f"One or more of the libraries for {pattern} does not exist: {libraries}")  # noqa: TRY002

            if check_scenario(scenario_group_set):
                if isinstance(scenario_group_set, str):
                    ret[pattern].scenario_groups = {scenario_group_set}
                else:
                    ret[pattern].scenario_groups = set(scenario_group_set)
            else:
                raise ValueError(f"One or more of the scenario groups for {pattern} does not exist: {scenario_group_set}")  # noqa: TRY002

        return ret

    except AttributeError:
        raise ValueError("Error in the test selection file") from None  # noqa: TRY002

class LibraryProcessor:

    def __init__(self, libraries = None):
        self.selected = libraries if libraries else set()
        self.impacted = set()
        self.user_choice = None
        self.branch_selector = None

    def process_pr_title(self, inputs):
        libraries = "|".join(ALL_LIBRARIES)
        match = re.search(rf"^\[({libraries})(?:@([^\]]+))?\]", inputs.pr_title)
        if match:
            logger.info(f"PR title matches => run {match[1]}")
            self.user_choice = match[1]
            self.selected.add(self.user_choice)

            # if users specified a branch, another job will prevent the merge
            # so let user do what he/she wants :
            self.branch_selector = match[2]


    def compute_impacted(self, modified_file: str, impacts: dict[str, Param]) -> list[str]:
        libraries = "|".join(ALL_LIBRARIES)
        patterns = [
            rf"^manifests/({libraries})\.",
            rf"^utils/build/docker/({libraries})/",
            rf"^lib-injection/build/docker/({libraries})/",
            rf"^utils/build/build_({libraries})_base_images.sh",
        ]

        for pattern in patterns:
            if match := re.search(pattern, modified_file):
                self.impacted.add(match[1])
                return 

        for pattern, requirement in impacts.items():
            if fnmatch(modified_file, pattern):
                self.impacted |= requirement.libraries
                return 

        self.impacted |= LIBRARIES

    def is_manual(self, file):
        if self.user_choice:
            if self.branch_selector or len(self.impacted) == 0:
                return True
            else:
                # user specified a library in the PR title
                # and there are some impacted libraries
                if file.startswith("tests/"):
                    # modification in tests files are complex, trust user
                    return True
                elif self.impacted != {self.user_choice}:
                    # only acceptable use case : impacted library exactly matches user choice
                    raise ValueError(
                        f"""File {file} is modified, and it may impact {', '.join(self.impacted)}.
                        Please remove the PR title prefix [{self.user_choice}]"""
                    )
        else:
            return False

    def add(self, file, impacts):
        self.compute_impacted(file, impacts)
        if not self.is_manual(file):
            self.selected |= self.impacted


    def get_outputs(self):
        populated_result = [
            {
                "library": library,
                "version": "prod",
            }
            for library in sorted(self.selected)
        ] + [
            {
                "library": library,
                "version": "dev",
            }
            for library in sorted(self.selected)
            if "otel" not in library
        ]

        libraries_with_dev = [item["library"] for item in populated_result if item["version"] == "dev"]
        return {
            "library_matrix": populated_result,
            "libraries_with_dev": libraries_with_dev,
            "desired_execution_time": 600 if len(self.selected) == 1 else 3600,
        }

class ScenarioProcessor:

    def __init__(self, scenario_groups = None):
        self.scenario_groups = scenario_groups if scenario_groups else set()
        self.scenarios = {scenarios.default.name}
        self.scenarios_by_files = defaultdict(set)

    def process_manifests(self, inputs):
        modified_nodeids = set()

        for nodeid in set(list(inputs.new_manifests.keys()) + list(inputs.old_manifests.keys())):
            if (
                nodeid not in inputs.old_manifests
                or nodeid not in inputs.new_manifests
                or inputs.new_manifests[nodeid] != inputs.old_manifests[nodeid]
            ):
                modified_nodeids.add(nodeid)

        scenario_names: Iterable[str]
        for nodeid, scenario_names in inputs.scenario_map.items():
            for modified_nodeid in modified_nodeids:
                if nodeid.startswith(modified_nodeid):
                    self.scenarios |= set(scenario_names)
                    break

    def compute_scenarios_by_files(self, inputs):
        scenario_names: Iterable[str]
        for nodeid, scenario_names in inputs.scenario_map.items():
            file = nodeid.split(":", 1)[0]
            for scenario_name in scenario_names:
                self.scenarios_by_files[file].add(scenario_name)

    def process_test_files(self, file):
        if file.startswith("tests/"):
            if file.endswith(("/utils.py", "/conftest.py", ".json")):
                # particular use case for modification in tests/ of a file utils.py or conftest.py
                # in that situation, takes all scenarios executed in tests/<path>/

                # same for any json file

                folder = "/".join(file.split("/")[:-1]) + "/"  # python trickery to remove last element

                for sub_file, scenario_names in self.scenarios_by_files.items():
                    if sub_file.startswith(folder):
                        self.scenarios |= scenario_names

    def process_regular_file(self, file, impacts):
        for pattern, requirement in impacts.items():
            if fnmatch(file, pattern):
                self.scenario_groups |= requirement.scenario_groups
                # on first matching pattern, stop the loop
                break
        else:
            self.scenario_groups.add(scenario_groups.all.name)

        # now get known scenarios executed in this file
        if file in self.scenarios_by_files:
            self.scenarios |= self.scenarios_by_files[file]

    def add(self, file, impacts):
        self.process_test_files(file)
        self.process_regular_file(file, impacts)

    def get_outputs(self):
        return {
                    "scenarios": ",".join(sorted(list(self.scenarios))),
                    "scenarios_groups": ",".join(sorted(list(self.scenario_groups)))
                    }


class Inputs:
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # noqa: PTH120, PTH100

    def __init__(self, mock = False):
        self.output = None
        self.event_name = "pull_request"
        self.ref = ""
        self.is_gitlab = False
        self.pr_title = ""
        self.mapping_file = os.path.join(self.root_dir, "test-selection.yml")
        self.raw_impacts = None
        self.modified_files = []
        self.scenario_map = None
        self.new_manifests = {}
        self.old_manifests = {}
        if not mock:
            self.populate()
        if not self.raw_impacts:
            self.load_raw_impacts()
        if not self.scenario_map:
            self.load_scenario_mappings()


    def populate(self):
        self.load_output()
        self.load_git_info()
        self.load_raw_impacts()
        self.load_modified_files()
        self.load_scenario_mappings()
        self.load_manifests()

    def load_output(self):
        # Get output file (different for Gitlab and Github)
        parser = argparse.ArgumentParser(description="print output")
        parser.add_argument(
            "--output",
            "-o",
            type=str,
            default="",
            help="Output file. If not provided, output to stdout",
        )
        args = parser.parse_args()

        self.output = args.output

    def load_git_info(self):
        # Get all relevant environment variables.
        if "GITLAB_CI" in os.environ:
            self.event_name = os.environ.get("CI_PIPELINE_SOURCE", "push")
            self.ref = os.environ.get("CI_COMMIT_REF_NAME", "")
            self.is_gitlab = True
        else:
            self.event_name = os.environ.get("GITHUB_EVENT_NAME", "pull_request")
            self.ref = os.environ.get("GITHUB_REF", "fake-branch-name")
            self.pr_title = os.environ.get("GITHUB_PR_TITLE", "").lower()

    def load_raw_impacts(self):
        # Gets the raw pattern matching data that maps file to impacted 
        # libraries/scenario groups
        with open(self.mapping_file, "r") as file:
            self.raw_impacts = yaml.safe_load(file)["patterns"]

    def load_modified_files(self):
        # Gets the modified files. Computed with gh in a previous ci step.
        with open("modified_files.txt", "r", encoding="utf-8") as f:
            self.modified_files: list[str] = [line.strip() for line in f]

    def load_scenario_mappings(self):
        if self.event_name in ("pull_request", "push"):
            # Get the mappings used to compute impacted scenarios by file, especially
            # test files
            # This file is generated with
            # ./run.sh MOCK_THE_TEST --collect-only --scenario-report
            with open("logs_mock_the_test/scenarios.json", encoding="utf-8") as f:
                self.scenario_map: dict[str, list[str]] = json.load(f)

    def load_manifests(self):
            # Collects old and new manifests, used to make a diff
            self.new_manifests = load_manifests("manifests/")
            self.old_manifests = load_manifests("original/manifests/")

def extra_gitlab_output(inputs):
    return {
            "CI_PIPELINE_SOURCE": inputs.event_name,
            "CI_COMMIT_REF_NAME": inputs.ref
            }

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

def process(inputs) -> None:
    outputs = {}
    impacts = parse(inputs)
    if inputs.is_gitlab:
        outputs |= extra_gitlab_output(inputs)

    rebuild_lambda_proxy = False

    if inputs.event_name not in ("pull_request", "push") or inputs.ref == "refs/heads/main":
        sp = ScenarioProcessor({scenario_groups.all.name})
        lp = LibraryProcessor(LIBRARIES)

    else:
        sp = ScenarioProcessor()
        lp = LibraryProcessor()

        sp.process_manifests(inputs)
        sp.compute_scenarios_by_files(inputs)

        lp.process_pr_title(inputs)

        for file in inputs.modified_files:

            sp.add(file, impacts)
            lp.add(file, impacts)

            if file in (
                "utils/build/docker/lambda_proxy/pyproject.toml",
                "utils/build/docker/lambda-proxy.Dockerfile",
            ):
                rebuild_lambda_proxy = True


    if inputs.is_gitlab:
        outputs |= sp.get_outputs() 
    else:
        outputs |= lp.get_outputs()| {"rebuild_lambda_proxy": rebuild_lambda_proxy} | sp.get_outputs() 

    strings_out = stringify_outputs(outputs)

    return strings_out


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    inputs = Inputs()
    strings_out = process(inputs)
    print_outputs(strings_out, inputs)








class Tests(unittest.TestCase):
    maxDiff = None
    all_lib_matrix = 'library_matrix=[{"library": "cpp", "version": "prod"}, {"library": "cpp_httpd", "version": "prod"}, {"library": "cpp_nginx", "version": "prod"}, {"library": "dotnet", "version": "prod"}, {"library": "golang", "version": "prod"}, {"library": "java", "version": "prod"}, {"library": "nodejs", "version": "prod"}, {"library": "php", "version": "prod"}, {"library": "python", "version": "prod"}, {"library": "python_lambda", "version": "prod"}, {"library": "ruby", "version": "prod"}, {"library": "rust", "version": "prod"}, {"library": "cpp", "version": "dev"}, {"library": "cpp_httpd", "version": "dev"}, {"library": "cpp_nginx", "version": "dev"}, {"library": "dotnet", "version": "dev"}, {"library": "golang", "version": "dev"}, {"library": "java", "version": "dev"}, {"library": "nodejs", "version": "dev"}, {"library": "php", "version": "dev"}, {"library": "python", "version": "dev"}, {"library": "python_lambda", "version": "dev"}, {"library": "ruby", "version": "dev"}, {"library": "rust", "version": "dev"}]'
    all_lib_with_dev = 'libraries_with_dev=["cpp", "cpp_httpd", "cpp_nginx", "dotnet", "golang", "java", "nodejs", "php", "python", "python_lambda", "ruby", "rust"]'

    def test_complete_file_path(self):
        inputs = Inputs(mock=True)
        inputs.modified_files = [".github/workflows/run-docker-ssi.yml"]

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
        inputs.modified_files = ["utils/build/docker/python/test.Dockerfile"]

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

    def test_ref_main(self):
        inputs = Inputs(mock=True)
        inputs.ref = "refs/heads/main"
        inputs.modified_files = ["utils/build/docker/python/test.Dockerfile"]

        strings_out = process(inputs)

        # print_outputs(strings_out, inputs)
        self.assertEqual(strings_out,  [
                self.all_lib_matrix,
                self.all_lib_with_dev,
                'desired_execution_time=3600',
                'rebuild_lambda_proxy=false',
                'scenarios="DEFAULT"',
                'scenarios_groups="all"',
                ])

    # To setup copy the manifests directory and edit the python manifest, depending
    # on your edit you may have to change the scenarios line in the output.
    def test_manifest(self):
        inputs = Inputs(mock=True)
        inputs.modified_files = ["manifests/python.yml"]
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
        inputs.modified_files = ["manifests/agent.yml"]
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
        inputs.modified_files = ["tests/auto_inject/test_auto_inject_guardrail.py"]

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

    def test_test_file_utils(self):
        inputs = Inputs(mock=True)
        inputs.modified_files = ["tests/auto_inject/utils.py"]

        strings_out = process(inputs)

        # print_outputs(strings_out, inputs)
        self.assertEqual(strings_out,  [
                self.all_lib_matrix,
                self.all_lib_with_dev,
                'desired_execution_time=3600',
                'rebuild_lambda_proxy=false',
                'scenarios="CHAOS_INSTALLER_AUTO_INJECTION,CONTAINER_AUTO_INJECTION_INSTALL_SCRIPT,CONTAINER_AUTO_INJECTION_INSTALL_SCRIPT_APPSEC,CONTAINER_AUTO_INJECTION_INSTALL_SCRIPT_PROFILING,DEFAULT,DEMO_AWS,HOST_AUTO_INJECTION_INSTALL_SCRIPT,HOST_AUTO_INJECTION_INSTALL_SCRIPT_APPSEC,HOST_AUTO_INJECTION_INSTALL_SCRIPT_PROFILING,INSTALLER_AUTO_INJECTION,INSTALLER_NOT_SUPPORTED_AUTO_INJECTION,LOCAL_AUTO_INJECTION_INSTALL_SCRIPT,MULTI_INSTALLER_AUTO_INJECTION,SIMPLE_AUTO_INJECTION_APPSEC,SIMPLE_AUTO_INJECTION_PROFILING,SIMPLE_INSTALLER_AUTO_INJECTION"',
                'scenarios_groups=""',
                ])
        
    def test_wrong_library_tag(self):
        inputs = Inputs(mock=True)
        inputs.pr_title = "[java] Some title"
        inputs.modified_files = ["utils/build/docker/python/test.Dockerfile"]

        self.assertRaises(Exception, process, inputs)

    def test_wrong_library_tag_with_branch(self):
        inputs = Inputs(mock=True)
        inputs.pr_title = "[java@main] Some title"
        inputs.modified_files = ["utils/build/docker/python/test.Dockerfile"]

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
        inputs.pr_title = "[java] Some title"
        inputs.modified_files = ["tests/auto_inject/test_auto_inject_guardrail.py"]

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
        inputs.modified_files = ["utils/build/docker/lambda_proxy/pyproject.toml"]

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
        inputs.modified_files = ["binaries/dd-trace-go/_tools/README.md"]

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
        inputs.is_gitlab = True
        inputs.ref="some_branch"
        inputs.modified_files = ["README.md"]

        strings_out = process(inputs)

        # print_outputs(strings_out, inputs)
        self.assertEqual(strings_out,  [
            'CI_PIPELINE_SOURCE="pull_request"',
            'CI_COMMIT_REF_NAME="some_branch"',
            'scenarios="DEFAULT"',
            'scenarios_groups=""',
            ])


if __name__ == "__main__":
    main()

