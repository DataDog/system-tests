import subprocess
from pathlib import Path
from typing import Any, TextIO

from utils import pytest, scenarios
from utils.docker_fixtures._test_clients import _core

_BASE = "datadog/system-tests:php-parametric.base-c84d9fa316f4"
_HEAD = f'Head "https://registry-1.docker.io/v2/datadog/system-tests/manifests/{_BASE.split(":")[1]}"'
_RESOLVE = f"failed to resolve source metadata for docker.io/{_BASE}: failed to do request: {_HEAD}"

# Output of the failure seen in the nightly (2026-11-23, php parametric)
TLS_TIMEOUT_LOG = f"""#3 [internal] load metadata for docker.io/{_BASE}
#3 ERROR: failed to do request: {_HEAD}: net/http: TLS handshake timeout
------
 > [internal] load metadata for docker.io/{_BASE}:
------
ERROR: failed to build: failed to solve: {_RESOLVE}: net/http: TLS handshake timeout
"""

TOO_MANY_REQUESTS_LOG = f"""#3 [internal] load metadata for docker.io/{_BASE}
ERROR: failed to solve: {_BASE}: failed to resolve source metadata: unexpected status from HEAD request: \
429 Too Many Requests: toomanyrequests: You have reached your pull rate limit.
"""

BAD_GATEWAY_LOG = """#7 [base 1/1] FROM docker.io/library/php:8.2
ERROR: failed to solve: failed to copy: httpReadSeeker: failed open: unexpected status code \
https://registry-1.docker.io/v2/library/php/blobs/sha256:abc: 502 Bad Gateway
"""

# Other real buildkit/buildx transient errors
BLOB_UNEXPECTED_EOF_LOG = """#7 [base 1/1] FROM docker.io/library/php:8.2@sha256:abc
#7 ERROR: failed to copy: unexpected EOF
------
ERROR: failed to build: failed to solve: failed to copy: unexpected EOF
"""
HEAD_EOF_LOG = f"ERROR: failed to solve: {_RESOLVE}: EOF\n"
NO_SUCH_HOST_LOG = (
    f"ERROR: failed to solve: {_RESOLVE}: dial tcp: lookup registry-1.docker.io on 127.0.0.53:53: no such host\n"
)
DEADLINE_EXCEEDED_LOG = f"ERROR: failed to solve: {_RESOLVE}: context deadline exceeded\n"
CLIENT_TIMEOUT_LOG = (
    f"ERROR: failed to solve: {_RESOLVE}: net/http: request canceled (Client.Timeout exceeded while awaiting headers)\n"
)
BUILDER_LOST_LOG = """#9 [3/5] COPY . /app
ERROR: failed to receive status: rpc error: code = Unavailable desc = error reading from server: EOF
"""

COMPILE_ERROR_LOG = """#9 [4/6] RUN composer install
#9 1.234 PHP Parse error: syntax error, unexpected token "}" in /app/server.php on line 12
#9 ERROR: process "/bin/sh -c composer install" did not complete successfully: exit code: 255
------
ERROR: failed to build: failed to solve: process "/bin/sh -c composer install" did not complete successfully: \
exit code: 255
"""

# A RUN step that fails on a network error is a build step failure: not retried
RUN_STEP_NETWORK_ERROR_LOG = """#9 [4/6] RUN pip install -r requirements.txt
#9 3.2 ERROR: Could not install packages due to an OSError: ('Connection aborted.', \
ConnectionResetError(104, 'Connection reset by peer'))
#9 ERROR: process "/bin/sh -c pip install -r requirements.txt" did not complete successfully: exit code: 1
ERROR: failed to solve: process "/bin/sh -c pip install -r requirements.txt" did not complete successfully: \
exit code: 1
"""
RUN_STEP_UNEXPECTED_EOF_LOG = """#9 [4/6] RUN curl -fsSL https://example.com/tool.tgz | tar xz
#9 2.1 gzip: stdin: unexpected EOF
#9 ERROR: process "/bin/sh -c curl -fsSL https://example.com/tool.tgz | tar xz" did not complete successfully: \
exit code: 2
ERROR: failed to solve: process "/bin/sh -c curl -fsSL https://example.com/tool.tgz | tar xz" did not complete \
successfully: exit code: 2
"""

# A step prints (and recovers from) a network error, then a real failure happens in another step
RECOVERED_NETWORK_ERROR_THEN_COPY_FAILURE_LOG = """#6 [2/4] RUN ./download.sh
#6 1.204 ERROR: download failed: read tcp 172.17.0.2:41234->1.2.3.4:443: read: connection reset by peer, retrying
#6 3.410 download ok
#6 DONE 3.5s
#7 [3/4] COPY missing.txt /app/
#7 ERROR: failed to calculate checksum of ref 3f0c::wxyz: "/missing.txt": not found
------
 > [3/4] COPY missing.txt /app/:
------
ERROR: failed to build: failed to solve: failed to compute cache key: failed to calculate checksum of ref \
3f0c::wxyz: "/missing.txt": not found
"""

