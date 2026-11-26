"""Tests for the scripts run by the jobs of the generated GitLab child pipeline (utils/ci/gitlab/jobs/)."""

import shutil
import subprocess
import sys
import time
from pathlib import Path

from utils import pytest
from utils import scenarios
from utils.ci.gitlab.jobs import _common, build_weblog, push_to_test_optimization, run_parametric, run_scenario


def _trace(name: str, tags: list[str], *command: str) -> list[str]:
    tag_args = [arg for tag in tags for arg in ("--tags", tag)]
    return ["datadog-ci", "trace", "--name", name, *tag_args, "--", "utils/ci/without_ci_secrets.sh", *command]


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


@pytest.fixture
def run_calls(
    commands: list[list[str]],  # noqa: ARG001 - for its fake system-tests clone and environment
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[list[str], dict[str, object]]]:
    """Like commands, with the keyword arguments of each run() call."""
    recorded: list[tuple[list[str], dict[str, object]]] = []

    def record(command: list[str], **kwargs: object) -> int:
        recorded.append((command, kwargs))
        return 0

    monkeypatch.setattr(_common, "run", record)
    return recorded


@pytest.fixture
def subprocess_calls(monkeypatch: pytest.MonkeyPatch) -> tuple[list[list[str]], list[int], list[float]]:
    """Make the subprocesses started by run() return the exit codes appended to the 2nd list, record the commands
    in the 1st one, and the pauses between attempts in the 3rd one.
    """
    commands: list[list[str]] = []
    returncodes: list[int] = []
    sleeps: list[float] = []

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[bytes]:
        commands.append(command)
        return subprocess.CompletedProcess(command, returncodes.pop(0))

    monkeypatch.setattr(_common.subprocess, "run", fake_run)
    monkeypatch.setattr(_common.time, "sleep", sleeps.append)
    return commands, returncodes, sleeps


TIMEOUT_TAG = ["timeout", "--kill-after=10s", "15s", "datadog-ci", "tag"]


@scenarios.test_the_test
class Test_GitlabRunHelper:
    def test_command_without_timeout_is_run_once(
        self, subprocess_calls: tuple[list[list[str]], list[int], list[float]]
    ) -> None:
        commands, returncodes, sleeps = subprocess_calls
        returncodes.append(3)

        assert _common.run(["false"], check=False) == 3
        assert commands == [["false"]]
        assert sleeps == []

    def test_failed_attempt_is_retried(self, subprocess_calls: tuple[list[list[str]], list[int], list[float]]) -> None:
        commands, returncodes, sleeps = subprocess_calls
        returncodes.extend([124, 0])

        assert _common.run(["datadog-ci", "tag"], timeout=15, attempts=3) == 0
        assert commands == [TIMEOUT_TAG, TIMEOUT_TAG]
        assert sleeps == [5]

    def test_allowed_failure_after_all_attempts(
        self, subprocess_calls: tuple[list[list[str]], list[int], list[float]]
    ) -> None:
        commands, returncodes, sleeps = subprocess_calls
        returncodes.extend([124, 1, 137])

        assert _common.run(["datadog-ci", "tag"], allow_failure=True, timeout=15, attempts=3) == 137
        assert commands == [TIMEOUT_TAG] * 3
        assert sleeps == [5, 10]

    def test_failure_after_all_attempts_exits(
        self, subprocess_calls: tuple[list[list[str]], list[int], list[float]]
    ) -> None:
        _, returncodes, _ = subprocess_calls
        returncodes.extend([1, 124])

        with pytest.raises(SystemExit) as exc:
            _common.run(["datadog-ci", "tag"], timeout=15, attempts=2)
        assert exc.value.code == 124

    def test_hung_command_is_killed(self) -> None:
        """A real hung command: coreutils timeout stops it, and its children, with exit code 124."""
        if not shutil.which("timeout"):
            pytest.skip("coreutils timeout is not installed")
        start = time.monotonic()
        # the sleep is a child of sh, like datadog-ci is a child of dd-sts exchange
        assert _common.run(["sh", "-c", "sleep 30; true"], timeout=1, check=False) == 124
        assert time.monotonic() - start < 10

    def test_datadog_ci_metadata_calls_are_bounded(
        self, run_calls: list[tuple[list[str], dict[str, object]]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SYSTEM_TESTS_GENERATED_PIPELINE_START_TIME", "0")

        _common.tag_job("run")
        _common.emit_execution_time_metric()

        assert [command[:2] for command, _ in run_calls] == [["datadog-ci", "tag"], ["datadog-ci", "measure"]]
        for _, kwargs in run_calls:
            # best-effort, as before
            assert kwargs == {"allow_failure": True, "timeout": 15, "attempts": 3}

    def test_datadog_ci_trace_is_not_bounded(
        self, run_calls: list[tuple[list[str], dict[str, object]]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """datadog-ci trace wraps build.sh / run.sh, which legitimately run for minutes."""
        monkeypatch.setenv("TEST_LIBRARY", "python")

        _common.traced("run python DEFAULT", ["./run.sh", "DEFAULT"])

        assert run_calls == [
            (_trace("run python DEFAULT", ["system-tests.library:python"], "./run.sh", "DEFAULT"), {"check": True})
        ]

    def test_traced_command_does_not_get_ci_secrets(self) -> None:
        """The test runner fails in CI if it finds a secret in its environment (see utils/proxy/scrubber.py)"""
        ci_secrets = {
            "CI_JOB_TOKEN": "glcbt-0123456789",
            "CI_REGISTRY_PASSWORD": "0123456789",
            "CI_DEPENDENCY_PROXY_PASSWORD": "0123456789",
            "CI_RUNNER_SHORT_TOKEN": "t1_01234567",
            "DD_STS_OIDC_TOKEN": "eyJ0eXAiOiJKV1QiLCJhbGciOi",
            "DD_API_KEY": "0123456789abcdef0123456789abcdef",
            "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "eyJ0eXAiOiJKV1QiLCJhbGciOi",
            "ACTIONS_ID_TOKEN_REQUEST_URL": "https://token.actions.githubusercontent.com/x",
        }

        result = subprocess.run(
            ["utils/ci/without_ci_secrets.sh", "env"],
            env={"PATH": "/usr/bin:/bin", **ci_secrets},
            text=True,
            capture_output=True,
            check=True,
        )

        names = {line.split("=", 1)[0] for line in result.stdout.splitlines()}
        assert names.isdisjoint(ci_secrets)
        assert "PATH" in names

    def test_junit_upload_is_bounded(self, run_calls: list[tuple[list[str], dict[str, object]]]) -> None:
        Path("logs_default").mkdir()
        Path("logs_default/reportJunit.xml").write_text("<testsuites/>")

        push_to_test_optimization.main()

        assert run_calls[0] == (["dd-sts", "debug"], {"timeout": 15})
        command, kwargs = run_calls[1]
        assert command[5:8] == ["datadog-ci", "junit", "upload"]
        # not allowed to fail, as before
        assert kwargs == {"timeout": 90, "attempts": 2}


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
