"""Finalize a Docker SSI, AWS SSI or K8s lib injection GitLab job.

Runs in the after_script of those jobs, in system-tests and in the repositories that launch them.
Each profile is an ordered list of steps. A failing step is reported and the next steps still run,
so the job is always tagged and its logs are always collected and printed.

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

SYSTEM_TESTS_DIR = Path(__file__).resolve().parents[2]

AWS_LOGS_BUCKET = "system-tests-aws-ssi-apm"
MAX_ARTIFACT_FILE_SIZE = 50 * 1024 * 1024


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


def run(command: list[str], env: Mapping[str, str] | None = None, cwd: Path | None = None) -> None:
    subprocess.run(command, check=True, cwd=cwd, env=None if env is None else {**os.environ, **env})


@cache
def read_secret(*path: str) -> str:
    result = subprocess.run(["read-system-tests-secret", *path], check=True, stdout=subprocess.PIPE, text=True)
    return result.stdout.strip()


def tag_official_workflow(job: Job) -> None:
    run(["datadog-ci", "tag", "--level", "job", "--tags", "ci.framework.name:system-tests"], env=job.datadog_env())


def delete_kind_clusters(_job: Job) -> None:
    run(["kind", "delete", "clusters", "--all"])


def upload_logs_to_s3(job: Job) -> None:
    aws_config = Path.home() / ".aws" / "config"
    aws_config.parent.mkdir(parents=True, exist_ok=True)
    aws_config.write_text(read_secret("apm-ecosystems-reliability-profile", "config") + "\n")

    for folder in job.log_folders:
        pipeline_id = job.env.get("CI_PIPELINE_ID", "datadog-local")
        prefix = f"{pipeline_id}/{folder.name}/{job.env['VM']}_{job.env['WEBLOG']}/"
        run(
            ["aws", "s3", "cp", str(folder), f"s3://{AWS_LOGS_BUCKET}/{prefix}", "--recursive", "--quiet"],
            env={"AWS_PROFILE": "apm-ecosystems-reliability-ci"},
        )
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
        run(
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
    reports = sorted(job.reports_dir.glob("logs*/reportJunit.xml"))
    if not reports:
        print("No reports/logs*/reportJunit.xml found; skipping Test Optimization upload")
        return
    run(
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
            "DD_TAGS": f"test.configuration.ci_environment:{job.env.get('CI_ENVIRONMENT', 'prod')}",
        },
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
    logs_pattern: str
    feature_parity_pattern: str
    steps: tuple[Step, ...]


PROFILES: dict[str, Profile] = {
    "docker": Profile(
        scenario_variable="SCENARIO",
        logs_pattern="logs_{scenario}",
        feature_parity_pattern="feature_parity.json",
        steps=(tag_official_workflow, collect_logs, publish_feature_parity, upload_junit_reports, print_logs),
    ),
    "aws": Profile(
        scenario_variable="SCENARIO",
        logs_pattern="logs_{scenario}",
        feature_parity_pattern="*_feature_parity.json",
        steps=(
            tag_official_workflow,
            upload_logs_to_s3,
            delete_large_log_files,
            collect_logs,
            publish_feature_parity,
            print_logs,
        ),
    ),
    "k8s": Profile(
        scenario_variable="K8S_SCENARIO",
        logs_pattern="logs_*",
        feature_parity_pattern="feature_parity.json",
        steps=(tag_official_workflow, delete_kind_clusters, collect_logs, publish_feature_parity, print_logs),
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
