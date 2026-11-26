"""The AWS AMI refresh tags its pipeline so Green CI skips that run only."""

import os
from pathlib import Path
import stat
import subprocess

import yaml

from utils import pytest, scenarios
from utils.scripts.ci_orchestrators.gitlab_exporter import build_ssi_gitlab_pipeline

EXCLUDE_JOB = "/.gitlab/exclude_ami_update_from_green_ci.yml"
SCRIPT = "utils/scripts/exclude_ami_update_from_green_ci.sh"


def _fake_executable(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def _run_script(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, ami_update: str | None
) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _fake_executable(
        bin_dir / "read-system-tests-secret",
        "#!/bin/bash\nprintf '%s' 'test-api-key'\n",
    )
    _fake_executable(
        bin_dir / "datadog-ci",
        '#!/bin/bash\nprintf \'%s\\n\' "$*" > "$CAPTURE"\nprintf \'%s\' "$DATADOG_API_KEY" > "$CAPTURE_KEY"\n',
    )
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    monkeypatch.setenv("CAPTURE", str(tmp_path / "datadog-ci-args"))
    monkeypatch.setenv("CAPTURE_KEY", str(tmp_path / "datadog-ci-key"))
    if ami_update is None:
        monkeypatch.delenv("AMI_UPDATE", raising=False)
    else:
        monkeypatch.setenv("AMI_UPDATE", ami_update)

    return subprocess.run(["bash", SCRIPT], check=False, capture_output=True, text=True)


@scenarios.test_the_test
def test_script_does_not_tag_a_pipeline_without_ami_update(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    result = _run_script(tmp_path, monkeypatch, ami_update=None)

    assert result.returncode == 0
    assert "stays in Green CI" in result.stdout
    assert not (tmp_path / "datadog-ci-args").exists()


@scenarios.test_the_test
def test_script_tags_the_pipeline_when_ami_update_is_true(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    result = _run_script(tmp_path, monkeypatch, ami_update="true")

    assert result.returncode == 0
    assert (tmp_path / "datadog-ci-args").read_text() == "tag --level pipeline --tags green_ci.excluded:true\n"
    assert (tmp_path / "datadog-ci-key").read_text() == "test-api-key"


@scenarios.test_the_test
def test_script_continues_when_the_datadog_call_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _fake_executable(bin_dir / "read-system-tests-secret", "#!/bin/bash\nprintf '%s' 'test-api-key'\n")
    _fake_executable(bin_dir / "datadog-ci", "#!/bin/bash\nexit 1\n")
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    monkeypatch.setenv("AMI_UPDATE", "true")

    result = subprocess.run(["bash", SCRIPT], check=False, capture_output=True, text=True)

    assert result.returncode == 0
    assert "AMI refresh continues" in result.stdout


@scenarios.test_the_test
def test_parent_and_child_pipelines_include_the_exclude_job(monkeypatch: pytest.MonkeyPatch):
    parent = yaml.safe_load(Path(".gitlab-ci.yml").read_text())
    job = yaml.safe_load(Path(EXCLUDE_JOB.lstrip("/")).read_text())["exclude_ami_update_from_green_ci"]
    monkeypatch.setenv("CI_PROJECT_NAME", "system-tests")
    for name in ("SYSTEM_TESTS_REF", "K8S_INJECTOR_IMG", "K8S_LIB_INIT_IMG", "K8S_WEBLOG_IMG"):
        monkeypatch.delenv(name, raising=False)
    matrix_data: dict[str, dict] = {
        "aws_ssi_scenario_defs": {"SIMPLE_INSTALLER_AUTO_INJECTION": {"test-app-php": ["Ubuntu_22_amd64"]}},
        "dockerssi_scenario_defs": {},
        "libinjection_scenario_defs": {},
    }

    child = build_ssi_gitlab_pipeline("php", matrix_data, "dev")

    assert {"local": EXCLUDE_JOB} in parent["include"]
    assert {"local": EXCLUDE_JOB} in child["include"]
    assert job["rules"] == [{"if": '$AMI_UPDATE == "true"'}]
    assert job["script"] == [f"bash {SCRIPT}"]
    assert job["stage"] == ".pre"
    assert job["before_script"] == []
    assert job["after_script"] == []
    assert job["artifacts"]["paths"] == []
    assert job["variables"]["KUBERNETES_CPU_REQUEST"] == "1"
