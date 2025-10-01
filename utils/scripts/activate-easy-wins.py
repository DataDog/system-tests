from __future__ import annotations

import argparse
import json
import os
import zipfile
from enum import Enum
from pathlib import Path
from typing import Any

import requests
import ruamel.yaml
from tqdm import tqdm


class UnexpectedStatusError(Exception):
    """Raised when an unexpected status is encountered."""


LIBRARIES = [
    # "agent",
    "cpp_httpd",
    # "cpp_nginx",
    "cpp",
    # "dd_apm_inject",
    "dotnet",
    "golang",
    "java",
    # "k8s_cluster_agent",
    "nodejs",
    "php",
    "python_lambda",
    # "python_otel",
    "python",
    "ruby",
    # "rust"
]

ARTIFACT_URL = (
    "https://api.github.com/repos/DataDog/system-tests-dashboard/actions/workflows/nightly.yml/runs?per_page=1"
)


def pull_artifact(url: str, token: str, path_root: str, path_data_root: str) -> None:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "python-requests",
    }

    # Get workflow runs
    with requests.get(url, headers=headers, timeout=60) as resp_runs:
        resp_runs.raise_for_status()
        runs_data = resp_runs.json()

    download_url = None
    page = 0
    while not download_url:
        page += 1
        artifacts_url = runs_data["workflow_runs"][0]["artifacts_url"] + f"?page={page}"
        with requests.get(artifacts_url, headers=headers, timeout=60) as resp_artifacts:
            resp_artifacts.raise_for_status()
            artifacts_data = resp_artifacts.json()

        # Download the first artifact
        for artifact in artifacts_data["artifacts"]:
            if artifact["name"] == "test-report":
                download_url = artifact["archive_download_url"]

        # If we've checked all pages and found no test-report artifact, error
        if not download_url and len(artifacts_data["artifacts"]) == 0:
            raise RuntimeError("test-report not found in the last nightly run")

    with requests.get(download_url, headers=headers, stream=True, timeout=60) as r:
        r.raise_for_status()
        total_size = int(r.headers.get("content-length", 0))

        with (
            open(f"{path_root}/data.zip", "wb") as f,
            tqdm(total=total_size, unit="B", unit_scale=True, desc="Downloading artifact") as pbar,
        ):
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))

    # Extract the downloaded zip file
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


def parse_artifact_data(
    path_data_opt: str, libraries: list[str]
) -> dict[str, dict[str, dict[str, dict[str, tuple[TestClassStatus, set[str]]]]]]:
    test_data: dict[str, dict[str, dict[str, dict[str, tuple[TestClassStatus, set[str]]]]]] = {}

    for directory in os.listdir(path_data_opt):
        if "dev" in directory:
            continue

        for scenario in os.listdir(f"{path_data_opt}/{directory}"):
            try:
                with open(f"{path_data_opt}/{directory}/{scenario}/report.json", encoding="utf-8") as file:
                    scenario_data = json.load(file)
            except FileNotFoundError:
                continue

            library = scenario_data["context"]["library_name"]
            if library not in libraries:
                break

            variant = scenario_data["context"]["weblog_variant"]

            if not test_data.get(library):
                test_data[library] = {}

            for test in scenario_data["tests"]:
                test_path = test["nodeid"].split("::")[0]
                test_class = test["nodeid"].split("::")[1]

                if not test_data[library].get(test_path):
                    test_data[library][test_path] = {}

                if not test_data[library][test_path].get(test_class):
                    test_data[library][test_path][test_class] = {}

                if not test_data[library][test_path][test_class].get(variant):
                    test_data[library][test_path][test_class][variant] = (
                        TestClassStatus.parse(test["outcome"]),
                        set(test["metadata"]["owners"]),
                    )
                else:
                    outcome = TestClassStatus.parse(test["outcome"])
                    previous_outcome, previous_owners = test_data[library][test_path][test_class][variant]
                    test_data[library][test_path][test_class][variant] = (
                        merge_update_status(outcome, previous_outcome),
                        set(test["metadata"]["owners"]) | previous_owners,
                    )

    return test_data


