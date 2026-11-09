"""Refresh the checked-in FFE fixture snapshot from its canonical repository."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DESTINATION = REPOSITORY_ROOT / "tests" / "parametric" / "test_ffe" / "ffe-system-test-data"
FIXTURE_REPOSITORY = "https://github.com/DataDog/ffe-system-test-data.git"
FIXTURE_REF_PATTERN = re.compile(r"[A-Za-z0-9._/-]+")
SELECTION_VECTORS_PATH = Path("flag-selection/selection-vectors.json")
SELECTION_DROP_REASONS = frozenset({"malformed_selection", "too_many_values", "invalid_key_pattern", "invalid_tag"})


def _validate_fixture_ref(fixture_ref: str) -> None:
    if (
        not fixture_ref
        or fixture_ref.startswith("-")
        or ".." in fixture_ref
        or FIXTURE_REF_PATTERN.fullmatch(fixture_ref) is None
    ):
        msg = f"Invalid FFE fixture ref: {fixture_ref!r}"
        raise ValueError(msg)


def _run_git(working_directory: Path, *arguments: str) -> str:
    environment = {
        **os.environ,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
    }
    result = subprocess.run(
        ["git", *arguments],
        cwd=working_directory,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _copy_entry(source: Path, destination: Path) -> None:
    if source.is_symlink():
        msg = f"Refusing to copy symbolic link from FFE fixture repository: {source}"
        raise ValueError(msg)

    if source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        return

    if not source.is_dir():
        msg = f"Refusing to copy unsupported filesystem entry from FFE fixture repository: {source}"
        raise ValueError(msg)

    destination.mkdir(parents=True, exist_ok=True)
    for child in sorted(source.iterdir()):
        _copy_entry(child, destination / child.name)


def _copy_fixture_snapshot(source: Path, snapshot: Path) -> None:
    # Import rules-based evaluator corpora and selection vectors, not precomputed assignments.
    for name in ("ufc-config.json", "evaluation-cases"):
        _copy_entry(source / name, snapshot / name)
    if (source / SELECTION_VECTORS_PATH.parent).is_symlink():
        msg = "Refusing to copy symbolic link from FFE fixture repository: flag-selection"
        raise ValueError(msg)
    _copy_entry(source / SELECTION_VECTORS_PATH, snapshot / SELECTION_VECTORS_PATH)

    feature_suites = source / "evaluation-suites"
    if feature_suites.exists() or feature_suites.is_symlink():
        _copy_entry(feature_suites, snapshot / feature_suites.name)


def _validate_evaluation_suite(config_path: Path, cases_directory: Path) -> int:
    if not config_path.is_file() or not cases_directory.is_dir():
        msg = "FFE fixture repository does not contain the expected fixture layout"
        raise ValueError(msg)

    with config_path.open(encoding="utf-8") as config_file:
        config = json.load(config_file)
    if not isinstance(config, dict) or not isinstance(config.get("flags"), dict) or not config["flags"]:
        msg = "FFE UFC fixture must contain a non-empty flags object"
        raise ValueError(msg)

    case_files = sorted(cases_directory.glob("*.json"))
    if any(not path.is_file() or path.suffix != ".json" for path in cases_directory.iterdir()):
        msg = "FFE evaluation-cases must contain only JSON files"
        raise ValueError(msg)
    if not case_files:
        msg = "No FFE JSON fixture files found"
        raise ValueError(msg)

    case_count = 0
    for case_file in case_files:
        with case_file.open(encoding="utf-8") as fixture_file:
            test_cases = json.load(fixture_file)
        if not isinstance(test_cases, list):
            msg = f"{case_file} must contain a JSON array of test cases"
            raise TypeError(msg)
        if not test_cases:
            msg = f"{case_file} must contain at least one evaluation case"
            raise ValueError(msg)
        case_count += len(test_cases)

    return case_count


def _validate_fixture_snapshot(snapshot: Path) -> int:
    fixture_count = _validate_evaluation_suite(snapshot / "ufc-config.json", snapshot / "evaluation-cases")

    suites_directory = snapshot / "evaluation-suites"
    if not suites_directory.exists():
        return fixture_count
    if not suites_directory.is_dir() or suites_directory.is_symlink():
        msg = "FFE evaluation-suites must be a directory"
        raise ValueError(msg)
    suite_directories = sorted(suites_directory.iterdir())
    if not suite_directories:
        msg = "FFE evaluation-suites must contain at least one feature suite"
        raise ValueError(msg)
    for suite_directory in suite_directories:
        if not suite_directory.is_dir() or suite_directory.is_symlink():
            msg = "FFE evaluation-suites must contain only suite directories"
            raise ValueError(msg)
        if {entry.name for entry in suite_directory.iterdir()} != {"ufc-config.json", "cases"}:
            msg = f"FFE feature suite {suite_directory.name} must contain only ufc-config.json and cases"
            raise ValueError(msg)
        fixture_count += _validate_evaluation_suite(
            suite_directory / "ufc-config.json",
            suite_directory / "cases",
        )

    return fixture_count


def _validate_selection_vectors(snapshot: Path) -> int:
    with (snapshot / SELECTION_VECTORS_PATH).open(encoding="utf-8") as fixture_file:
        vectors = json.load(fixture_file)
    cases = vectors.get("cases") if isinstance(vectors, dict) else None
    if not isinstance(cases, list) or not cases:
        msg = "FFE selection vectors must contain a non-empty cases array"
        raise ValueError(msg)

    names: set[str] = set()
    sdk_count = 0
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("name"), str) or not case["name"]:
            msg = "FFE selection vector must have a non-empty name"
            raise ValueError(msg)
        name = case["name"]
        if name in names:
            msg = f"Duplicate FFE selection vector name: {name}"
            raise ValueError(msg)
        names.add(name)
        if ("query" in case) == ("rawQuery" in case):
            msg = f"FFE selection vector must have exactly one query form: {name}"
            raise ValueError(msg)
        if "rawQuery" in case:
            if not isinstance(case["rawQuery"], str) or "sdk" in case:
                msg = f"Raw-query FFE selection vector must not have an SDK expectation: {name}"
                raise ValueError(msg)
            continue

        query = case["query"]
        if (
            not isinstance(query, dict)
            or set(query) - {"selected_flag_tags", "selected_flag_key_patterns"}
            or any(
                not isinstance(values, list) or any(not isinstance(value, str) for value in values)
                for values in query.values()
            )
        ):
            msg = f"Invalid FFE selection vector query: {name}"
            raise ValueError(msg)
        sdk = case.get("sdk")
        if not isinstance(sdk, dict) or set(sdk) not in ({"selection"}, {"dropped"}):
            msg = f"FFE selection vector must have one SDK expectation: {name}"
            raise ValueError(msg)
        if "dropped" in sdk:
            if not isinstance(sdk["dropped"], str) or sdk["dropped"] not in SELECTION_DROP_REASONS:
                msg = f"Unknown FFE selection drop reason: {name}"
                raise ValueError(msg)
        else:
            selection = sdk["selection"]
            if (
                not isinstance(selection, dict)
                or set(selection) != {"tags", "keyPatterns"}
                or any(
                    not isinstance(values, list) or any(not isinstance(value, str) or not value for value in values)
                    for values in selection.values()
                )
            ):
                msg = f"Invalid canonical FFE selection expectation: {name}"
                raise ValueError(msg)
        sdk_count += 1

    if sdk_count == 0:
        msg = "No FFE selection SDK cases found"
        raise ValueError(msg)
    return sdk_count


def _relative_files(directory: Path, excluded_files: frozenset[str] = frozenset()) -> list[Path]:
    return sorted(
        path.relative_to(directory)
        for path in directory.rglob("*")
        if path.is_file() and path.relative_to(directory).as_posix() not in excluded_files
    )


def _have_same_contents(snapshot: Path, destination: Path) -> bool:
    if not destination.is_dir():
        return False

    snapshot_files = _relative_files(snapshot)
    destination_files = _relative_files(destination, frozenset({"SOURCE.md"}))
    if snapshot_files != destination_files:
        return False

    return all(
        (snapshot / relative_path).read_bytes() == (destination / relative_path).read_bytes()
        for relative_path in snapshot_files
    )


def _write_source_metadata(snapshot: Path, source_commit: str) -> None:
    (snapshot / "SOURCE.md").write_text(
        f"""# FFE Fixture Snapshot

