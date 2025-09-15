from __future__ import annotations

import cProfile
import json
import os
import urllib.request
import zipfile
from enum import Enum
from pathlib import Path
from typing import Any

import requests
import ruamel.yaml


class UnexpectedStatusError(Exception):
    """Raised when an unexpected status is encountered."""


LIBRARIES = [
    "agent",
    "cpp_httpd",
    "cpp_nginx",
    "cpp",
    "dd_apm_inject",
    "dotnet",
    "golang",
    "java",
    "k8s_cluster_agent",
    "nodejs",
    "php",
    "python_lambda",
    "python_otel",
    "python",
    "ruby",
    "rust"
]

ARTIFACT_URL = "https://api.github.com/repos/DataDog/system-tests-dashboard/actions/workflows/push-feature-parity-dashboard.yml/runs?per_page=5"


def pull_artifact(url: str, path_root: str, path_data_root: str) -> None:
    token = os.getenv("GITHUB_TOKEN")  # expects your GitHub token in env var

    req_runs = urllib.request.Request(url)  # noqa: S310
    req_runs.add_header("Authorization", f"token {token}")
    req_runs.add_header("Accept", "application/vnd.github+json")
    with urllib.request.urlopen(req_runs) as resp_runs:  # noqa: S310
        artifacts = json.load(resp_runs)

    artifacts_url = artifacts["workflow_runs"][4]["artifacts_url"]
    req_artifacts = urllib.request.Request(artifacts_url)  # noqa: S310
    req_artifacts.add_header("Authorization", f"token {token}")
    req_artifacts.add_header("Accept", "application/vnd.github+json")
    with urllib.request.urlopen(req_artifacts) as resp_artifacts:  # noqa: S310
        artifacts = json.load(resp_artifacts)

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "python-requests",
    }
    download_url = artifacts["artifacts"][0]["archive_download_url"]

    with requests.get(download_url, headers=headers, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(f"{path_root}/data.zip", "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

    with zipfile.ZipFile(f"{path_root}/data.zip") as z:
        z.extractall(path_data_root)


class TestClassStatus(Enum):
    ACTIVATE = 1
    CACTIVATE = 2
    NOEDIT = 3

    @staticmethod
    def parse(test_status: str) -> TestClassStatus:
        match test_status:
            case "passed":
                return TestClassStatus.CACTIVATE
            case "xpassed":
                return TestClassStatus.ACTIVATE
            case "failed":
                return TestClassStatus.NOEDIT
            case "xfailed":
                return TestClassStatus.NOEDIT
            case "skipped":
                return TestClassStatus.NOEDIT
            case _:
                raise UnexpectedStatusError(f"Unexpected status: {test_status}")


def merge_update_status(status1: TestClassStatus, status2: TestClassStatus) -> TestClassStatus:
    match (status1, status2):
        case (TestClassStatus.ACTIVATE, TestClassStatus.ACTIVATE):
            return TestClassStatus.ACTIVATE
        case (TestClassStatus.CACTIVATE, TestClassStatus.ACTIVATE):
            return TestClassStatus.CACTIVATE
        case (TestClassStatus.ACTIVATE, TestClassStatus.CACTIVATE):
            return TestClassStatus.CACTIVATE
        case (TestClassStatus.CACTIVATE, TestClassStatus.CACTIVATE):
            return TestClassStatus.CACTIVATE
        case (TestClassStatus.NOEDIT, _):
            return TestClassStatus.NOEDIT
        case (_, TestClassStatus.NOEDIT):
            return TestClassStatus.NOEDIT
        case _:
            raise UnexpectedStatusError(f"Unexpected status: {status1}, {status2}")


def parse_artifact_data(path_data_opt: str) -> dict[str, dict[str, dict[str, dict[str, TestClassStatus]]]]:
    test_data: dict[str, dict[str, dict[str, dict[str, TestClassStatus]]]] = {}
    for language in os.listdir(path_data_opt):
        test_data[language] = {}
        for variant in os.listdir(f"{path_data_opt}/{language}"):
            for scenario in os.listdir(f"{path_data_opt}/{language}/{variant}"):
                with open(f"{path_data_opt}/{language}/{variant}/{scenario}") as file:
                    scenario_data = json.load(file)
                for test in scenario_data["tests"]:
                    test_path = test["path"].split("::")[0]
                    test_class = test["path"].split("::")[1]
                    if not test_data[language].get(test_path):
                        test_data[language][test_path] = {}
                    if not test_data[language][test_path].get(test_class):
                        test_data[language][test_path][test_class] = {}
                    if not test_data[language][test_path][test_class].get(variant):
                        test_data[language][test_path][test_class][variant] = TestClassStatus.parse(test["outcome"])
                    else:
                        outcome = TestClassStatus.parse(test["outcome"])
                        previous_outcome = test_data[language][test_path][test_class][variant]
                        test_data[language][test_path][test_class][variant] = merge_update_status(
                            outcome, previous_outcome
                        )

    return test_data


def parse_manifest(library: str, path_root: str) -> ruamel.yaml.CommentedMap:  # type: ignore[type-arg]
    yaml = ruamel.yaml.YAML()
    yaml.width = 200
    with open(f"{path_root}/manifests/{library}.yml") as file:
        return yaml.load(file)


def write_manifest(manifest: ruamel.yaml.CommentedMap, outfile: str) -> None:  # type: ignore[type-arg]
    yaml = ruamel.yaml.YAML()
    yaml.width = 200
    with open(outfile, "w", encoding="utf8") as outfile:
        yaml.dump(manifest, outfile)


def build_search(path: list[str]) -> list[str | None]:
    ret: list[str | None] = ["", None, None]
    field_count = 1
    for level in path:
        if len(level) == 0 or level[-1] == "/" or level[-3:] == ".py":
            if isinstance(ret[0], str):
                ret[0] += level
        else:
            ret[field_count] = level
            field_count += 1
    return ret


def get_global_update_status(root: Any, current: TestClassStatus) -> TestClassStatus:  # type: ignore[misc]  # noqa: ANN401
    if current == TestClassStatus.NOEDIT:
        return TestClassStatus.NOEDIT
    elif type(root) is dict:
        for branch in root.values():
            current = merge_update_status(current, get_global_update_status(branch, current))
    else:
        current = merge_update_status(current, root)
    return current


def update_entry(
    language: str,
    _manifest: ruamel.yaml.CommentedMap,  # type: ignore[type-arg]
    test_data: dict[str, dict[str, dict[str, dict[str, TestClassStatus]]]],
    search: list[str | None],
    root_path: list[str],
    ancester: ruamel.yaml.CommentedMap,  # type: ignore[type-arg]
    versions
) -> None:
    get_global_update_status(test_data, TestClassStatus.ACTIVATE)
    update_status = TestClassStatus.NOEDIT
    try:
        if search[1] and isinstance(search[0], str) and isinstance(search[1], str):
            update_status = get_global_update_status(
                test_data[language][search[0]][search[1]], TestClassStatus.ACTIVATE
            )
        elif isinstance(search[0], str):
            update_status = get_global_update_status(test_data[language][search[0]], TestClassStatus.ACTIVATE)
    except (KeyError, TypeError):
        pass
    if update_status == TestClassStatus.ACTIVATE and (
        "bug" in ancester[root_path[-1]]
        or "missing_feature" in ancester[root_path[-1]]
        or "incomplete_test_app" in ancester[root_path[-1]]
    ):
        ancester[root_path[-1]] = versions[language]
        # Remove comments from updated entry
        if hasattr(ancester, "ca") and hasattr(ancester.ca, "items") and root_path[-1] in ancester.ca.items:
            del ancester.ca.items[root_path[-1]]


def update_tree(
    root: ruamel.yaml.CommentedMap | str,  # type: ignore[type-arg]
    ancester: ruamel.yaml.CommentedMap,  # type: ignore[type-arg]
    language: str,
    manifest: ruamel.yaml.CommentedMap,  # type: ignore[type-arg]
    test_data: dict[str, dict[str, dict[str, dict[str, TestClassStatus]]]],
    root_path: list[str],
    versions
) -> None:
    if type(root) is ruamel.yaml.comments.CommentedMap:
        for branch_path, branch in root.items():
            update_tree(branch, root, language, manifest, test_data, [*root_path, branch_path], versions)
    else:
        search = build_search(root_path)
        update_entry(language, manifest, test_data, search, root_path, ancester, versions)


def update_manifest(
    language: str,
    manifest: ruamel.yaml.CommentedMap,
    test_data: dict[str, dict[str, dict[str, dict[str, TestClassStatus]]]],  # type: ignore[type-arg]
    versions
) -> None:
    update_tree(manifest, manifest, language, manifest, test_data, [], versions)


def get_versions(path_data_opt: str):
    versions = {}
    for library in os.listdir(path_data_opt):
        variant = os.listdir(f"{path_data_opt}/{library}")[0]
        file_paths = os.listdir(f"{path_data_opt}/{library}/{variant}")
        found_version = False
        for file_path in file_paths:
            if found_version:
                break
            with open(f"{path_data_opt}/{library}/{variant}/{file_path}") as file:
                data = json.load(file)
                for dep in data["testedDependencies"]:
                    if dep["name"] == "library":
                        versions[library] = dep["version"]
                        found_version = True
                if not versions.get(library):
                    versions[library] = "xpass"
    return versions



def main() -> None:
    path_root = Path(__file__).parents[2]
    path_data_root = f"{path_root}/data"
    path_data_opt = f"{path_data_root}/dev"

    get_versions(path_data_opt)
    print("Pulling test results")
    pull_artifact(ARTIFACT_URL, path_root, path_data_root)
    print("Parsing test results")
    test_data = parse_artifact_data(path_data_opt)
    versions = get_versions(path_data_opt)
    for library in LIBRARIES:
        print(f"Updating manifest for {library}")
        manifest = parse_manifest(library, path_root)
        update_manifest(library, manifest, test_data, versions)
        write_manifest(manifest, f"{path_root}/manifests/{library}.yml")

if __name__ == "__main__":
    main()
