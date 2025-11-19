from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from collections import OrderedDict, defaultdict
from fnmatch import fnmatch
from typing import TYPE_CHECKING, Any

import yaml

from utils._context._scenarios import scenario_groups as all_scenario_groups, scenarios, get_all_scenarios
from utils._logger import logger
from utils.manifest import Manifest

if TYPE_CHECKING:
    from collections.abc import Iterable

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # noqa: PTH120, PTH100
scenario_names = {scenario.name for scenario in get_all_scenarios()}

# do not include otel in system-tests CI by default, as the staging backend is not stable enough
LIBRARIES = {
    "cpp",
    "cpp_httpd",
    "cpp_nginx",
    "dotnet",
    "golang",
    "java",
    "nodejs",
    "otel_collector",
    "php",
    "python",
    "ruby",
    "python_lambda",
    "rust",
}

LAMBDA_LIBRARIES = {"python_lambda"}
OTEL_LIBRARIES = {"java_otel", "python_otel"}  # , "nodejs_otel"]

ALL_LIBRARIES = LIBRARIES | LAMBDA_LIBRARIES | OTEL_LIBRARIES


def check_scenarios(scenarios: set[str]) -> bool:
    return all(name in scenario_names for name in scenarios)


def check_scenario_groups(val: set[str]) -> bool:
    return all(hasattr(all_scenario_groups, scenario) for scenario in val)


def check_libraries(val: set[str]) -> bool:
    return all(library in ALL_LIBRARIES for library in val)


def _setify(value: list[str] | set[str] | str | None) -> set[str]:
    if isinstance(value, set):
        return value

    if isinstance(value, list):
        return {*value}

    if isinstance(value, str):
        return {value}

    assert value is None

    return set()


class Param:
    def __init__(
        self,
        pattern: str,
        parameters: dict,
    ):
        self.libraries = _setify(parameters.get("libraries", LIBRARIES))

        if "scenario_groups" not in parameters and "scenario" not in parameters:  # no instruction -> run all
            self.scenario_groups = {all_scenario_groups.all.name}
            self.scenarios = set()
        else:
            self.scenario_groups = _setify(parameters.get("scenario_groups"))
            self.scenarios = _setify(parameters.get("scenario"))

        if not check_libraries(self.libraries):
            raise ValueError(f"One or more of the libraries for {pattern} does not exist: {self.libraries}")
        if not check_scenario_groups(self.scenario_groups):
            raise ValueError(f"One or more of the scenario groups for {pattern} does not exist: {self.scenario_groups}")
        if not check_scenarios(self.scenarios):
            raise ValueError(f"Scenario {self.scenarios} for {pattern} does not exist")


def match_patterns(modified_file: str, impacts: dict[str, Param]) -> Param | None:
    for pattern, requirement in impacts.items():
        if fnmatch(modified_file, pattern):
            logger.debug(f"Matched file {modified_file} with pattern {pattern}")
            return requirement
    logger.debug(f"No match found for file {modified_file}")
    return None


def get_prefix(path: str, pattern: str) -> str:
    """Returns the prefix of `path` before the given `pattern` (including the trailing slash).

    Example:
        get_prefix("aa/bb/pattern/dd/ee", "pattern")  # -> "aa/bb/"

    """
    parts = path.split("/")
    if pattern in parts:
        idx = parts.index(pattern)
        return "/".join(parts[: idx + 0]) + "/" if idx > 0 else ""

    return path


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
                logger.info(
                    f"PR title matches branch {self.branch_selector} "
                    "=> user library selection will be enforced without checks"
                )

    def compute_impacted(self, modified_file: str, param: Param | None) -> None:
        self.impacted = set()

        if param is not None:
            self.impacted |= param.libraries
            return

        logger.warning(f"Unknown file {modified_file} was detected, activating all libraries.")
        self.impacted |= LIBRARIES

    def is_manual(self, file: str) -> bool:
        if not self.user_choice:
            return False

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

    def add(self, file: str, param: Param | None) -> None:
        self.compute_impacted(file, param)
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
            if "otel" not in library and library not in ("otel_collector", "python_lambda")
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
        if "nccatoni/manifest-migration" in inputs.ref:
            self.scenario_groups |= {all_scenario_groups.all.name}
            return
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
            if "/utils/" in file:
                # particular use case for modification in a utils/ folder:
                # in that situation, all files near to this utils/ folder, or inside folders near it
                # are be impacted

                folder = get_prefix(file, "utils")

                for sub_file, scenario_names in self.scenarios_by_files.items():
                    if sub_file.startswith(folder):
                        self.scenarios |= scenario_names

            elif file.endswith(("/utils.py", "/conftest.py", ".json")):
                # particular use case for modification in tests/ of a file utils.py or conftest.py:
                # in that situation, takes all scenarios executed in tests/<path>/

                # same for any json file

                folder = "/".join(file.split("/")[:-1]) + "/"  # python trickery to remove last element

                for sub_file, scenario_names in self.scenarios_by_files.items():
                    if sub_file.startswith(folder):
                        self.scenarios |= scenario_names

    def process_regular_file(self, file: str, param: Param | None) -> None:
        if param is not None:
            self.scenario_groups |= param.scenario_groups
            self.scenarios |= param.scenarios

        else:
            logger.warning(f"Unknown file {file} was detected, activating all scenario groups.")
            self.scenario_groups.add(all_scenario_groups.all.name)

        # now get known scenarios executed in this file
        if file in self.scenarios_by_files:
            self.scenarios |= self.scenarios_by_files[file]

    def add(self, file: str, param: Param | None) -> None:
        self.process_test_files(file)
        self.process_regular_file(file, param)

    def get_outputs(self) -> dict[str, str]:
        return {
            "scenarios": ",".join(sorted(self.scenarios)),
            "scenarios_groups": ",".join(sorted(self.scenario_groups)),
        }