DOCKERFILE_SYNTAX_ERROR_LOG = """#1 [internal] load build definition from parametric.Dockerfile
ERROR: failed to solve: dockerfile parse error on line 3: unknown instruction: RUNN
"""

SUCCESS_LOG = "#12 naming to docker.io/library/php-test-library done\n"

TRANSIENT_LOGS = [
    TLS_TIMEOUT_LOG,
    TOO_MANY_REQUESTS_LOG,
    BAD_GATEWAY_LOG,
    BLOB_UNEXPECTED_EOF_LOG,
    HEAD_EOF_LOG,
    NO_SUCH_HOST_LOG,
    DEADLINE_EXCEEDED_LOG,
    CLIENT_TIMEOUT_LOG,
    BUILDER_LOST_LOG,
]
BUILD_ERROR_LOGS = [
    COMPILE_ERROR_LOG,
    RUN_STEP_NETWORK_ERROR_LOG,
    RUN_STEP_UNEXPECTED_EOF_LOG,
    RECOVERED_NETWORK_ERROR_THEN_COPY_FAILURE_LOG,
    DOCKERFILE_SYNTAX_ERROR_LOG,
]


class _FakeTime:
    """Replaces the time module in _core: sleep() advances a fake monotonic clock"""

    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class _Completed:
    def __init__(self, returncode: int) -> None:
        self.returncode = returncode


class _FakeRun:
    """Replaces subprocess.run: each call writes the next output to the log file and returns its exit code.

    Each call takes `duration` seconds on the fake clock.
    """

    def __init__(self, clock: _FakeTime, outcomes: list[tuple[int, str]], duration: float = 5) -> None:
        self.clock = clock
        self.outcomes = list(outcomes)
        self.duration = duration
        self.timeouts: list[float] = []

    @property
    def calls(self) -> int:
        return len(self.timeouts)

    def __call__(self, cmd: list[str], *, stdout: TextIO, timeout: float, **kwargs: Any) -> _Completed:  # noqa: ANN401
        del kwargs
        returncode, output = self.outcomes[self.calls]
        self.timeouts.append(timeout)
        if self.duration > timeout:
            self.clock.now += timeout
            raise subprocess.TimeoutExpired(cmd, timeout)
        self.clock.now += self.duration
        stdout.write(output)
        stdout.flush()
        return _Completed(returncode)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _FakeTime:
    fake = _FakeTime()
    monkeypatch.setattr(_core, "time", fake)
    return fake


def _run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    clock: _FakeTime,
    outcomes: list[tuple[int, str]],
    duration: float = 5,
) -> tuple[int, _FakeRun, str]:
    fake = _FakeRun(clock, outcomes, duration)
    monkeypatch.setattr(_core.subprocess, "run", fake)
    log_path = tmp_path / "docker_build_log.log"
    log_path.write_text("running ['docker', 'build']\n")
    returncode = _core._run_docker_build(["docker", "build"], str(log_path), {})  # noqa: SLF001
    return returncode, fake, log_path.read_text()


@scenarios.test_the_test
@pytest.mark.parametrize("log", TRANSIENT_LOGS)
def test_registry_errors_are_transient(log: str):
    assert _core._is_transient_build_failure(log)  # noqa: SLF001


@scenarios.test_the_test
@pytest.mark.parametrize("log", [*BUILD_ERROR_LOGS, SUCCESS_LOG, ""])
def test_build_errors_are_not_transient(log: str):
    assert not _core._is_transient_build_failure(log)  # noqa: SLF001


@scenarios.test_the_test
def test_transient_error_is_retried_until_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, clock: _FakeTime):
    returncode, fake, log = _run(
        monkeypatch, tmp_path, clock, [(1, TLS_TIMEOUT_LOG), (1, BAD_GATEWAY_LOG), (0, SUCCESS_LOG)]
    )

    assert returncode == 0
    assert fake.calls == 3
    assert clock.sleeps == [10, 30]
    # every attempt is marked in the log, and the previous ones are kept
    assert log.startswith("running ['docker', 'build']\n")
    assert "===== docker build attempt 1/3 =====" in log
    assert "===== docker build attempt 2/3 =====" in log
    assert "===== docker build attempt 3/3 =====" in log
    assert "attempt 1/3 failed with a transient registry/network error, retrying in 10s" in log
    assert log.index("attempt 1/3 =====") < log.index("TLS handshake timeout") < log.index("attempt 2/3 =====")
    assert log.index("attempt 2/3 =====") < log.index("502 Bad Gateway") < log.index("attempt 3/3 =====")
    assert log.rstrip().endswith(SUCCESS_LOG.rstrip())