def parse_manifest(library: str, path_root: str, yaml: ruamel.yaml.YAML) -> ruamel.yaml.CommentedMap:  # type: ignore[type-arg]
    with open(f"{path_root}/manifests/{library}.yml", encoding="utf-8") as file:
        return yaml.load(file)


def write_manifest(manifest: ruamel.yaml.CommentedMap, outfile_path: str, yaml: ruamel.yaml.YAML) -> None:  # type: ignore[type-arg]
    with open(outfile_path, "w", encoding="utf8") as outfile:
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


def get_global_update_status(root: Any, current: TestClassStatus, owners: set[str]) -> tuple[TestClassStatus, set[str]]:  # type: ignore[misc]  # noqa: ANN401
    if current == TestClassStatus.NOEDIT:
        return TestClassStatus.NOEDIT, set()
    if isinstance(root, dict):
        for branch in root.values():
            current = merge_update_status(current, get_global_update_status(branch, current, owners)[0])
    else:
        current = merge_update_status(current, root[0])
        owners |= root[1]
    return current, owners


def build_updated_subtree(
    test_data_root: Any,  # type: ignore[misc]  # noqa: ANN401
    original_value: str,
    version: str,
    *,
    is_file_level: bool = False,
) -> ruamel.yaml.CommentedMap | None:  # type: ignore[type-arg]
    """Build an updated subtree containing both activated and non-activated parts."""

    def _collect_all_paths_with_status(
        root: Any,  # noqa: ANN401
        path: list[str],
    ) -> list[tuple[list[str], tuple[TestClassStatus, set[str]]]]:  # type: ignore[misc]
        all_paths = []

        if isinstance(root, dict):
            for key, branch in root.items():
                branch_paths = _collect_all_paths_with_status(branch, [*path, key])
                all_paths.extend(branch_paths)
        # Leaf node - return path with its status
        elif len(path) > 1 and "parametric" in path[-1]:
            all_paths.append((path[:-1], root))
        else:
            all_paths.append((path, root))

        return all_paths

    all_paths = _collect_all_paths_with_status(test_data_root, [])
    activable_paths = [
        path for path, status in all_paths if status[0] in (TestClassStatus.ACTIVATE, TestClassStatus.CACTIVATE)
    ]

    if not activable_paths:
        return original_value

    # For test class-level entries, only build subtree if partial activation is needed
    if len(activable_paths) == len(all_paths) and not is_file_level:
        return version

    # Build subtree structure with both activated and non-activated paths
    # Sort paths to ensure lexicographic key ordering
    sorted_paths = sorted(all_paths, key=lambda x: x[0])

    subtree = ruamel.yaml.CommentedMap()

    for path, status in sorted_paths:
        current = subtree
        for part in path[:-1]:
            if part not in current:
                current[part] = ruamel.yaml.CommentedMap()
            current = current[part]

        # Set value based on whether this path should be activated
        if status[0] in (TestClassStatus.ACTIVATE, TestClassStatus.CACTIVATE):
            current[path[-1]] = version  # New version for activated paths
        else:
            current[path[-1]] = original_value  # Keep original value for non-activated paths

    return subtree


