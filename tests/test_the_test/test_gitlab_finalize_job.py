"""Tests for utils/scripts/gitlab_finalize_job.py and for the GitLab jobs that call it."""

import os
from pathlib import Path
import subprocess

import yaml

from utils import pytest, scenarios
from utils.scripts import gitlab_finalize_job as finalizer
from utils.scripts.ci_orchestrators.gitlab_exporter import build_ssi_gitlab_pipeline

BASE_JOBS_PROFILES = {
    ".base_docker_ssi_job": "docker",
    ".base_job_onboarding_system_tests": "aws",
    ".k8s_lib_injection_base": "k8s",
}


@pytest.fixture
def commands(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Record the commands run by the steps instead of running them."""
    recorded: list[list[str]] = []

    def run(command: list[str], env: dict[str, str] | None = None, cwd: Path | None = None) -> None:  # noqa: ARG001
        recorded.append(command)

    monkeypatch.setattr(finalizer, "run", run)
    monkeypatch.setattr(finalizer, "read_secret", lambda *path: "/".join(path))
    return recorded


def _job(profile: str, tmp_path: Path, **env: str) -> finalizer.Job:
    return finalizer.Job(
        profile=finalizer.PROFILES[profile],
        env=env,
        project_dir=tmp_path / "project",
        system_tests_dir=tmp_path / "system-tests",
    )


def _write(path: Path, content: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


@scenarios.test_the_test
def test_docker_profile_publishes_reports_on_system_tests_main(tmp_path: Path, commands: list[list[str]]):
    logs = tmp_path / "system-tests" / "logs_docker_ssi"
    _write(logs / "feature_parity.json", "{}")
    _write(logs / "reportJunit.xml", "<testsuites/>")
    job = _job("docker", tmp_path, SCENARIO="DOCKER_SSI", CI_PROJECT_NAME="system-tests", CI_COMMIT_BRANCH="main")

    assert finalizer.finalize(job) == 0

    reports = tmp_path / "project" / "reports" / "logs_docker_ssi"
    assert (reports / "reportJunit.xml").is_file()
    assert [command[:3] for command in commands] == [
        ["datadog-ci", "tag", "--level"],
        ["curl", "-X", "POST"],
        ["datadog-ci", "junit", "upload"],
        ["bash", str(tmp_path / "system-tests" / "utils" / "scripts" / "gitlab_print_logs.sh")],
    ]
    assert f"@{reports / 'feature_parity.json'}" in commands[1]


@scenarios.test_the_test
def test_feature_parity_is_only_published_on_system_tests_main(tmp_path: Path, commands: list[list[str]]):
    _write(tmp_path / "system-tests" / "logs_docker_ssi" / "feature_parity.json", "{}")
    job = _job("docker", tmp_path, SCENARIO="DOCKER_SSI", CI_PROJECT_NAME="dd-trace-java", CI_COMMIT_BRANCH="main")

    assert finalizer.finalize(job) == 0
    assert not [command for command in commands if command[0] == "curl"]


@scenarios.test_the_test
def test_aws_profile_uploads_to_s3_and_keeps_large_files_out_of_the_artifacts(
    tmp_path: Path, commands: list[list[str]], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    logs = tmp_path / "system-tests" / "logs_simple_installer_auto_injection"
    _write(logs / "vm_feature_parity.json", "{}")
    _write(logs / "feature_parity.json", "{}")
    with (logs / "large.log").open("wb") as large_file:
        large_file.truncate(finalizer.MAX_ARTIFACT_FILE_SIZE + 1)
    job = _job(
        "aws",
        tmp_path,
        SCENARIO="SIMPLE_INSTALLER_AUTO_INJECTION",
        VM="Ubuntu_22_amd64",
        WEBLOG="test-app-java",
        CI_PIPELINE_ID="42",
        CI_PROJECT_NAME="system-tests",
        CI_COMMIT_BRANCH="main",
    )

    assert finalizer.finalize(job) == 0

    prefix = "42/logs_simple_installer_auto_injection/Ubuntu_22_amd64_test-app-java/"
    assert commands[1][:5] == ["aws", "s3", "cp", str(logs), f"s3://system-tests-aws-ssi-apm/{prefix}"]
    assert job.aws_console_url.endswith(f"prefix={prefix}")
    assert (tmp_path / "home" / ".aws" / "config").read_text() == "apm-ecosystems-reliability-profile/config\n"
    reports = tmp_path / "project" / "reports" / "logs_simple_installer_auto_injection"
    assert not (reports / "large.log").exists()
    uploaded = [command[-1] for command in commands if command[0] == "curl"]
    assert uploaded == [f"@{reports / 'vm_feature_parity.json'}"]


@scenarios.test_the_test
def test_k8s_profile_deletes_clusters_and_collects_every_log_folder(tmp_path: Path, commands: list[list[str]]):
    _write(tmp_path / "system-tests" / "logs_k8s_lib_injection" / "tests.log")
    _write(tmp_path / "system-tests" / "logs_other" / "tests.log")
    job = _job("k8s", tmp_path, K8S_SCENARIO="K8S_LIB_INJECTION", CI_PROJECT_NAME="dd-trace-php")

    assert finalizer.finalize(job) == 0

    assert commands[1] == ["kind", "delete", "clusters", "--all"]
    reports = tmp_path / "project" / "reports"
    assert sorted(path.name for path in reports.iterdir()) == ["logs_k8s_lib_injection", "logs_other"]


@scenarios.test_the_test
def test_log_folders_with_sockets_are_collected(tmp_path: Path, commands: list[list[str]]):
    logs = tmp_path / "system-tests" / "logs_docker_ssi"
    _write(logs / "interfaces" / "library" / "00001.json", "{}")
    os.mkfifo(logs / "interfaces" / "agent.fifo")
    job = _job("docker", tmp_path, SCENARIO="DOCKER_SSI")

    assert finalizer.finalize(job) == 0

    reports = tmp_path / "project" / "reports" / "logs_docker_ssi" / "interfaces"
    assert (reports / "library" / "00001.json").is_file()
    assert not (reports / "agent.fifo").exists()
    assert commands[-1][0] == "bash"


@scenarios.test_the_test
def test_a_failing_step_does_not_stop_the_next_ones(
    tmp_path: Path, commands: list[list[str]], monkeypatch: pytest.MonkeyPatch
):
    def run(command: list[str], env: dict[str, str] | None = None, cwd: Path | None = None) -> None:  # noqa: ARG001
        if command[0] == "datadog-ci":
            raise subprocess.CalledProcessError(1, command)
        commands.append(command)

    monkeypatch.setattr(finalizer, "run", run)
    job = _job("docker", tmp_path, SCENARIO="DOCKER_SSI")

    assert finalizer.finalize(job) == 1

    assert [command[0] for command in commands] == ["bash"]


@scenarios.test_the_test
def test_logs_are_printed_even_without_log_folder(tmp_path: Path, commands: list[list[str]]):
    job = _job("docker", tmp_path, SCENARIO="DOCKER_SSI")

    assert finalizer.finalize(job) == 1

    assert commands[-1][0] == "bash"
    assert (tmp_path / "project" / "reports").is_dir()


@scenarios.test_the_test
def test_entry_point_runs_the_finalizer():
    result = subprocess.run(
        ["bash", "utils/scripts/gitlab_finalize_job.sh", "--help"], check=True, capture_output=True, text=True
    )
    assert "--profile {aws,docker,k8s}" in result.stdout


@scenarios.test_the_test
def test_base_jobs_call_the_finalizer_from_the_system_tests_checkout():
    pipeline = yaml.safe_load(Path(".gitlab/ssi_gitlab-ci.yml").read_text())

    for base_job, profile in BASE_JOBS_PROFILES.items():
        assert pipeline[base_job]["variables"]["SYSTEM_TESTS_DIR"] == "$CI_PROJECT_DIR"
        assert pipeline[base_job]["after_script"] == [
            f'bash "${{SYSTEM_TESTS_DIR}}/utils/scripts/gitlab_finalize_job.sh" --profile {profile}'
        ]


@pytest.mark.parametrize(
    ("project", "expected_dirs"),
    [
        ("system-tests", dict.fromkeys(BASE_JOBS_PROFILES, "$CI_PROJECT_DIR")),
        (
            "dd-trace-php",
            {
                ".base_docker_ssi_job": "/system-tests",
                ".base_job_onboarding_system_tests": "$CI_PROJECT_DIR/system-tests",
                ".k8s_lib_injection_base": "/system-tests",
            },
        ),
    ],
)
@scenarios.test_the_test
def test_generated_jobs_point_to_the_checkout_they_run_in(
    project: str, expected_dirs: dict[str, str], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("CI_PROJECT_NAME", project)
    for name in ("SYSTEM_TESTS_REF", "K8S_INJECTOR_IMG", "K8S_LIB_INIT_IMG", "K8S_WEBLOG_IMG"):
        monkeypatch.delenv(name, raising=False)
    matrix_data: dict[str, dict] = {
        "aws_ssi_scenario_defs": {"SIMPLE_INSTALLER_AUTO_INJECTION": {"test-app-php": ["Ubuntu_22_amd64"]}},
        "dockerssi_scenario_defs": {"DOCKER_SSI": {"php-app": [{"ubuntu:22.04": ["8.3"], "arch": "linux/amd64"}]}},
        "libinjection_scenario_defs": {"K8S_LIB_INJECTION": ["dd-lib-php-init-test-app"]},
    }

    pipeline = build_ssi_gitlab_pipeline("php", matrix_data, "dev")

    assert {job: pipeline[job]["variables"]["SYSTEM_TESTS_DIR"] for job in expected_dirs} == expected_dirs