class Inputs:
    impacts: dict[str, Param]

    def __init__(
        self,
        output: str | None = None,
        mapping_file: str = "utils/scripts/libraries_and_scenarios_rules.yml",
        scenario_map_file: str = "logs_mock_the_test/scenarios.json",
        new_manifests: str = "manifests/",
        old_manifests: str = "original/manifests/",
    ) -> None:
        self.is_gitlab = False
        self.load_git_info()
        self.output = output
        self.mapping_file = os.path.join(root_dir, mapping_file)
        self.scenario_map_file = os.path.join(root_dir, scenario_map_file)
        if "nccatoni/manifest-migration" not in self.ref:
            print(self.ref)
            self.new_manifests: dict[str, list[dict[str, Any]]] = Manifest.parse(new_manifests)
            self.old_manifests: dict[str, list[dict[str, Any]]] = Manifest.parse(old_manifests)

            if not self.new_manifests:
                raise FileNotFoundError(f"Manifest files not found: {new_manifests}")
            if not self.old_manifests:
                raise FileNotFoundError(f"Manifest files not found: {old_manifests}")

        self.load_raw_impacts()
        self.load_scenario_mappings()

        self.load_modified_files()

    def load_git_info(self) -> None:
        # Get all relevant environment variables.
        if "GITLAB_CI" in os.environ:
            self.event_name = os.environ.get("CI_PIPELINE_SOURCE", "push")
            self.ref = os.environ.get("CI_COMMIT_REF_NAME", "")
            self.pr_title = ""
            self.is_gitlab = True
        else:
            self.event_name = os.environ.get("GITHUB_EVENT_NAME", "pull_request")
            self.ref = os.environ.get("GITHUB_REF", "")
            self.pr_title = os.environ.get("GITHUB_PR_TITLE", "").lower()

    def load_raw_impacts(self) -> None:
        # Gets the raw pattern matching data that maps file to impacted
        # libraries/scenario groups

        default_param = Param(".*", {"libraries": LIBRARIES, "scenario_groups": all_scenario_groups.all.name})
        self.impacts: dict[str, Param] = OrderedDict()

        with open(self.mapping_file, "r", encoding="utf-8") as file:
            raw_impacts = yaml.safe_load(file)["patterns"]
            assert isinstance(raw_impacts, dict), "patterns property of {self.mapping_file} must be a dict"

            for pattern, parameters in raw_impacts.items():
                self.impacts[pattern] = Param(pattern, parameters) if parameters else default_param

    def load_modified_files(self) -> None:
        if self.ref != "refs/heads/main":
            # Gets the modified files. Computed with gh in a previous ci step.
            with open("modified_files.txt", "r", encoding="utf-8") as f:
                self.modified_files = [line.strip() for line in f]

    def load_scenario_mappings(self) -> None:
        if self.event_name in ("pull_request", "push"):
            # Get the mappings used to compute impacted scenarios by file, especially
            # test files
            # This file is generated with
            # ./run.sh MOCK_THE_TEST --collect-only --scenario-report
            with open(self.scenario_map_file, encoding="utf-8") as f:
                self.scenario_map = json.load(f)


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
    if inputs.is_gitlab:
        outputs |= extra_gitlab_output(inputs)
        logging.disable()

    rebuild_lambda_proxy = False

    if inputs.event_name not in ("pull_request", "push") or inputs.ref == "refs/heads/main":
        scenario_processor = ScenarioProcessor({all_scenario_groups.all.name})
        library_processor = LibraryProcessor(LIBRARIES)

    else:
        scenario_processor = ScenarioProcessor()
        library_processor = LibraryProcessor()

        scenario_processor.process_manifests(inputs)
        scenario_processor.compute_scenarios_by_files(inputs)

        library_processor.process_pr_title(inputs)

        assert inputs.modified_files is not None
        for file in inputs.modified_files:
            param = match_patterns(file, inputs.impacts)
            scenario_processor.add(file, param)
            library_processor.add(file, param)

            if file in (
                "utils/build/docker/lambda_proxy/pyproject.toml",
                "utils/build/docker/lambda-proxy.Dockerfile",
            ):
                rebuild_lambda_proxy = True

    if inputs.is_gitlab:
        outputs |= scenario_processor.get_outputs()
    else:
        outputs |= (
            library_processor.get_outputs()
            | {"rebuild_lambda_proxy": rebuild_lambda_proxy}
            | scenario_processor.get_outputs()
        )

    return stringify_outputs(outputs)


def main() -> None:
    logging.basicConfig(level=logging.INFO)

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

    inputs = Inputs(output=args.output)
    strings_out = process(inputs)
    print_outputs(strings_out, inputs)


if __name__ == "__main__":
    main()
