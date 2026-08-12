from __future__ import annotations

# Unit tests intentionally construct adapters without invoking their network-startup
# constructors so their private runtime state can be tested deterministically.
# ruff: noqa: SLF001

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from bazel.parametric.sharding import pytest_split_arguments
from utils import scenarios
from utils.docker_fixtures._test_agent import TestAgentAPI
from utils.docker_fixtures._test_clients._test_client_parametric import ParametricTestClientApi
from utils.parametric.process import ProcessContainer


class _Process:
    def __init__(self, pid: int) -> None:
        self.pid = pid
        self.returncode: int | None = None
        self.wait_timeouts: list[float | None] = []

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        self.wait_timeouts.append(timeout)
        self.returncode = 0
        return self.returncode


class _DockerContainer:
    name = "docker-compatible"
    status = "running"

    def __init__(self) -> None:
        self.restarts = 0
        self.wait_timeout: float | None = None

    def logs(self, *, stderr: bool = True, stdout: bool = True) -> bytes:
        del stderr, stdout
        return b"docker logs"

    def restart(self) -> None:
        self.restarts += 1

    def wait(self, timeout: float | None = None) -> dict[str, int]:
        self.wait_timeout = timeout
        return {"StatusCode": 0}


def _request() -> SimpleNamespace:
    return SimpleNamespace(
        cls=None,
        module=SimpleNamespace(__name__="test_module"),
        node=SimpleNamespace(name="test_name"),
    )


@scenarios.test_the_test
def test_process_container_lifecycle_and_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    processes = [_Process(100), _Process(101)]
    killed: list[tuple[int, int]] = []

    def popen(command: list[str], **kwargs: object) -> _Process:
        del command, kwargs
        return processes.pop(0)

    monkeypatch.setattr("utils.parametric.process.subprocess.Popen", popen)
    monkeypatch.setattr("utils.parametric.process.os.killpg", lambda pid, sig: killed.append((pid, sig)))
    monkeypatch.setenv("TEST_TMPDIR", str(tmp_path))
    container = ProcessContainer(
        name="lifecycle",
        proot=Path("/proot"),
        executable=Path("/server"),
        environment={},
        arguments=[],
        output_directory=tmp_path / "outputs",
    )
    root = container._root

    container.restart()
    assert container.status == "running"
    assert killed[0][0] == 100
    container.stop()
    assert killed[1][0] == 101
    container.remove()
    assert not root.exists()


@scenarios.test_the_test
def test_process_container_rootfs_translation(tmp_path: Path) -> None:
    container = cast("ProcessContainer", object.__new__(ProcessContainer))
    container._root = tmp_path
    (tmp_path / "parametric-tracer-logs").mkdir()

    container.write_file("/etc/datadog-agent/managed/datadog-agent/stable/config", "stable")
    container.write_file("/parametric-tracer-logs/trace.log", "trace")

    assert container.read_file("/etc/datadog-agent/managed/datadog-agent/stable/config") == "stable"
    assert container.list_files("/parametric-tracer-logs", "*.log") == ["/parametric-tracer-logs/trace.log"]
    assert container._translate("/proc/self/status") == Path("/proc/self/status")
    with pytest.raises(ValueError, match="escapes process sandbox"):
        container._translate("/../../outside")


@scenarios.test_the_test
def test_test_agent_endpoint_mapping(tmp_path: Path) -> None:
    api = TestAgentAPI(
        "agent-container",
        8126,
        str(tmp_path),
        host_port=18126,
        otlp_http_host_port=14318,
        otlp_grpc_host_port=14317,
        pytest_request=_request(),
        network="network",
        tracer_host="agent.internal",
        tracer_otlp_http_port=4318,
        tracer_otlp_grpc_port=4317,
    )

    assert api.apm_url == "http://agent.internal:8126"
    assert api.otlp_http_url == "http://agent.internal:4318"
    assert api.otlp_grpc_endpoint == "agent.internal:4317"


@scenarios.test_the_test
def test_runtime_neutral_api_keeps_docker_restart_and_wait() -> None:
    container = _DockerContainer()
    client = cast("ParametricTestClientApi", object.__new__(ParametricTestClientApi))
    client.container = cast("Any", container)
    client.timeout = 0
    client._wait = lambda _timeout: None  # type: ignore[assignment]

    client.restart()
    client.wait_for_exit(2.5)

    assert container.restarts == 1
    assert container.wait_timeout == 2.5
    assert client.get_stderr_logs() == "docker logs"


@scenarios.test_the_test
def test_sixteen_bazel_shards_map_to_every_pytest_split_group_once() -> None:
    groups = [pytest_split_arguments(16, shard_index) for shard_index in range(16)]

    assert groups == [
        ["--splitting-algorithm=least_duration", "--splits=16", f"--group={group}"]
        for group in range(1, 17)
    ]
    assert len({tuple(arguments) for arguments in groups}) == 16
