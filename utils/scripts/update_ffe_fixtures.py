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
FIXTURE_COPY_DISALLOW_LIST = frozenset(
    {
        ".git",
        ".github",
        ".gitignore",
        "ci",
        "CONTRIBUTING.md",
        "LICENSE",
        "LICENSE-3rdparty.csv",
        "NOTICE",
        "README.md",
        "SOURCE.md",
    }
)
FIXTURE_REF_PATTERN = re.compile(r"[A-Za-z0-9._/-]+")


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
    for entry in sorted(source.iterdir()):
        if entry.name in FIXTURE_COPY_DISALLOW_LIST:
            continue
        _copy_entry(entry, snapshot / entry.name)


def _validate_fixture_snapshot(snapshot: Path) -> int:
    config_path = snapshot / "ufc-config.json"
    cases_directory = snapshot / "evaluation-cases"
    if not config_path.is_file() or not cases_directory.is_dir():
        msg = "FFE fixture repository does not contain the expected fixture layout"
        raise ValueError(msg)

    with config_path.open(encoding="utf-8") as config_file:
        json.load(config_file)

    case_files = sorted(cases_directory.glob("*.json"))
    if not case_files:
        msg = "No FFE JSON fixture files found"
        raise ValueError(msg)

    fixture_count = 0
    for case_file in case_files:
        with case_file.open(encoding="utf-8") as fixture_file:
            test_cases = json.load(fixture_file)
        if not isinstance(test_cases, list):
            msg = f"{case_file} must contain a JSON array of test cases"
            raise TypeError(msg)
        fixture_count += len(test_cases)

    if fixture_count == 0:
        msg = "No FFE fixture test cases found"
        raise ValueError(msg)

    return fixture_count


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
draft test PR only when the allowed fixture contents change.
""",
        encoding="utf-8",
    )


def _set_github_outputs(source_commit: str, fixture_count: int, *, changed: bool) -> None:
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with Path(github_output).open("a", encoding="utf-8") as output_file:
            output_file.write(f"source_commit={source_commit}\n")
            output_file.write(f"fixture_count={fixture_count}\n")
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
        changed = not _have_same_contents(snapshot, FIXTURE_DESTINATION)

        if changed:
            _write_source_metadata(snapshot, source_commit)
            if FIXTURE_DESTINATION.exists():
                shutil.rmtree(FIXTURE_DESTINATION)
            shutil.copytree(snapshot, FIXTURE_DESTINATION)

        _set_github_outputs(source_commit, fixture_count, changed=changed)
        print(f"Checked FFE fixtures from DataDog/ffe-system-test-data@{source_commit}")
        print(f"Loaded {fixture_count} canonical fixture cases")
        print(f"Fixture snapshot changed: {str(changed).lower()}")
        return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="main", help="Branch, tag, or commit from DataDog/ffe-system-test-data")
    arguments = parser.parse_args()
    update_fixtures(arguments.ref)


if __name__ == "__main__":
    main()
