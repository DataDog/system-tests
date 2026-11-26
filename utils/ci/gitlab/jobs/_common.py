"""Helpers shared by the scripts run by the jobs of the generated GitLab child pipeline.

Each script reads its inputs from the environment variables set on the GitLab job (see build_pipeline.py).
Variables that system-tests commands already understand (TEST_LIBRARY, SYSTEM_TESTS_WEBLOG, ...) are left in
the environment and reach build.sh/run.sh untouched. Everything else (static flags, values computed here, inputs
without an env var counterpart, like the weblog for build.sh) is passed as command line arguments.

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


# For the best-effort datadog-ci calls that only send metadata (see run()): without a timeout, a hung call blocks
# the job until its own timeout. A healthy call (one small API request plus Node startup) takes a few seconds.
# Same values as the dd_ci_retry --allow-failure calls in templates.yml.
DD_CI_TIMEOUT = 15
DD_CI_ATTEMPTS = 3
# after a failed attempt, wait RETRY_BACKOFF * <attempt number> seconds
RETRY_BACKOFF = 5
# SIGKILL a command that is still running this long after the SIGTERM of its timeout
KILL_AFTER = 10


def run(
    command: list[str],
    *,
    allow_failure: bool = False,
    check: bool = True,
    timeout: int | None = None,
    attempts: int = 1,
) -> int:
    """Run a command and return its return code.

    With a timeout (in seconds), each attempt is run through coreutils timeout, which also kills its children (e.g.
    the command run by dd-sts exchange): exit code 124 on timeout, 137 if it had to be killed. Up to attempts
    attempts are made, until one succeeds, with a short pause between them.

    If it fails: with allow_failure, only log a warning; otherwise, exit with its return code, unless check is
    False, in which case the caller handles the failure.
    """
    name = command[0]
    if timeout is not None:
        command = ["timeout", f"--kill-after={KILL_AFTER}s", f"{timeout}s", *command]
    returncode = 0
    for attempt in range(1, attempts + 1):
        log(f"$ {' '.join(command)}")
        returncode = subprocess.run(command, check=False).returncode
        if returncode == 0:
            break
        if attempt < attempts:
            log(f"WARNING: {name} failed with exit code {returncode} (attempt {attempt}/{attempts}), retrying")
            time.sleep(RETRY_BACKOFF * attempt)
    if returncode != 0:
        if allow_failure:
            log(f"WARNING: {name} failed with exit code {returncode}, ignored")
        elif check:
            sys.exit(returncode)
    return returncode


def tag_job(job_type: str) -> None:
    # job metadata for Datadog CI Visibility: the Datadog API being unavailable must not fail the job
    run(
        ["datadog-ci", "tag", "--level", "job", "--tags", f"system-tests.job_type:{job_type}"],
        allow_failure=True,
        timeout=DD_CI_TIMEOUT,
        attempts=DD_CI_ATTEMPTS,
    )


def traced(name: str, command: list[str], *, scenario: str | None = None, check: bool = True) -> int:
    """Run a command wrapped in a datadog-ci span, tagged with the library/weblog/scenario of the job.

    The command gets neither the DD_API_KEY of datadog-ci nor the secrets of the GitLab job: the test runner fails
    if it finds one in its environment (see utils/ci/without_ci_secrets.sh).

    Return its return code, see run() for check.
    """
    tags = [f"system-tests.library:{env('TEST_LIBRARY')}"]
    if weblog := os.environ.get("SYSTEM_TESTS_WEBLOG"):
        tags.append(f"system-tests.weblog:{weblog}")
    if scenario:
        tags.append(f"system-tests.scenario:{scenario}")

    tag_args = [arg for tag in tags for arg in ("--tags", tag)]
    return run(
        ["datadog-ci", "trace", "--name", name, *tag_args, "--", "utils/ci/without_ci_secrets.sh", *command],
        check=check,
    )


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
    # like tag_job: a metric that can't be sent must not fail the job
    run(
        ["datadog-ci", "measure", "--level", "job", "--measures", f"system-tests.total_duration:{elapsed}"],
        allow_failure=True,
        timeout=DD_CI_TIMEOUT,
        attempts=DD_CI_ATTEMPTS,
    )
