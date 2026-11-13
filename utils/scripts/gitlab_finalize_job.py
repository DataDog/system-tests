"""Finalize a Docker SSI, AWS SSI or K8s lib injection GitLab job.

Runs in the after_script of those jobs, in system-tests and in the repositories that launch them.
Each profile is an ordered list of steps. A failing step is reported and the next steps still run,
so log collection and printing are attempted even if another step fails.

To add a feature, write a step function and add it to the profiles that need it.

Uses only the standard library: the system-tests virtualenv does not exist when the job fails before
./build.sh. Generated pipelines of older system-tests commits call this script with --profile, so keep
that option backward compatible.
"""

# The wrapper falls back to the system python3, which may predate the annotation syntax used here.
from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import cache
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

SYSTEM_TESTS_DIR = Path(__file__).resolve().parents[2]

AWS_LOGS_BUCKET = "system-tests-aws-ssi-apm"
MAX_ARTIFACT_FILE_SIZE = 50 * 1024 * 1024
PUBLISH_ATTEMPTS = 3
PUBLISH_TIMEOUT_SECONDS = 30
PUBLISH_RETRY_DELAY_SECONDS = 5
# The raw log folder is uploaded before large files are removed. Two attempts of 60s, plus a
# full feature-parity retry, stay inside the runner's 5-minute after_script timeout.
S3_PUBLISH_ATTEMPTS = 2
S3_PUBLISH_TIMEOUT_SECONDS = 60
# Two JUnit attempts (65s at most), so an AWS job on system-tests main, which also publishes to S3 (125s at most)
# and feature parity (100s at most), still prints its logs inside the 5-minute after_script timeout.
JUNIT_PUBLISH_ATTEMPTS = 2


@dataclass
class Job:
    """What the steps know about the job being finalized."""

    profile: Profile
    env: Mapping[str, str]
    project_dir: Path
    system_tests_dir: Path
    aws_console_url: str = ""

    @property
    def scenario(self) -> str:
        return self.env.get(self.profile.scenario_variable, "logs").lower()

    @property
    def reports_dir(self) -> Path:
        return self.project_dir / "reports"

    @property
    def ci_environment(self) -> str:
        """Environment of the run (prod, dev...): each kind of generated job passes it in its own variable."""
        return self.env.get(self.profile.environment_variable) or self.env.get("CI_ENVIRONMENT") or "prod"

    @property
    def logs_pattern(self) -> str:
        return self.profile.logs_pattern.format(scenario=self.scenario)

    @property
    def log_folders(self) -> list[Path]:
        return sorted(folder for folder in self.system_tests_dir.glob(self.logs_pattern) if folder.is_dir())

    @property
    def is_system_tests_main(self) -> bool:
        return self.env.get("CI_PROJECT_NAME") == "system-tests" and self.env.get("CI_COMMIT_BRANCH") == "main"

    def datadog_env(self) -> dict[str, str]:
        return {
            "DATADOG_SITE": self.env.get("DATADOG_SITE", "datadoghq.com"),
            "DATADOG_API_KEY": read_secret("test_optimization", "dd_api_key"),
        }


Step = Callable[[Job], None]


def run(
    command: list[str],
    env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    timeout: float | None = None,
) -> None:
    subprocess.run(command, check=True, cwd=cwd, timeout=timeout, env=None if env is None else {**os.environ, **env})


def _publish_failure(command_name: str, error: subprocess.CalledProcessError | subprocess.TimeoutExpired) -> str:
    """Status only. CalledProcessError stringifies the whole argument list."""
    if isinstance(error, subprocess.TimeoutExpired):
        return f"{command_name} timed out after {error.timeout} seconds"
    return f"{command_name} exited with status {error.returncode}"


