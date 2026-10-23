"""Tests for the scripts run by the jobs of the generated GitLab child pipeline (utils/ci/gitlab/jobs/)."""

import subprocess
import sys
from pathlib import Path

from utils import pytest
from utils import scenarios
from utils.ci.gitlab.jobs import _common, build_weblog, push_to_test_optimization, run_parametric, run_scenario


def _trace(name: str, tags: list[str], *command: str) -> list[str]:
    tag_args = [arg for tag in tags for arg in ("--tags", tag)]
    return ["datadog-ci", "trace", "--name", name, *tag_args, "--", *command]


TAG_RUN = ["datadog-ci", "tag", "--level", "job", "--tags", "system-tests.job_type:run"]


@pytest.fixture
def commands(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[list[str]]:
    """Record commands instead of running them, from a fake system-tests clone in $CI_PROJECT_DIR."""
    recorded: list[list[str]] = []
    monkeypatch.setattr(_common, "run", recorded.append)

    clone = tmp_path / "system-tests"
    (clone / "binaries").mkdir(parents=True)
    monkeypatch.chdir(clone)
    monkeypatch.setenv("CI_PROJECT_DIR", str(tmp_path))
    for name in (
        "SYSTEM_TESTS_BINARIES_ARTIFACT_PATH",
        "SYSTEM_TESTS_GENERATED_PIPELINE_START_TIME",
        "SYSTEM_TESTS_WEBLOG",
    ):
        monkeypatch.delenv(name, raising=False)
    return recorded


@scenarios.test_the_test
class Test_GitlabJobScripts:
    def test_run_scenario_with_upstream_binaries(
        self, commands: list[list[str]], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        (tmp_path / "upstream").mkdir()
        (tmp_path / "upstream" / "lib.tgz").write_text("lib")
        monkeypatch.setenv("TEST_LIBRARY", "golang")
        monkeypatch.setenv("SYSTEM_TESTS_WEBLOG", "envoy")
        monkeypatch.setenv("SYSTEM_TESTS_SCENARIO", "GO_PROXIES_DEFAULT")
        monkeypatch.setenv("SYSTEM_TESTS_WEBLOG_BUILD_REQUIRED", "false")
        monkeypatch.setenv("SYSTEM_TESTS_BINARIES_ARTIFACT_PATH", "upstream")
        monkeypatch.setenv("SYSTEM_TESTS_GENERATED_PIPELINE_START_TIME", "0")

        run_scenario.main()

        assert Path("binaries/lib.tgz").read_text() == "lib"
        assert commands[0] == ["ls", "-la", "binaries/"]
        assert commands[1] == TAG_RUN
        # weblog and library are passed through the environment, not on the command line
        assert commands[2] == _trace(
            "run golang GO_PROXIES_DEFAULT envoy",
            [
                "system-tests.library:golang",
                "system-tests.weblog:envoy",
                "system-tests.scenario:GO_PROXIES_DEFAULT",
            ],
            "./run.sh",
            "GO_PROXIES_DEFAULT",
        )
        assert commands[3][:5] == ["datadog-ci", "measure", "--level", "job", "--measures"]
        assert len(commands) == 4

    def test_run_scenario_loads_weblog_built_by_build_job(
        self, commands: list[list[str]], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        (tmp_path / "binaries").mkdir()
        (tmp_path / "binaries" / "python-flask-weblog.tar.zst").write_text("image")
        monkeypatch.setenv("TEST_LIBRARY", "python")
        monkeypatch.setenv("SYSTEM_TESTS_WEBLOG", "flask")
        monkeypatch.setenv("SYSTEM_TESTS_SCENARIO", "DEFAULT")
        monkeypatch.setenv("SYSTEM_TESTS_WEBLOG_BUILD_REQUIRED", "true")

        run_scenario.main()

        assert Path("binaries/python-flask-weblog.tar.zst").read_text() == "image"
        tags = ["system-tests.library:python", "system-tests.weblog:flask"]
        assert commands == [
            TAG_RUN,
            _trace("build python flask", tags, "./build.sh", "-i", "weblog"),
            _trace("run python DEFAULT flask", [*tags, "system-tests.scenario:DEFAULT"], "./run.sh", "DEFAULT"),
        ]

    def test_build_weblog(self, commands: list[list[str]], monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("TEST_LIBRARY", "python")
        monkeypatch.setenv("WEBLOG_VARIANT", "flask")
        monkeypatch.setenv("SYSTEM_TESTS_WEBLOG", "flask")
        Path("binaries/python-flask-weblog.tar.zst").write_text("image")

        build_weblog.main()

        assert commands == [
            ["datadog-ci", "tag", "--level", "job", "--tags", "system-tests.job_type:build"],
            _trace(
                "build python flask",
                ["system-tests.library:python", "system-tests.weblog:flask"],
                "./build.sh",
                "-i",
                "weblog",
                "--save-to-binaries",
            ),
        ]
        # moved to $CI_PROJECT_DIR, where artifacts are collected
        assert (tmp_path / "binaries" / "python-flask-weblog.tar.zst").read_text() == "image"
        assert not Path("binaries").exists()

    def test_run_parametric(self, commands: list[list[str]], monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_LIBRARY", "java")
        monkeypatch.setenv("SYSTEM_TESTS_PARAMETRIC_GROUP", "2")
        monkeypatch.setenv("SYSTEM_TESTS_PARAMETRIC_JOB_COUNT", "6")
        monkeypatch.setenv("SYSTEM_TESTS_PARAMETRIC_WORKERS", "4")

        run_parametric.main()

        assert commands == [
            TAG_RUN,
            _trace(
                "run java PARAMETRIC 2",
                ["system-tests.library:java", "system-tests.scenario:PARAMETRIC"],
                "./run.sh",
                "PARAMETRIC",
                "--maxprocesses=4",
                "--splits=6",
                "--group=2",
            ),
        ]

    def test_missing_input_fails(self, commands: list[list[str]], monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SYSTEM_TESTS_SCENARIO", raising=False)
        monkeypatch.setenv("TEST_LIBRARY", "python")
        monkeypatch.setenv("SYSTEM_TESTS_WEBLOG", "flask")

        with pytest.raises(SystemExit, match="SYSTEM_TESTS_SCENARIO"):
            run_scenario.main()
        assert commands == []

    def test_push_to_test_optimization(
        self, commands: list[list[str]], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        Path("logs_default").mkdir()
        Path("logs_default/reportJunit.xml").write_text("<testsuites/>")
        monkeypatch.delenv("DD_API_KEY", raising=False)

        push_to_test_optimization.main()

        assert commands[0] == ["dd-sts", "debug"]
        # the API key is passed by dd-sts to the upload command only
        assert commands[1][:9] == [
            *("dd-sts", "exchange", "--policy", "system-tests-gitlab", "--"),
            *("datadog-ci", "junit", "upload", "logs_default/reportJunit.xml"),
        ]
        assert "DD_API_KEY" not in _common.os.environ
        assert not list(tmp_path.glob("*.env"))

    def test_push_to_test_optimization_without_report(self, commands: list[list[str]]) -> None:
        push_to_test_optimization.main()

        assert commands == []

    def test_job_scripts_do_not_load_the_framework(self) -> None:
        """run_job.py imports the job scripts without utils/__init__.py: they must only use the standard library."""
        code = (
            "import sys; sys.path.insert(0, 'utils/ci/gitlab'); import run_job; "
            "[__import__(f'jobs.{job}') for job in run_job.JOBS]; "
            "assert not [m for m in sys.modules if m.split('.')[0] == 'utils'], 'utils was imported'"
        )
        # -I: ignore PYTHONPATH, so that the system-tests clone is not importable
        subprocess.run([sys.executable, "-I", "-c", code], check=True)

    def test_run_job_rejects_unknown_job(self) -> None:
        result = subprocess.run(
            [sys.executable, "utils/ci/gitlab/run_job.py", "unknown"], check=False, capture_output=True, text=True
        )
        assert result.returncode != 0
        assert "usage: run_job.py" in result.stderr
