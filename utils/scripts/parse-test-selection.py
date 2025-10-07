from __future__ import annotations

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
from utils._context._scenarios import scenarios, scenario_groups

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


def parse(inputs: Inputs) -> dict[str, Param]:
    try:
        ret = OrderedDict()
        if inputs.raw_impacts is None:
            raise ValueError("raw_impacts is None")
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
                raise ValueError(f"One or more of the libraries for {pattern} does not exist: {libraries}")

            if check_scenario(scenario_group_set):
                if isinstance(scenario_group_set, str):
                    ret[pattern].scenario_groups = {scenario_group_set}
                else:
                    ret[pattern].scenario_groups = set(scenario_group_set)
            else:
                raise ValueError(
                    f"One or more of the scenario groups for {pattern} does not exist: {scenario_group_set}"
                )

        return ret

    except AttributeError:
        raise ValueError("Error in the test selection file") from None


class LibraryProcessor:
    def __init__(self, libraries: set[str] | None = None):
        self.selected = libraries if libraries else set()
        self.impacted: set[str] = set()
        self.user_choice: str | None = None
        self.branch_selector: str | None = None

    def process_pr_title(self, inputs: Inputs) -> None:
        libraries = "|".join(ALL_LIBRARIES)
        match = re.search(rf"^\[({libraries})(?:@([^\]]+))?\]", inputs.pr_title)
        if match:
            logger.info(f"PR title matches library => run {match[1]}")
            self.user_choice = match[1]
            self.selected.add(self.user_choice)

            # if users specified a branch, another job will prevent the merge
            # so let user do what he/she wants :
            self.branch_selector = match[2]
            if self.branch_selector:
                logger.info(f"PR title matches branch {self.branch_selector} => user library selection will be enforced without checks")

    def compute_impacted(self, modified_file: str, impacts: dict[str, Param]) -> None:
        self.impacted = set()
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

        logger.warning(f"Unknown file {modified_file} was detected, activating all libraries.")
        self.impacted |= LIBRARIES

    def is_manual(self, file: str) -> bool:
        if self.user_choice:
            if self.branch_selector or len(self.impacted) == 0:
                return True
            # user specified a library in the PR title
            # and there are some impacted libraries
            if file.startswith("tests/") or self.impacted == {self.user_choice}:
                # modification in tests files are complex, trust user
                return True
            # only acceptable use case : impacted library exactly matches user choice
            raise ValueError(
                f"""File {file} is modified, and it may impact {', '.join(self.impacted)}.
                        Please remove the PR title prefix [{self.user_choice}]"""
            )
        return False

    def add(self, file: str, impacts: dict[str, Param]) -> None:
        self.compute_impacted(file, impacts)
        if not self.is_manual(file):
            self.selected |= self.impacted

    def get_outputs(self) -> dict[str, Any]:
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
    def __init__(self, scenario_groups: set[str] | None = None):
        self.scenario_groups = scenario_groups if scenario_groups else set()
        self.scenarios = {scenarios.default.name}
        self.scenarios_by_files: dict[str, set[str]] = defaultdict(set)

    def process_manifests(self, inputs: Inputs) -> None:
        modified_nodeids = set()

        for nodeid in set(list(inputs.new_manifests.keys()) + list(inputs.old_manifests.keys())):
            if (
                nodeid not in inputs.old_manifests
                or nodeid not in inputs.new_manifests
                or inputs.new_manifests[nodeid] != inputs.old_manifests[nodeid]
            ):
                modified_nodeids.add(nodeid)

        if inputs.scenario_map is None:
            return
        scenario_names: Iterable[str]
        for nodeid, scenario_names in inputs.scenario_map.items():
            for modified_nodeid in modified_nodeids:
                if nodeid.startswith(modified_nodeid):
                    self.scenarios |= set(scenario_names)
                    break

    def compute_scenarios_by_files(self, inputs: Inputs) -> None:
        if inputs.scenario_map is None:
            return
        scenario_names: Iterable[str]
        for nodeid, scenario_names in inputs.scenario_map.items():
            file = nodeid.split(":", 1)[0]
            for scenario_name in scenario_names:
                self.scenarios_by_files[file].add(scenario_name)

    def process_test_files(self, file: str) -> None:
        if file.startswith("tests/"):
            if file.endswith(("/utils.py", "/conftest.py", ".json")):
                # particular use case for modification in tests/ of a file utils.py or conftest.py
                # in that situation, takes all scenarios executed in tests/<path>/

                # same for any json file

                folder = "/".join(file.split("/")[:-1]) + "/"  # python trickery to remove last element

                for sub_file, scenario_names in self.scenarios_by_files.items():
                    if sub_file.startswith(folder):
                        self.scenarios |= scenario_names

    def process_regular_file(self, file: str, impacts: dict[str, Param]) -> None:
        for pattern, requirement in impacts.items():
            if fnmatch(file, pattern):
                self.scenario_groups |= requirement.scenario_groups
                # on first matching pattern, stop the loop
                break
        else:
            logger.warning(f"Unknown file {file} was detected, activating all scenario groups.")
            self.scenario_groups.add(scenario_groups.all.name)

        # now get known scenarios executed in this file
        if file in self.scenarios_by_files:
            self.scenarios |= self.scenarios_by_files[file]

    def add(self, file: str, impacts: dict[str, Param]) -> None:
        self.process_test_files(file)
        self.process_regular_file(file, impacts)

    def get_outputs(self) -> dict[str, str]:
        return {
            "scenarios": ",".join(sorted(self.scenarios)),
            "scenarios_groups": ",".join(sorted(self.scenario_groups)),
        }