These files are copied from the canonical FFE fixture repository.

Canonical source: https://github.com/DataDog/ffe-system-test-data
Source commit: {source_commit}

Do not edit these fixtures directly in system-tests. Add or update shared FFE behavior in
ffe-system-test-data first, then refresh this snapshot.

The weekly update workflow runs `python3 utils/scripts/update_ffe_fixtures.py` and opens a signed
draft test PR only when the evaluator or selection fixture contents change.
""",
        encoding="utf-8",
    )


def _set_github_outputs(source_commit: str, fixture_count: int, selection_fixture_count: int, *, changed: bool) -> None:
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with Path(github_output).open("a", encoding="utf-8") as output_file:
            output_file.write(f"source_commit={source_commit}\n")
            output_file.write(f"fixture_count={fixture_count}\n")
            output_file.write(f"selection_fixture_count={selection_fixture_count}\n")
            output_file.write(f"changed={str(changed).lower()}\n")


def update_fixtures(fixture_ref: str) -> bool:
    """Update the snapshot and return whether its allowed contents changed."""
    _validate_fixture_ref(fixture_ref)

    with tempfile.TemporaryDirectory(prefix="ffe-system-test-data-") as temporary_directory:
        temporary_path = Path(temporary_directory)
        source = temporary_path / "source"
        snapshot = temporary_path / "snapshot"
        source.mkdir()
        snapshot.mkdir()

        _run_git(source, "init", "--quiet")
        _run_git(source, "remote", "add", "origin", FIXTURE_REPOSITORY)
        _run_git(source, "fetch", "--quiet", "--depth", "1", "origin", fixture_ref)
        _run_git(source, "checkout", "--quiet", "--detach", "FETCH_HEAD")
        source_commit = _run_git(source, "rev-parse", "HEAD")

        _copy_fixture_snapshot(source, snapshot)
        fixture_count = _validate_fixture_snapshot(snapshot)
        selection_fixture_count = _validate_selection_vectors(snapshot)
        changed = not _have_same_contents(snapshot, FIXTURE_DESTINATION)

        if changed:
            _write_source_metadata(snapshot, source_commit)
            if FIXTURE_DESTINATION.exists():
                shutil.rmtree(FIXTURE_DESTINATION)
            shutil.copytree(snapshot, FIXTURE_DESTINATION)

        _set_github_outputs(source_commit, fixture_count, selection_fixture_count, changed=changed)
        print(f"Checked FFE fixtures from DataDog/ffe-system-test-data@{source_commit}")
        print(f"Loaded {fixture_count} canonical fixture cases")
        print(f"Loaded {selection_fixture_count} canonical selection SDK cases")
        print(f"Fixture snapshot changed: {str(changed).lower()}")
        return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="main", help="Branch, tag, or commit from DataDog/ffe-system-test-data")
    arguments = parser.parse_args()
    update_fixtures(arguments.ref)


if __name__ == "__main__":
    main()