@scenarios.test_the_test
def test_transient_error_gives_up_after_max_attempts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, clock: _FakeTime):
    returncode, fake, log = _run(monkeypatch, tmp_path, clock, [(1, TLS_TIMEOUT_LOG)] * 3)

    assert returncode == 1
    assert fake.calls == 3
    assert clock.sleeps == [10, 30]
    assert log.count("TLS handshake timeout") == 6  # 2 lines per attempt


@scenarios.test_the_test
@pytest.mark.parametrize("log", BUILD_ERROR_LOGS)
def test_build_error_is_not_retried(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, clock: _FakeTime, log: str):
    returncode, fake, _ = _run(monkeypatch, tmp_path, clock, [(1, log), (0, SUCCESS_LOG)])

    assert returncode == 1
    assert fake.calls == 1
    assert clock.sleeps == []


@scenarios.test_the_test
def test_build_error_after_transient_error_is_not_retried(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, clock: _FakeTime
):
    # only the output of the last attempt decides: the TLS error of attempt 1 must not cause a retry
    returncode, fake, _ = _run(
        monkeypatch, tmp_path, clock, [(1, TLS_TIMEOUT_LOG), (1, COMPILE_ERROR_LOG), (0, SUCCESS_LOG)]
    )

    assert returncode == 1
    assert fake.calls == 2
    assert clock.sleeps == [10]


@scenarios.test_the_test
def test_attempt_timeouts_share_the_total_budget(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, clock: _FakeTime):
    start = clock.now
    # attempt 1 takes 250s, 10s wait, attempt 2 takes 250s, 30s wait: attempt 3 only gets the 360s left
    returncode, fake, _ = _run(monkeypatch, tmp_path, clock, [(1, TLS_TIMEOUT_LOG)] * 3, duration=250)

    assert returncode == 1
    assert fake.timeouts == [600, 600, 360]
    assert clock.sleeps == [10, 30]
    assert clock.now - start == 790


@scenarios.test_the_test
def test_no_new_attempt_without_enough_budget(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, clock: _FakeTime):
    start = clock.now
    # attempt 1 takes 400s, 10s wait, attempt 2 takes 400s: 90s left, minus a 30s wait, is not enough
    returncode, fake, log = _run(monkeypatch, tmp_path, clock, [(1, TLS_TIMEOUT_LOG)] * 3, duration=400)

    assert returncode == 1
    assert fake.timeouts == [600, 490]
    assert clock.sleeps == [10]
    assert clock.now - start == 810
    assert "attempt 2/3 failed with a transient registry/network error, not retrying" in log


@scenarios.test_the_test
def test_attempt_is_killed_at_the_end_of_the_budget(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, clock: _FakeTime):
    start = clock.now
    # attempts take 350s: attempt 3 starts with 160s left, and is killed when the 900s budget is spent.
    # A timeout is not retried, as before.
    with pytest.raises(subprocess.TimeoutExpired):
        _run(monkeypatch, tmp_path, clock, [(1, TLS_TIMEOUT_LOG)] * 3, duration=350)

    assert clock.sleeps == [10, 30]
    assert clock.now - start == 900


def _factory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, clock: _FakeTime, outcomes: list[tuple[int, str]]
) -> _core.TestClientFactory:
    monkeypatch.setattr(_core.subprocess, "run", _FakeRun(clock, outcomes))
    monkeypatch.setattr(_core, "mirror_enabled", lambda: False)
    monkeypatch.setattr(_core.shutil, "which", lambda _: "/usr/bin/docker")

    dockerfile = tmp_path / "parametric.Dockerfile"
    dockerfile.write_text("FROM alpine\nCMD ['run']\n")
    factory = _core.TestClientFactory(
        library="php",
        dockerfile=str(dockerfile),
        tag="php-test-library",
        container_name="php-test-library",
        container_volumes={},
        container_env={},
    )
    factory.configure(str(tmp_path / "logs"))
    return factory


@scenarios.test_the_test
def test_factory_build_survives_registry_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, clock: _FakeTime):
    factory = _factory(monkeypatch, tmp_path, clock, [(1, TLS_TIMEOUT_LOG), (0, SUCCESS_LOG)])

    class _Image:
        attrs: dict[str, Any] = {"Config": {"Cmd": ["run"]}}

    factory._image = _Image()  # type: ignore[assignment] # noqa: SLF001
    factory.build(github_token_file="")

    log = (tmp_path / "logs" / "outputs" / "docker_build_log.log").read_text()
    assert log.startswith("running ['/usr/bin/docker', 'build', '--progress=plain'")
    assert "===== docker build attempt 2/3 =====" in log
    assert clock.sleeps == [10]


@scenarios.test_the_test
def test_factory_build_fails_on_first_build_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, clock: _FakeTime):
    factory = _factory(monkeypatch, tmp_path, clock, [(1, COMPILE_ERROR_LOG), (0, SUCCESS_LOG)])

    with pytest.raises(pytest.exit.Exception, match="Failed to build framework test server image"):
        factory.build(github_token_file="")

    assert clock.sleeps == []
