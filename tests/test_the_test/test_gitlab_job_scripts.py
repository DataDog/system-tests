"""Tests for the scripts run by the jobs of the generated GitLab child pipeline (utils/ci/gitlab/jobs/)."""

import shutil
import subprocess
import sys
import time
from pathlib import Path

from utils import pytest
from utils import scenarios
from utils.ci.gitlab.jobs import (
    _common,
    build_weblog,
    load_dev_binaries,
    push_to_test_optimization,
    run_parametric,
    run_scenario,
)


def _trace(name: str, tags: list[str], *command: str) -> list[str]:
    tag_args = [arg for tag in tags for arg in ("--tags", tag)]
    return ["datadog-ci", "trace", "--name", name, *tag_args, "--", *command]


# before any monkeypatching
REAL_RUN_WITH_TIMEOUT = load_dev_binaries.run_with_timeout
REAL_POPEN = subprocess.Popen

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


@pytest.fixture
def dev_binaries(
    commands: list[list[str]],  # noqa: ARG001 (fake clone and recorded commands)
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[list[tuple[list[str], dict[str, str]]], list[list[str]]]:
    """Fake load-binary.sh (each call writes <target>-binary in BINARIES_DIR) and dd-octo-sts calls.

    Return the load-binary.sh calls, with their environment, and the dd-octo-sts calls.
    """
    loads: list[tuple[list[str], dict[str, str]]] = []
    octo_sts: list[list[str]] = []

    def fake_load(command: list[str], *, timeout: float, env: dict[str, str]) -> int:
        assert timeout == load_dev_binaries.LOAD_TIMEOUT_SECONDS
        loads.append((command, env))
        # each attempt starts from an empty folder, a direct child of the clone (load-binary.sh calls ../utils)
        output = Path(env["BINARIES_DIR"])
        assert output.parent == Path()
        assert not list(output.iterdir())
        (output / f"{command[-1]}-binary").write_text(command[-1])
        return 0

    class _Result:
        def __init__(self, returncode: int, stdout: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = ""

    def fake_octo_sts(command: list[str], **kwargs: object) -> _Result:
        assert command[0] == "dd-octo-sts"
        assert kwargs["timeout"] == load_dev_binaries.GITHUB_TOKEN_TIMEOUT_SECONDS
        octo_sts.append(command)
        return _Result(0, "ghs_token\n")

    monkeypatch.setattr(load_dev_binaries, "run_with_timeout", fake_load)
    monkeypatch.setattr(load_dev_binaries.subprocess, "run", fake_octo_sts)
    monkeypatch.setattr(load_dev_binaries.time, "sleep", lambda _: None)
    monkeypatch.setenv("TEST_LIBRARY", "python")
    monkeypatch.setenv("GITHUB_TOKEN", "inherited")
    for name in ("SYSTEM_TESTS_DEV_BINARIES_GITHUB_TOKEN", "LIBRARY_TARGET_BRANCH", "AGENT_TARGET_BRANCH"):
        monkeypatch.delenv(name, raising=False)
    return loads, octo_sts


@scenarios.test_the_test
class Test_GitlabLoadDevBinaries:
    def test_loads_agent_then_library(
        self,
        commands: list[list[str]],
        dev_binaries: tuple[list[tuple[list[str], dict[str, str]]], list[list[str]]],
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        loads, octo_sts = dev_binaries
        monkeypatch.setenv("LIBRARY_TARGET_BRANCH", "my-branch")

        load_dev_binaries.main()

        assert [command for command, _ in loads] == [
            ["./utils/scripts/load-binary.sh", "agent"],
            ["./utils/scripts/load-binary.sh", "python"],
        ]
        for _, env in loads:
            # target branches reach load-binary.sh through the environment
            assert env["LIBRARY_TARGET_BRANCH"] == "my-branch"
            # curl calls get timeouts
            assert "max-time" in (Path(env["CURL_HOME"]) / ".curlrc").read_text()
            # no token unless asked for
            assert "GITHUB_TOKEN" not in env
        assert octo_sts == []
        # both are collected in the artifact, in $CI_PROJECT_DIR
        artifact = tmp_path / load_dev_binaries.ARTIFACT_PATH
        assert sorted(path.name for path in artifact.iterdir()) == ["agent-binary", "python-binary"]
        assert commands == [
            ["datadog-ci", "tag", "--level", "job", "--tags", "system-tests.job_type:dev_binaries"],
            ["ls", "-la", str(artifact)],
        ]

    @pytest.mark.usefixtures("dev_binaries")
    def test_retries_failed_loads(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        fake_load = load_dev_binaries.run_with_timeout
        attempts: list[str] = []

        def flaky_load(command: list[str], *, timeout: float, env: dict[str, str]) -> int:
            fake_load(command, timeout=timeout, env=env)
            attempts.append(command[-1])
            # a timeout (124) on the first attempt for the library, after having written a partial result
            return 124 if attempts.count("python") == 1 and command[-1] == "python" else 0

        monkeypatch.setattr(load_dev_binaries, "run_with_timeout", flaky_load)

        load_dev_binaries.main()

        assert attempts == ["agent", "python", "python"]
        assert sorted(path.name for path in (tmp_path / load_dev_binaries.ARTIFACT_PATH).iterdir()) == [
            "agent-binary",
            "python-binary",
        ]

    @pytest.mark.usefixtures("dev_binaries")
    def test_fails_after_all_attempts(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        attempts: list[list[str]] = []

        def failing_load(command: list[str], **_: object) -> int:
            attempts.append(command)
            return 3

        monkeypatch.setattr(load_dev_binaries, "run_with_timeout", failing_load)

        with pytest.raises(SystemExit) as exc:
            load_dev_binaries.main()

        assert exc.value.code == 3
        # the library is not loaded once the agent failed
        assert attempts == [["./utils/scripts/load-binary.sh", "agent"]] * load_dev_binaries.LOAD_ATTEMPTS
        assert not (tmp_path / load_dev_binaries.ARTIFACT_PATH).exists()

    def test_github_token(
        self,
        dev_binaries: tuple[list[tuple[list[str], dict[str, str]]], list[list[str]]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        loads, octo_sts = dev_binaries
        monkeypatch.setenv("SYSTEM_TESTS_DEV_BINARIES_GITHUB_TOKEN", "true")

        load_dev_binaries.main()

        assert [env["GITHUB_TOKEN"] for _, env in loads] == ["ghs_token", "ghs_token"]
        assert octo_sts == [
            ["dd-octo-sts", "token", "--scope", "DataDog/system-tests", "--policy", "gitlab.github-access.read"],
            ["dd-octo-sts", "revoke", "-t", "ghs_token"],
        ]

    @pytest.mark.parametrize("failure", ["exit_code", "timeout"])
    def test_github_token_is_best_effort(
        self,
        dev_binaries: tuple[list[tuple[list[str], dict[str, str]]], list[list[str]]],
        monkeypatch: pytest.MonkeyPatch,
        failure: str,
    ) -> None:
        """Without a token (e.g. pipelines of another project), load-binary.sh calls GitHub unauthenticated."""
        loads, _ = dev_binaries
        token_calls: list[list[str]] = []

        def failing_octo_sts(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            token_calls.append(command)
            if failure == "timeout":
                raise subprocess.TimeoutExpired(command, 60)
            return subprocess.CompletedProcess(command, 1, "", "no policy matched")

        monkeypatch.setattr(load_dev_binaries.subprocess, "run", failing_octo_sts)
        monkeypatch.setenv("SYSTEM_TESTS_DEV_BINARIES_GITHUB_TOKEN", "true")

        load_dev_binaries.main()

        assert len(token_calls) == load_dev_binaries.GITHUB_TOKEN_ATTEMPTS
        assert all("GITHUB_TOKEN" not in env for _, env in loads)
        assert len(loads) == 2

    def test_github_token_is_revoked_when_loading_fails(
        self,
        dev_binaries: tuple[list[tuple[list[str], dict[str, str]]], list[list[str]]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _, octo_sts = dev_binaries
        monkeypatch.setattr(load_dev_binaries, "run_with_timeout", lambda *_, **__: 1)
        monkeypatch.setenv("SYSTEM_TESTS_DEV_BINARIES_GITHUB_TOKEN", "true")

        with pytest.raises(SystemExit):
            load_dev_binaries.main()

        assert octo_sts[-1] == ["dd-octo-sts", "revoke", "-t", "ghs_token"]

    @pytest.mark.parametrize("load_returncode", [0, 1])
    @pytest.mark.usefixtures("dev_binaries")
    def test_github_token_is_never_logged(
        self,
        commands: list[list[str]],
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        load_returncode: int,
    ) -> None:
        """Through the real run_with_timeout (it logs the commands), with a fake load-binary.sh."""
        monkeypatch.setattr(load_dev_binaries, "run_with_timeout", REAL_RUN_WITH_TIMEOUT)
        # load-binary.sh replaced by a command checking that it gets the token
        script = f'[ "$GITHUB_TOKEN" = ghs_token ] || exit 99; exit {load_returncode}'
        monkeypatch.setattr(
            load_dev_binaries.subprocess, "Popen", lambda _, **kwargs: REAL_POPEN(["sh", "-c", script], **kwargs)
        )
        monkeypatch.setenv("SYSTEM_TESTS_DEV_BINARIES_GITHUB_TOKEN", "true")

        if load_returncode:
            with pytest.raises(SystemExit) as exc:
                load_dev_binaries.main()
            assert exc.value.code == load_returncode
        else:
            load_dev_binaries.main()
        output = capsys.readouterr()

        assert "load-binary.sh" in output.out
        assert "ghs_token" not in output.out + output.err
        assert not [command for command in commands if "ghs_token" in " ".join(command)]

    def test_job_credentials_do_not_reach_load_binary(
        self,
        dev_binaries: tuple[list[tuple[list[str], dict[str, str]]], list[list[str]]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        loads, _ = dev_binaries
        for name in load_dev_binaries.SECRET_VARIABLES:
            monkeypatch.setenv(name, "secret")

        load_dev_binaries.main()

        for _, env in loads:
            assert not [name for name in load_dev_binaries.SECRET_VARIABLES if name in env]
            assert "secret" not in env.values()
            # git clones (cpp_kong, ruby_lambda) are aborted if they stall
            assert env["GIT_HTTP_LOW_SPEED_LIMIT"] == "1000"
            assert env["GIT_HTTP_LOW_SPEED_TIME"] == "60"

    def test_curl_retries_fit_in_the_load_timeout(self) -> None:
        """Curl gets to retry a stalled transfer before load-binary.sh is killed."""
        assert f"max-time = {load_dev_binaries.CURL_MAX_TIME_SECONDS}\n" in load_dev_binaries.CURLRC
        curl_time = (
            load_dev_binaries.CURL_ATTEMPTS * load_dev_binaries.CURL_MAX_TIME_SECONDS
            + (load_dev_binaries.CURL_ATTEMPTS - 1) * load_dev_binaries.CURL_RETRY_DELAY_SECONDS
        )
        assert curl_time < load_dev_binaries.LOAD_TIMEOUT_SECONDS
        # what load-binary.sh passes to curl
        script = Path("utils/scripts/load-binary.sh").read_text()
        assert f"--retry {load_dev_binaries.CURL_ATTEMPTS - 1} " in script
        assert f"--retry-delay {load_dev_binaries.CURL_RETRY_DELAY_SECONDS} " in script

    @pytest.mark.parametrize(
        ("target", "expected"),
        [
            ("agent", {"agent-image": "datadog/agent-dev:master-py3\n"}),
            ("python", {"python-load-from-s3": "main\n"}),
        ],
    )
    def test_real_load_binary_offline(
        self, commands: list[list[str]], tmp_path: Path, target: str, expected: dict[str, str]
    ) -> None:
        """The real load-binary.sh, run like the job does: from the clone, with a relative BINARIES_DIR.

        curl, docker and git fail: the agent and python dev binaries need no network.
        """
        assert commands == []
        scripts = Path("utils/scripts")  # in the fake clone, the cwd (see the commands fixture)
        scripts.mkdir(parents=True)
        repo_scripts = Path(load_dev_binaries.__file__).parents[4] / "utils" / "scripts"
        for name in ("load-binary.sh", "docker_base_image.sh"):
            shutil.copy2(repo_scripts / name, scripts / name)
        stubs = tmp_path / "stubs"
        stubs.mkdir()
        for tool in ("curl", "docker", "git"):
            (stubs / tool).write_text(f"#!/bin/sh\necho 'unexpected {tool} call' >&2\nexit 97\n")
            (stubs / tool).chmod(0o755)
        env = {"PATH": f"{stubs}:/usr/bin:/bin", "HOME": str(tmp_path)}

        output = load_dev_binaries.load_binary(target, env)

        assert not output.is_absolute()
        assert {path.name: path.read_text() for path in output.iterdir()} == expected
        # load-binary.sh calls ../utils/scripts from BINARIES_DIR (e.g. docker_base_image.sh for dotnet and php)
        assert (output / ".." / "utils" / "scripts" / "docker_base_image.sh").is_file()

    def test_run_with_timeout_kills_the_process_tree(self) -> None:
        """A hanging command is killed with its children, instead of running until the job timeout."""
        start = time.monotonic()
        returncode = load_dev_binaries.run_with_timeout(["sh", "-c", "sleep 30 & sleep 30; wait"], timeout=1, env=None)
        assert returncode == 124
        assert time.monotonic() - start < 10

    def test_run_with_timeout_returns_the_return_code(self) -> None:
        assert load_dev_binaries.run_with_timeout(["sh", "-c", "exit 3"], timeout=10) == 3