class Inputs:
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # noqa: PTH120, PTH100

    def __init__(self, mock: bool = False) -> None:  # noqa: FBT001, FBT002
        self.output: str | None = None
        self.event_name = "pull_request"
        self.ref = ""
        self.is_gitlab = False
        self.pr_title = ""
        self.mapping_file = os.path.join(self.root_dir, "test-selection.yml")
        self.raw_impacts: dict[str, Any] | None = None
        self.modified_files: list[str] = []
        self.scenario_map: dict[str, list[str]] | None = None
        self.new_manifests: dict[str, Any] = {}
        self.old_manifests: dict[str, Any] = {}
        if not mock:
            self.populate()
        if not self.raw_impacts:
            self.load_raw_impacts()
        if not self.scenario_map:
            self.load_scenario_mappings()

    def populate(self) -> None:
        self.load_output()
        self.load_git_info()
        self.load_raw_impacts()
        self.load_modified_files()
        self.load_scenario_mappings()
        self.load_manifests()

    def load_output(self) -> None:
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

    def load_git_info(self) -> None:
        # Get all relevant environment variables.
        if "GITLAB_CI" in os.environ:
            self.event_name = os.environ.get("CI_PIPELINE_SOURCE", "push")
            self.ref = os.environ.get("CI_COMMIT_REF_NAME", "")
            self.is_gitlab = True
        else:
            self.event_name = os.environ.get("GITHUB_EVENT_NAME", "pull_request")
            self.ref = os.environ.get("GITHUB_REF", "fake-branch-name")
            self.pr_title = os.environ.get("GITHUB_PR_TITLE", "").lower()

    def load_raw_impacts(self) -> None:
        # Gets the raw pattern matching data that maps file to impacted
        # libraries/scenario groups
        with open(self.mapping_file, "r", encoding="utf-8") as file:
            self.raw_impacts = yaml.safe_load(file)["patterns"]

    def load_modified_files(self) -> None:
        # Gets the modified files. Computed with gh in a previous ci step.
        with open("modified_files.txt", "r", encoding="utf-8") as f:
            self.modified_files = [line.strip() for line in f]

    def load_scenario_mappings(self) -> None:
        if self.event_name in ("pull_request", "push"):
            # Get the mappings used to compute impacted scenarios by file, especially
            # test files
            # This file is generated with
            # ./run.sh MOCK_THE_TEST --collect-only --scenario-report
            with open("logs_mock_the_test/scenarios.json", encoding="utf-8") as f:
                self.scenario_map = json.load(f)

    def load_manifests(self) -> None:
        # Collects old and new manifests, used to make a diff
        self.new_manifests = load_manifests("manifests/")
        self.old_manifests = load_manifests("original/manifests/")


def extra_gitlab_output(inputs: Inputs) -> dict[str, str]:
    return {"CI_PIPELINE_SOURCE": inputs.event_name, "CI_COMMIT_REF_NAME": inputs.ref}


def stringify_outputs(outputs: dict[str, Any]) -> list[str]:
    ret = []
    for name, value in outputs.items():
        ret.append(f"{name}={json.dumps(value)}")
    return ret


def print_outputs(strings_out: list[str], inputs: Inputs) -> None:
    def print_ci_outputs(strings_out: list[str], f: Any) -> None:  # noqa: ANN401
        for s in strings_out:
            print(s, file=f)

    if inputs.output:
        with open(inputs.output, "w", encoding="utf-8") as f:
            print_ci_outputs(strings_out, f)
    else:
        print_ci_outputs(strings_out, sys.stdout)


def process(inputs: Inputs) -> list[str]:
    outputs: dict[str, Any] = {}
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
        outputs |= lp.get_outputs() | {"rebuild_lambda_proxy": rebuild_lambda_proxy} | sp.get_outputs()

    return stringify_outputs(outputs)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    inputs = Inputs()
    strings_out = process(inputs)
    print_outputs(strings_out, inputs)


if __name__ == "__main__":
    main()