def run_publish(
    command: list[str],
    env: Mapping[str, str] | None = None,
    *,
    attempts: int = PUBLISH_ATTEMPTS,
    timeout: float = PUBLISH_TIMEOUT_SECONDS,
    ignore_failure: bool = False,
) -> bool:
    """Retry a publish command.

    Raise when every attempt fails. The S3 log upload sets ignore_failure so a remaining
    failure is logged and the after_script still exits 0.
    """
    failure = ""
    for attempt in range(1, attempts + 1):
        try:
            run(command, env=env, timeout=timeout)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as attempt_error:
            failure = _publish_failure(command[0], attempt_error)
            print(f"⚠️ {failure} (attempt {attempt}/{attempts})", flush=True)
            if attempt < attempts:
                time.sleep(PUBLISH_RETRY_DELAY_SECONDS)
            continue
        return True
    if ignore_failure:
        print(f"⚠️ {failure} after {attempts} attempts, ignored", flush=True)
        return False
    raise RuntimeError(f"{failure} after {attempts} attempts")


@cache
def read_secret(*path: str) -> str:
    result = subprocess.run(["read-system-tests-secret", *path], check=True, stdout=subprocess.PIPE, text=True)
    return result.stdout.strip()


def tag_official_workflow(job: Job) -> None:
    # job metadata for Datadog CI Visibility: the Datadog API being unavailable must not fail the job
    try:
        run(["datadog-ci", "tag", "--level", "job", "--tags", "ci.framework.name:system-tests"], env=job.datadog_env())
    except subprocess.CalledProcessError as error:
        print(f"⚠️ Could not tag the job, ignored: {error}", flush=True)


def delete_kind_clusters(_job: Job) -> None:
    run(["kind", "delete", "clusters", "--all"])


def upload_logs_to_s3(job: Job) -> None:
    aws_config = Path.home() / ".aws" / "config"
    aws_config.parent.mkdir(parents=True, exist_ok=True)
    aws_config.write_text(read_secret("apm-ecosystems-reliability-profile", "config") + "\n")

    for folder in job.log_folders:
        pipeline_id = job.env.get("CI_PIPELINE_ID", "datadog-local")
        prefix = f"{pipeline_id}/{folder.name}/{job.env['VM']}_{job.env['WEBLOG']}/"
        uploaded = run_publish(
            ["aws", "s3", "cp", str(folder), f"s3://{AWS_LOGS_BUCKET}/{prefix}", "--recursive", "--quiet"],
            env={"AWS_PROFILE": "apm-ecosystems-reliability-ci"},
            attempts=S3_PUBLISH_ATTEMPTS,
            timeout=S3_PUBLISH_TIMEOUT_SECONDS,
            ignore_failure=True,
        )
        if uploaded:
            job.aws_console_url = (
                f"https://s3.console.aws.amazon.com/s3/buckets/{AWS_LOGS_BUCKET}?region=us-east-1&prefix={prefix}"
            )


def delete_large_log_files(job: Job) -> None:
    for folder in job.log_folders:
        for file in sorted(folder.rglob("*")):
            if file.is_file() and not file.is_symlink() and file.stat().st_size > MAX_ARTIFACT_FILE_SIZE:
                print(f"Deleting large file ({file.stat().st_size // (1024 * 1024)}M): {file}")
                file.unlink()


def _sockets_and_fifos(directory: str, names: list[str]) -> set[str]:
    return {name for name in names if Path(directory, name).is_socket() or Path(directory, name).is_fifo()}


def collect_logs(job: Job) -> None:
    job.reports_dir.mkdir(parents=True, exist_ok=True)
    if not job.log_folders:
        raise FileNotFoundError(f"No {job.logs_pattern} folder in {job.system_tests_dir}")
    for folder in job.log_folders:
        shutil.copytree(
            folder, job.reports_dir / folder.name, symlinks=True, ignore=_sockets_and_fifos, dirs_exist_ok=True
        )