def update_entry(
    language: str,
    _manifest: ruamel.yaml.CommentedMap,  # type: ignore[type-arg]
    test_data: dict[str, dict[str, dict[str, dict[str, tuple[TestClassStatus, set[str]]]]]],
    search: list[str | None],
    root_path: list[str],
    ancestor: ruamel.yaml.CommentedMap,  # type: ignore[type-arg]
    versions: dict[str, str],
    excluded_owners: set[str],
) -> tuple[str, set[str]] | None:
    try:
        if search[2] and isinstance(search[0], str) and isinstance(search[1], str):
            test_data_root = test_data[language][search[0]][search[1]][search[2]]
        elif search[1] and isinstance(search[0], str) and isinstance(search[1], str):
            test_data_root: Any = test_data[language][search[0]][search[1]]  # type: ignore[misc]
        elif isinstance(search[0], str):
            test_data_root: Any = test_data[language][search[0]]  # type: ignore[misc]
        else:
            return None
        update_status, owners = get_global_update_status(test_data_root, TestClassStatus.ACTIVATE, set())

        current_value = ancestor[root_path[-1]]
        should_activate = (
            "bug" in current_value or "missing_feature" in current_value or "incomplete_test_app" in current_value
        )

        if (
            should_activate
            and update_status in (TestClassStatus.ACTIVATE, TestClassStatus.CACTIVATE)
            and not owners & excluded_owners
        ):
            ret = (ancestor[root_path[-1]], owners)

            # Determine if this is a file-level entry (search[1] is None) or test class-level (search[1] is set)
            is_file_level = search[1] is None

            # Try to build a subtree for partial activation
            subtree = build_updated_subtree(
                test_data_root, current_value, versions[language], is_file_level=is_file_level
            )

            if subtree is not None:
                # Partial activation or file-level activation
                ancestor[root_path[-1]] = subtree
            elif update_status == TestClassStatus.ACTIVATE:
                # Full activation for test class level
                ancestor[root_path[-1]] = versions[language]
            else:
                return None

            # Remove comments from updated entry
            if hasattr(ancestor, "ca") and hasattr(ancestor.ca, "items") and root_path[-1] in ancestor.ca.items:
                del ancestor.ca.items[root_path[-1]]
            return ret

        return None
    except KeyError:
        return None


def update_tree(
    root: ruamel.yaml.CommentedMap | str,  # type: ignore[type-arg]
    ancestor: ruamel.yaml.CommentedMap,  # type: ignore[type-arg]
    language: str,
    manifest: ruamel.yaml.CommentedMap,  # type: ignore[type-arg]
    test_data: dict[str, dict[str, dict[str, dict[str, tuple[TestClassStatus, set[str]]]]]],
    root_path: list[str],
    versions: dict[str, str],
    excluded_owners: set[str],
) -> list[tuple[list[str], str, str, set[str]]]:
    updates = []
    if isinstance(root, ruamel.yaml.comments.CommentedMap):
        for branch_path, branch in root.items():
            ret = update_tree(
                branch, root, language, manifest, test_data, [*root_path, branch_path], versions, excluded_owners
            )
            updates += ret
    else:
        search = build_search(root_path)
        result = update_entry(language, manifest, test_data, search, root_path, ancestor, versions, excluded_owners)
        if result:
            old_status, owners = result
            updates.append((root_path, old_status, versions[language], owners))
    return updates


def update_manifest(
    language: str,
    manifest: ruamel.yaml.CommentedMap,
    test_data: dict[str, dict[str, dict[str, dict[str, tuple[TestClassStatus, set[str]]]]]],  # type: ignore[type-arg]
    versions: dict[str, str],
    excluded_owners: set[str],
) -> list[tuple[list[str], str, str, set[str]]]:
    return update_tree(manifest, manifest, language, manifest, test_data, [], versions, excluded_owners)


def get_versions(path_data_opt: str, libraries: list[str]) -> dict[str, str]:
    versions = {}
    for library in libraries:
        found_version = False

        for variant in os.listdir(path_data_opt):
            if found_version:
                break
            if library not in variant:
                continue

            for scenario in os.listdir(f"{path_data_opt}/{variant}"):
                if found_version:
                    break

                try:
                    with open(f"{path_data_opt}/{variant}/{scenario}/report.json", encoding="utf-8") as file:
                        data = json.load(file)
                    if data["context"]["library_name"] == library:
                        versions[library] = f"v{data['context']['library']}"
                        found_version = True
                except (FileNotFoundError, KeyError):
                    continue

        if library == "cpp_httpd" and versions[library] == "v99.99.99":
            with requests.get("https://api.github.com/repos/DataDog/httpd-datadog/releases", timeout=60) as resp_runs:
                versions[library] = resp_runs.json()[0]["tag_name"]

        if not found_version:
            versions[library] = "xpass"

    return versions


