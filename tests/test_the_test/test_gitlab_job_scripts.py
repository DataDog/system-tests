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


def _image_list(scenario: str, library: str, weblog: str) -> list[str]:
    return [
        "env",
        "PYTHONPATH=.",
        "python",
        "utils/scripts/get-image-list.py",
        scenario,
        f"--library={library}",
        f"--weblog={weblog}",
        "--output=compose.yaml",
    ]


@pytest.fixture
def commands(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[list[str]]:
    """Record commands instead of running them, from a fake system-tests clone in $CI_PROJECT_DIR."""
    recorded: list[list[str]] = []

    def record(command: list[str], **_: object) -> int:
        recorded.append(command)
        return 0

    monkeypatch.setattr(_common, "run", record)

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
        monkeypatch.setenv("SYSTEM_TESTS_SCENARIOS", "GO_PROXIES_DEFAULT")
        monkeypatch.setenv("SYSTEM_TESTS_WEBLOG_BUILD_REQUIRED", "false")
        monkeypatch.setenv("SYSTEM_TESTS_BINARIES_ARTIFACT_PATH", "upstream")
        monkeypatch.setenv("SYSTEM_TESTS_GENERATED_PIPELINE_START_TIME", "0")

        run_scenario.main()

        assert Path("binaries/lib.tgz").read_text() == "lib"
        assert commands[0] == ["ls", "-la", "binaries/"]
        assert commands[1] == TAG_RUN
        assert commands[2] == _image_list("GO_PROXIES_DEFAULT", "golang", "envoy")
        # weblog and library are passed through the environment, not on the command line
        assert commands[3] == _trace(
            "run golang GO_PROXIES_DEFAULT envoy",
            [
                "system-tests.library:golang",
                "system-tests.weblog:envoy",
                "system-tests.scenario:GO_PROXIES_DEFAULT",
            ],
            "./run.sh",
            "GO_PROXIES_DEFAULT",
        )
        assert commands[4][:5] == ["datadog-ci", "measure", "--level", "job", "--measures"]
        assert len(commands) == 5

    def test_run_scenario_loads_weblog_built_by_build_job(
        self, commands: list[list[str]], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        (tmp_path / "binaries").mkdir()
        (tmp_path / "binaries" / "python-flask-weblog.tar.zst").write_text("image")
        monkeypatch.setenv("TEST_LIBRARY", "python")
        monkeypatch.setenv("SYSTEM_TESTS_WEBLOG", "flask")
        monkeypatch.setenv("SYSTEM_TESTS_SCENARIOS", "DEFAULT")
        monkeypatch.setenv("SYSTEM_TESTS_WEBLOG_BUILD_REQUIRED", "true")

        run_scenario.main()

        assert Path("binaries/python-flask-weblog.tar.zst").read_text() == "image"
        tags = ["system-tests.library:python", "system-tests.weblog:flask"]
        assert commands == [
            TAG_RUN,
            _trace("build python flask", tags, "./build.sh", "-i", "weblog", "-w", "flask"),
            _image_list("DEFAULT", "python", "flask"),
            _trace("run python DEFAULT flask", [*tags, "system-tests.scenario:DEFAULT"], "./run.sh", "DEFAULT"),
        ]

    def test_run_scenario_builds_local_weblog(
        self, commands: list[list[str]], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """build_mode: local, no build job: upstream binaries are copied, then build.sh builds the image."""
        (tmp_path / "upstream").mkdir()
        (tmp_path / "upstream" / "nodejs-load-from-npm").write_text("dd-trace")
        monkeypatch.setenv("TEST_LIBRARY", "nodejs")
        monkeypatch.setenv("SYSTEM_TESTS_WEBLOG", "express4")
        monkeypatch.setenv("SYSTEM_TESTS_SCENARIOS", "DEFAULT")
        monkeypatch.setenv("SYSTEM_TESTS_WEBLOG_BUILD_REQUIRED", "true")
        monkeypatch.setenv("SYSTEM_TESTS_BINARIES_ARTIFACT_PATH", "upstream")

        run_scenario.main()

        assert Path("binaries/nodejs-load-from-npm").read_text() == "dd-trace"
        tags = ["system-tests.library:nodejs", "system-tests.weblog:express4"]
        assert commands == [
            ["ls", "-la", "binaries/"],
            TAG_RUN,
            _trace("build nodejs express4", tags, "./build.sh", "-i", "weblog", "-w", "express4"),
            _image_list("DEFAULT", "nodejs", "express4"),
            _trace("run nodejs DEFAULT express4", [*tags, "system-tests.scenario:DEFAULT"], "./run.sh", "DEFAULT"),
        ]

    def test_run_scenario_pulls_images_before_running(
        self, commands: list[list[str]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Like the GitHub workflow: the images listed by get-image-list.py are pulled before run.sh."""

        def record(command: list[str], **_: object) -> int:
            commands.append(command)
            if "utils/scripts/get-image-list.py" in command:
                Path("compose.yaml").write_text("services:\n  agent:\n    image: datadog/agent:latest\n")
            return 0

        monkeypatch.setattr(_common, "run", record)
        monkeypatch.setenv("TEST_LIBRARY", "python")
        monkeypatch.setenv("SYSTEM_TESTS_WEBLOG", "flask")
        monkeypatch.setenv("SYSTEM_TESTS_SCENARIOS", "DEFAULT")
        monkeypatch.setenv("SYSTEM_TESTS_WEBLOG_BUILD_REQUIRED", "false")

        run_scenario.main()

        assert commands[:3] == [
            TAG_RUN,
            _image_list("DEFAULT", "python", "flask"),
            [".github/actions/pull_images/main.sh"],
        ]

    def test_run_scenario_runs_several_scenarios(
        self, commands: list[list[str]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Grouped scenarios: the weblog is built once, then each scenario is run, one after the other."""
        monkeypatch.setenv("TEST_LIBRARY", "python")
        monkeypatch.setenv("SYSTEM_TESTS_WEBLOG", "flask")
        monkeypatch.setenv("SYSTEM_TESTS_SCENARIOS", "DEFAULT,SAMPLING")
        monkeypatch.setenv("SYSTEM_TESTS_WEBLOG_BUILD_REQUIRED", "true")

        run_scenario.main()

        tags = ["system-tests.library:python", "system-tests.weblog:flask"]
        assert commands == [
            TAG_RUN,
            _trace("build python flask", tags, "./build.sh", "-i", "weblog", "-w", "flask"),
            _image_list("DEFAULT", "python", "flask"),
            _trace("run python DEFAULT flask", [*tags, "system-tests.scenario:DEFAULT"], "./run.sh", "DEFAULT"),
            _image_list("SAMPLING", "python", "flask"),
            _trace("run python SAMPLING flask", [*tags, "system-tests.scenario:SAMPLING"], "./run.sh", "SAMPLING"),
        ]

    def test_run_scenario_runs_next_scenarios_after_a_failure(
        self, commands: list[list[str]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Like the GitHub workflow: a failing scenario doesn't prevent the next ones from running."""

        def record(command: list[str], **_: object) -> int:
            commands.append(command)
            if command[-2:] == ["./run.sh", "DEFAULT"]:
                return 3
            if "utils/scripts/get-image-list.py" in command and "SAMPLING" in command:
                return 4
            return 0

        monkeypatch.setattr(_common, "run", record)
        monkeypatch.setenv("TEST_LIBRARY", "python")
        monkeypatch.setenv("SYSTEM_TESTS_WEBLOG", "flask")
        monkeypatch.setenv("SYSTEM_TESTS_SCENARIOS", "DEFAULT,SAMPLING,IPV6")
        monkeypatch.setenv("SYSTEM_TESTS_WEBLOG_BUILD_REQUIRED", "false")

        with pytest.raises(SystemExit) as exc:
            run_scenario.main()

        # exit code of the first failure
        assert exc.value.code == 3
        run_commands = [command[-1] for command in commands if command[-2:-1] == ["./run.sh"]]
        # images of SAMPLING could not be listed: it is not run, but IPV6 is
        assert run_commands == ["DEFAULT", "IPV6"]

    def test_build_weblog(self, commands: list[list[str]], monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("TEST_LIBRARY", "python")
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
                "-w",
                "flask",
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
        monkeypatch.delenv("SYSTEM_TESTS_SCENARIOS", raising=False)
        monkeypatch.setenv("TEST_LIBRARY", "python")
        monkeypatch.setenv("SYSTEM_TESTS_WEBLOG", "flask")

        with pytest.raises(SystemExit, match="SYSTEM_TESTS_SCENARIOS"):
            run_scenario.main()
        assert commands == []

    @pytest.mark.parametrize("value", [",", " , "])
    def test_empty_scenario_list_fails(
        self, commands: list[list[str]], monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        monkeypatch.setenv("SYSTEM_TESTS_SCENARIOS", value)
        monkeypatch.setenv("TEST_LIBRARY", "python")
        monkeypatch.setenv("SYSTEM_TESTS_WEBLOG", "flask")

        with pytest.raises(SystemExit, match="SYSTEM_TESTS_SCENARIOS does not list any scenario"):
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