def publish_feature_parity(job: Job) -> None:
    if not job.is_system_tests_main:
        return
    url = read_secret("fpd", "fp_import_url")
    api_key = read_secret("fpd", "fp_api_key")
    for report in sorted(job.reports_dir.glob(f"logs*/{job.profile.feature_parity_pattern}")):
        print(f"Processing report: {report}")
        run_publish(
            [
                "curl",
                "-X",
                "POST",
                url,
                "--fail",
                "--include",
                "--header",
                "Content-Type: application/json",
                "--header",
                f"FP_API_KEY: {api_key}",
                "--data",
                f"@{report}",
            ]
        )


def upload_junit_reports(job: Job) -> None:
    if job.env.get("CI_JOB_STATUS") == "canceled":
        print("Job canceled; skipping Test Optimization upload of a partial report")
        return
    reports = sorted(job.reports_dir.glob("logs*/reportJunit.xml"))
    if not reports:
        print("No reports/logs*/reportJunit.xml found; skipping Test Optimization upload")
        return
    run_publish(
        [
            "datadog-ci",
            "junit",
            "upload",
            *[str(report) for report in reports],
            "--service",
            "system-tests",
            "--env",
            "ci",
            "--verbose",
            "--xpath-tag",
            "test.codeowners=/testcase/properties/property[@name='test.codeowners']",
        ],
        env={
            **job.datadog_env(),
            "DD_TAGS": f"test.configuration.ci_environment:{job.ci_environment}",
        },
        attempts=JUNIT_PUBLISH_ATTEMPTS,
    )


def print_logs(job: Job) -> None:
    run(
        ["bash", str(job.system_tests_dir / "utils" / "scripts" / "gitlab_print_logs.sh")],
        env={"SCENARIO_SUFIX": job.scenario, "AWS_CONSOLE_URL": job.aws_console_url},
        cwd=job.project_dir,
    )


@dataclass(frozen=True)
class Profile:
    scenario_variable: str
    environment_variable: str
    logs_pattern: str
    feature_parity_pattern: str
    steps: tuple[Step, ...]


PROFILES: dict[str, Profile] = {
    "docker": Profile(
        scenario_variable="SCENARIO",
        environment_variable="ONBOARDING_FILTER_ENV",
        logs_pattern="logs_{scenario}",
        feature_parity_pattern="feature_parity.json",
        steps=(tag_official_workflow, collect_logs, publish_feature_parity, upload_junit_reports, print_logs),
    ),
    "aws": Profile(
        scenario_variable="SCENARIO",
        environment_variable="ONBOARDING_FILTER_ENV",
        logs_pattern="logs_{scenario}",
        feature_parity_pattern="*_feature_parity.json",
        steps=(
            upload_logs_to_s3,
            delete_large_log_files,
            collect_logs,
            publish_feature_parity,
            upload_junit_reports,
            print_logs,
        ),
    ),
    "k8s": Profile(
        scenario_variable="K8S_SCENARIO",
        environment_variable="REPORT_ENVIRONMENT",
        logs_pattern="logs_*",
        feature_parity_pattern="feature_parity.json",
        steps=(
            tag_official_workflow,
            delete_kind_clusters,
            collect_logs,
            publish_feature_parity,
            upload_junit_reports,
            print_logs,
        ),
    ),
}


def finalize(job: Job) -> int:
    failed_steps: list[str] = []
    for step in job.profile.steps:
        try:
            step(job)
        except Exception as error:
            print(f"❌ Step {step.__name__} failed: {error}", flush=True)
            failed_steps.append(step.__name__)
    if failed_steps:
        print(f"❌ Failed steps: {', '.join(failed_steps)}")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Finalize a Docker SSI, AWS SSI or K8s lib injection GitLab job.")
    parser.add_argument("--profile", required=True, choices=sorted(PROFILES))
    args = parser.parse_args()

    job = Job(
        profile=PROFILES[args.profile],
        env=os.environ,
        project_dir=Path(os.environ.get("CI_PROJECT_DIR", Path.cwd())),
        system_tests_dir=SYSTEM_TESTS_DIR,
    )
    return finalize(job)


if __name__ == "__main__":
    sys.exit(main())