def get_environ() -> dict[str, str]:
    environ = {**os.environ}

    try:
        with open(".env", "r", encoding="utf-8") as f:
            lines = [line.replace("export ", "").strip().split("=") for line in f if line.strip()]
            environ = {**environ, **dict(lines)}
    except FileNotFoundError:
        pass

    return environ


def main() -> None:
    environ = get_environ()
    parser = argparse.ArgumentParser(description="Activate easy wins in system tests")
    parser.add_argument(
        "--libraries",
        nargs="*",
        choices=LIBRARIES,
        default=LIBRARIES,
        help="Libraries to update (default: all libraries)",
    )
    parser.add_argument("--no-download", action="store_true", help="Skip downloading test data")
    parser.add_argument("--data-path", type=str, help="Custom path to store test data")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be updated without writing to files")
    parser.add_argument("--summary-only", action="store_true", help="Show only the final summary")
    parser.add_argument("--exclude", nargs="*", default=[], help="List of owners to exclude from activation")

    args = parser.parse_args()

    yaml = ruamel.yaml.YAML()
    yaml.explicit_start = True

    yaml.width = 4096
    yaml.comment_column = 120
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=2, offset=2)

    path_root = str(Path(__file__).parents[2])
    path_data_root = args.data_path if args.data_path else f"{path_root}/data"
    path_data_opt = path_data_root

    if not args.no_download:
        print("Pulling test results")
        token = environ["GITHUB_TOKEN"]  # expects your GitHub token in env var
        pull_artifact(ARTIFACT_URL, token, path_root, path_data_root)

    print("Parsing test results")
    test_data = parse_artifact_data(path_data_opt, args.libraries)
    versions = get_versions(path_data_opt, args.libraries)

    if args.dry_run and not args.summary_only:
        print("🔍 DRY RUN MODE - No files will be modified\n")

    excluded_owners = set(args.exclude)
    total_updates = 0
    library_counts = {}

    for library in args.libraries:
        manifest = parse_manifest(library, path_root, yaml)
        updates = update_manifest(library, manifest, test_data, versions, excluded_owners)
        library_counts[library] = len(updates)

        if not args.summary_only:
            action = "Analyzing" if args.dry_run else "Processing"
            print(f"\n📋 {action} {library.upper()}...")

            if updates:
                verb = "Would update" if args.dry_run else "Found"
                print(f"✅ {verb} {len(updates)} updates:")
                for path, old_status, new_version, owners in updates:
                    search_result = build_search(path)
                    test_path = f"{search_result[0]}::{search_result[1]}" if search_result[1] else search_result[0]
                    owners_str = ", ".join(sorted(owners)) if owners else "No owners"
                    print(f"   • {test_path}")
                    print(f"     {old_status} → {new_version}")
                    print(f"     Owners: {owners_str}")
            else:
                message = "No updates would be needed" if args.dry_run else "No updates needed"
                print(f"   {message}")

        total_updates += len(updates)
        if not args.dry_run:
            write_manifest(manifest, f"{path_root}/manifests/{library}.yml", yaml)

    # Display summary with per-library counts
    if args.dry_run:
        print(f"\n🔍 Dry Run Summary: Would update {total_updates} entries across {len(args.libraries)} libraries")
    else:
        print(f"\n🎉 Summary: Updated {total_updates} entries across {len(args.libraries)} libraries")

    # Show per-library breakdown
    for library, count in library_counts.items():
        if count > 0:
            print(f"   • {library}: {count}")
        elif not args.summary_only:  # Only show zero counts in detailed mode
            print(f"   • {library}: 0")


if __name__ == "__main__":
    main()
