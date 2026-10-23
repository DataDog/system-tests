"""Helpers shared by the scripts run by the jobs of the generated GitLab child pipeline.

Each script reads its inputs from the environment variables set on the GitLab job (see build_pipeline.py).
Variables that system-tests commands already understand (TEST_LIBRARY, WEBLOG_VARIANT, SYSTEM_TESTS_WEBLOG,
...) are left in the environment and reach build.sh/run.sh untouched. Everything else (static flags, values
computed here, inputs without an env var counterpart) is passed as command line arguments.

Scripts run from the system-tests clone (see .system_tests_base in templates.yml), started by run_job.py.
They must only use the standard library: they are imported without the system-tests framework.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


def log(message: str) -> None:
    sys.stdout.write(f"{message}\n")
    sys.stdout.flush()


def env(name: str) -> str:
    """Return a required environment variable, exit with an explicit error if missing."""
    value = os.environ.get(name, "")
    if not value:
        sys.exit(f"ERROR: environment variable {name} is required")
    return value


def project_dir() -> Path:
    """$CI_PROJECT_DIR, parent of the system-tests clone, where artifacts are collected."""
    return Path(env("CI_PROJECT_DIR"))


@contextmanager
def section(name: str, description: str, *, collapsed: bool = True) -> Iterator[None]:
    """Collapsible section in the GitLab job log."""
    log(f"section_start:{int(time.time())}:{name}[collapsed={str(collapsed).lower()}]\r\x1b[0K{description}")
    try:
        yield
    finally:
        log(f"section_end:{int(time.time())}:{name}\r\x1b[0K")


def run(command: list[str]) -> None:
    """Run a command, exit with its return code if it fails."""
    log(f"$ {' '.join(command)}")
    returncode = subprocess.run(command, check=False).returncode
    if returncode != 0:
        sys.exit(returncode)


def tag_job(job_type: str) -> None:
    run(["datadog-ci", "tag", "--level", "job", "--tags", f"system-tests.job_type:{job_type}"])


def traced(name: str, command: list[str], *, scenario: str | None = None) -> None:
    """Run a command wrapped in a datadog-ci span, tagged with the library/weblog/scenario of the job."""
    tags = [f"system-tests.library:{env('TEST_LIBRARY')}"]
    if weblog := os.environ.get("SYSTEM_TESTS_WEBLOG"):
        tags.append(f"system-tests.weblog:{weblog}")
    if scenario:
        tags.append(f"system-tests.scenario:{scenario}")

    tag_args = [arg for tag in tags for arg in ("--tags", tag)]
    run(["datadog-ci", "trace", "--name", name, *tag_args, "--", *command])


def copy_upstream_binaries() -> None:
    """Copy the binaries downloaded from upstream jobs into binaries/.

    SYSTEM_TESTS_BINARIES_ARTIFACT_PATH (relative to $CI_PROJECT_DIR) is only set on jobs that download
    upstream artifacts, nothing to do otherwise.
    """
    artifact_path = os.environ.get("SYSTEM_TESTS_BINARIES_ARTIFACT_PATH", "")
    if not artifact_path:
        return

    with section("copy_binaries", "Copying pre-built binaries into binaries/"):
        shutil.copytree(project_dir() / artifact_path, "binaries", symlinks=True, dirs_exist_ok=True)
        run(["ls", "-la", "binaries/"])


def emit_execution_time_metric() -> None:
    """Report the time elapsed since the start of the parent pipeline."""
    start_time = os.environ.get("SYSTEM_TESTS_GENERATED_PIPELINE_START_TIME", "")
    if not start_time.isdigit():
        log(
            "SYSTEM_TESTS_GENERATED_PIPELINE_START_TIME not set or not numeric "
            f"('{start_time}'), skipping metric emission"
        )
        return

    elapsed = int(time.time()) - int(start_time)
    run(["datadog-ci", "measure", "--level", "job", "--measures", f"system-tests.total_duration:{elapsed}"])
