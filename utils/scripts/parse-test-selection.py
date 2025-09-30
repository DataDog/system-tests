from ruamel.yaml import YAML
from typing import Any, TextIO
from utils._context._scenarios import scenario_groups
from manifests.parser.core import load as load_manifests
from functools import reduce
from collections import defaultdict
import os
import sys
import argparse
import re
import json


LIBRARIES = {
        "python",
        "java",
        "golang",
        "cpp"
        }


def transform_pattern(pattern: str):
    pattern = pattern.replace(".", r"\.")
    pattern = pattern.replace("*", ".*")
    return pattern

def check_scenario(val):
    match val:
        case set():
            return True
        case str():
            return hasattr(scenario_groups, val)
        case list():
            return all([hasattr(scenario_groups, scenario) for scenario in val])
        case _:
            return False

def check_libraries(val):
    match val:
        case set():
            return True
        case str():
            return val in LIBRARIES
        case list():
            return all([library in LIBRARIES for library in val])
        case _:
            return False

class Param:
    def __init__(self):
        self.libraries = LIBRARIES
        self.scenarios = {scenario_groups.all.name}

def parse():
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    yml_path = os.path.join(root_dir, 'test-selection.yml')

    yaml = YAML()
    with open(yml_path, 'r') as file:
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
                    raise Exception(f"One or more of the libraries does not exist: {libraries}")

            if scenarios != "ALL":
                if check_scenario(scenarios):
                    ret[pattern].scenarios = set(scenarios)
                else:
                    raise Exception(f"One or more of the scenario groups does not exist: {scenarios}")

        return ret

    except AttributeError:
        raise Exception("Error in the test selection file")

def process_manifest_files(modified_files):
    # this file is generated with
    # ./run.sh MOCK_THE_TEST --collect-only --scenario-report
    with open("logs_mock_the_test/scenarios.json", encoding="utf-8") as f:
        scenario_map: dict[str, list[str]] = json.load(f)

    modified_nodeids = set()
    scenarios = set()

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
                scenarios |= set(scenario_names)
                break

    libraries = set()
    for file in modified_files:
        if file.startswith("manifests/"):
            libraries.add(file.split("/")[-1].split(".")[0])

    return libraries, scenarios

def process_test_files(modified_files):
    scenarios = set()
    for file in modified_files:
        if file.startswith("tests/"):
            if file.endswith(("/utils.py", "/conftest.py", ".json")):
                # particular use case for modification in tests/ of a file utils.py or conftest.py
                # in that situation, takes all scenarios executed in tests/<path>/

                # same for any json file

                folder = "/".join(file.split("/")[:-1]) + "/"  # python trickery to remove last element

                for sub_file, scenario_names in scenarios_by_files.items():
                    if sub_file.startswith(folder):
                        scenarios |= set(scenario_names)

    return set(), scenarios

def process_general_files(modified_files):
    file_map = parse()

    libraries = set()
    scenarios = set()

    for file in modified_files:
        matched = False
        for pattern, param in file_map.items():
            if re.match(pattern, file):
                libraries |= param.libraries
                scenarios |= param.scenarios
                matched = True
        if not matched:
            libraries = LIBRARIES
            scenarios = {scenario_groups.all.name}

    return libraries, scenarios

def user_library_choice(detected_libraries):
    libraries = set()

    pr_title = os.environ.get("GITHUB_PR_TITLE", "").lower()
    match = re.search(rf"^\[({libraries})(?:@([^\]]+))?\]", pr_title)
    user_choice = None
    branch_selector = None
    if match:
        print(f"PR title matchs => run {match[1]}")
        user_choice = match[1]
        libraries |= {user_choice}

        # if users specified a branch, another job will prevent the merge
        # so let user do what he/she wants :
        branch_selector = match[2]

    if user_choice and not branch_selector and detected_libraries != libraries:
        raise Exception(
            f"""File {file} is modified, and it may impact {', '.join(impacted_libraries)}.
            Please remove the PR title prefix [{user_choice}]"""
        )

    return libraries, set()

def process_rebuild_lambda_proxy(modified_files):
    for file in modified_files:
        if file in ("utils/build/docker/lambda_proxy/pyproject.toml", "utils/build/docker/lambda-proxy.Dockerfile"):
            return True
    return False


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

    ret = []

    if "GITLAB_CI" in os.environ:
        event_name = os.environ.get("CI_PIPELINE_SOURCE", "push")
        ref = os.environ.get("CI_COMMIT_REF_NAME", "")
        print("CI_PIPELINE_SOURCE=" + event_name)
        print("CI_COMMIT_REF_NAME=" + ref)
    else:
        event_name = os.environ.get("GITHUB_EVENT_NAME", "pull_request")
        ref = os.environ.get("GITHUB_REF", "fake-branch-name")

    if event_name == "schedule" or ref == "refs/heads/main":
        ret.append(LIBRARIES, {scenario_groups.all.name})

    elif event_name in ("pull_request", "push"):
        # with open("modified_files.txt", encoding="utf-8") as f:
        #     modified_files = [line.strip() for line in f]
        modified_files = ["test"]


        ret.append(process_manifest_files(modified_files))
        ret.append(process_test_files(modified_files))
        ret.append(process_general_files(modified_files))
        ret.append(user_library_choice(ret[0]))

        rebuild_lambda_proxy = process_rebuild_lambda_proxy(modified_files)

        # print(ret)

        libraries, scenarios = reduce(
            lambda acc, r: [acc[0]|r[0], acc[1]|r[1]], ret, [set(), set()]
        )

    populated_libraries = [
        {
            "library": library,
            "version": "prod",
        }
        for library in sorted(libraries)
    ] + [
        {
            "library": library,
            "version": "dev",
        }
        for library in sorted(libraries)
        if "otel" not in library
    ]

    libraries_with_dev = [item["library"] for item in populated_libraries if item["version"] == "dev"]
    outputs = {
        "library_matrix": populated_libraries,
        "libraries_with_dev": libraries_with_dev,
        "desired_execution_time": 600 if len(libraries) == 1 else 3600,
        "rebuild_lambda_proxy": rebuild_lambda_proxy,
    }

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            print_library_outputs(outputs, f)
    else:
        print_library_outputs(outputs, sys.stdout)

    print("scenario_groups=" + ",".join(scenarios))


def print_library_outputs(outputs: dict[str, Any], f: TextIO) -> None:
    for name, value in outputs.items():
        print(f"{name}={json.dumps(value)}", file=f)




if __name__ == "__main__":
    main()
