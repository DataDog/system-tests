"""Dev binaries job (dev mode only): fetch the dev binaries of the agent and of one library, once for all its jobs.

Like the "Get dev artifacts" step of .github/workflows/compute-workflow-parameters.yml, it runs
utils/scripts/load-binary.sh for the agent, then for the library. Its artifacts are downloaded by the build, run
and parametric jobs of the library, which copy them into binaries/ (SYSTEM_TESTS_BINARIES_ARTIFACT_PATH).

Environment:
    TEST_LIBRARY: library to fetch the dev binaries of
    LIBRARY_TARGET_BRANCH, AGENT_TARGET_BRANCH: optional, read by load-binary.sh (main/master if not set)
    SYSTEM_TESTS_DEV_BINARIES_GITHUB_TOKEN: "true" to get a GitHub token for load-binary.sh (see get_github_token)

Every network call is bounded: each load-binary.sh call is killed after LOAD_TIMEOUT_SECONDS and retried, the
curl calls it makes get a connection and transfer timeout (CURLRC), so that a stalled transfer is retried by curl
itself instead of hanging until the job timeout, and its git clones are aborted if they stall (GIT_STALL_ENV).
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

from . import _common as ci

# relative to $CI_PROJECT_DIR, where artifacts are collected. Must match the artifacts of .system_tests_dev_binaries
# in child-pipeline.yml, and DEV_BINARIES_PATH in build_pipeline.py
ARTIFACT_PATH = "dev-binaries"

LOAD_ATTEMPTS = 3
LOAD_TIMEOUT_SECONDS = 600
RETRY_DELAY_SECONDS = 15

# read by curl through CURL_HOME. Per transfer: curl --retry retries a transfer that timed out. load-binary.sh retries
# 3 times (4 transfers, 5s apart): 4 x 120s + 15s fits in LOAD_TIMEOUT_SECONDS, so curl gets to retry before the kill
CURLRC = "connect-timeout = 30\nmax-time = 120\n"
CURL_ATTEMPTS = 4
CURL_RETRY_DELAY_SECONDS = 5
CURL_MAX_TIME_SECONDS = 120

# git clone (cpp_kong, ruby_lambda): aborted if slower than 1 KB/s for 60s
GIT_STALL_ENV = {"GIT_HTTP_LOW_SPEED_LIMIT": "1000", "GIT_HTTP_LOW_SPEED_TIME": "60"}

# credentials of the job, that load-binary.sh does not need
SECRET_VARIABLES = ("DDOCTOSTS_ID_TOKEN", "DD_STS_OIDC_TOKEN", "DD_API_KEY", "CI_JOB_TOKEN", "GITHUB_TOKEN")

# Existing policy (.github/chainguard/gitlab.github-access.read.sts.yaml): read-only, for any branch of
# DataDog/system-tests. The token is scoped to DataDog/system-tests, like the GITHUB_TOKEN of the GitHub workflow,
# which is enough to read public data of other repositories (e.g. the branches of DataDog/dd-trace-go) with the
# rate limit of an authenticated client.
GITHUB_TOKEN_SCOPE = "DataDog/system-tests"  # noqa: S105 (not a secret)
GITHUB_TOKEN_POLICY = "gitlab.github-access.read"  # noqa: S105 (not a secret)
GITHUB_TOKEN_ATTEMPTS = 3
GITHUB_TOKEN_TIMEOUT_SECONDS = 60


def run_with_timeout(command: list[str], *, timeout: float, env: dict[str, str] | None = None) -> int:
    """Run a command, kill it and all its children if it lasts more than timeout seconds.

    Return its return code, 124 (like timeout(1)) if it timed out.
    """
    ci.log(f"$ {' '.join(command)}")
    # in its own process group, to kill its children too (curl, docker, git...) if it times out
    process = subprocess.Popen(command, env=env, start_new_session=True)
    try:
        return process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        ci.log(f"ERROR: {command[0]} did not complete in {timeout}s, killed")
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        return 124


def get_github_token() -> str:
    """Best effort: a GitHub token from dd-octo-sts, or an empty string (load-binary.sh then calls GitHub
    unauthenticated).

    The job's OIDC token (DDOCTOSTS_ID_TOKEN) only matches the policy in pipelines of DataDog/system-tests.
    """
    command = ["dd-octo-sts", "token", "--scope", GITHUB_TOKEN_SCOPE, "--policy", GITHUB_TOKEN_POLICY]
    for attempt in range(1, GITHUB_TOKEN_ATTEMPTS + 1):
        try:
            # the token is captured, never logged
            result = subprocess.run(
                command, check=False, capture_output=True, text=True, timeout=GITHUB_TOKEN_TIMEOUT_SECONDS
            )
        except subprocess.TimeoutExpired:
            ci.log(f"WARNING: dd-octo-sts token timed out (attempt {attempt}/{GITHUB_TOKEN_ATTEMPTS})")
        except OSError as error:
            ci.log(f"WARNING: can't run dd-octo-sts: {error}")
            break
        else:
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            ci.log(
                f"WARNING: dd-octo-sts token failed with exit code {result.returncode} "
                f"(attempt {attempt}/{GITHUB_TOKEN_ATTEMPTS}): {result.stderr.strip()}"
            )
        if attempt < GITHUB_TOKEN_ATTEMPTS:
            time.sleep(attempt * 5)

    ci.log("WARNING: no GitHub token, calling GitHub unauthenticated (rate limited)")
    return ""


def revoke_github_token(token: str) -> None:
    try:
        subprocess.run(
            ["dd-octo-sts", "revoke", "-t", token],
            check=False,
            capture_output=True,
            timeout=GITHUB_TOKEN_TIMEOUT_SECONDS,
        )
    except (subprocess.TimeoutExpired, OSError) as error:
        ci.log(f"WARNING: can't revoke the GitHub token: {error}")


def load_binary(target: str, env: dict[str, str]) -> Path:
    """Run load-binary.sh for target, retried, into its own folder of the clone, and return this folder.

    The folder is emptied before each attempt, so that an attempt never sees the leftovers of the previous one
    (e.g. a partial git clone). It must be a direct child of the clone: load-binary.sh calls ../utils/scripts.
    """
    output = Path(f"dev-binaries-{target}")
    for attempt in range(1, LOAD_ATTEMPTS + 1):
        shutil.rmtree(output, ignore_errors=True)
        output.mkdir()
        returncode = run_with_timeout(
            ["./utils/scripts/load-binary.sh", target],
            timeout=LOAD_TIMEOUT_SECONDS,
            env={**env, "BINARIES_DIR": str(output)},
        )
        if returncode == 0:
            return output
        if attempt < LOAD_ATTEMPTS:
            ci.log(f"load-binary.sh {target} failed (attempt {attempt}/{LOAD_ATTEMPTS}), retrying")
            time.sleep(attempt * RETRY_DELAY_SECONDS)

    ci.log(f"ERROR: load-binary.sh {target} failed after {LOAD_ATTEMPTS} attempts")
    raise SystemExit(returncode)


def main() -> None:
    library = ci.env("TEST_LIBRARY")
    artifact = ci.project_dir() / ARTIFACT_PATH

    ci.tag_job("dev_binaries")

    curl_home = Path("dev-binaries-curl-home")
    curl_home.mkdir(exist_ok=True)
    (curl_home / ".curlrc").write_text(CURLRC, encoding="utf-8")
    env = {**os.environ, "CURL_HOME": str(curl_home.resolve()), **GIT_STALL_ENV}
    # GITHUB_TOKEN is never inherited: only set below, when this job asks for one
    for name in SECRET_VARIABLES:
        env.pop(name, None)

    token = ""
    if os.environ.get("SYSTEM_TESTS_DEV_BINARIES_GITHUB_TOKEN", "").lower() == "true":
        with ci.section("github_token", "Getting a GitHub token"):
            token = get_github_token()
        if token:
            env["GITHUB_TOKEN"] = token

    try:
        for target in ("agent", library):
            with ci.section(f"load_{target}", f"Loading the dev binaries of {target}", collapsed=False):
                output = load_binary(target, env)
                shutil.copytree(output, artifact, symlinks=True, dirs_exist_ok=True)
    finally:
        if token:
            revoke_github_token(token)

    ci.run(["ls", "-la", str(artifact)])


if __name__ == "__main__":
    main()
