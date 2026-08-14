from __future__ import annotations

# Unit tests intentionally construct adapters without invoking their network-startup
# constructors so their private runtime state can be tested deterministically.
# ruff: noqa: SLF001

from pathlib import Path
import stat
from types import SimpleNamespace
from typing import Any, cast
import zipfile

import pytest

from bazel.parametric.sharding import pytest_split_arguments, round_robin_indices
from bazel.parametric.python_server import _publish_port
from utils import scenarios
from utils._context._scenarios.parametric import process_library_configuration
from utils.docker_fixtures._test_agent import TestAgentAPI
from utils.docker_fixtures._test_clients._test_client_parametric import ParametricTestClientApi
from utils.parametric.process import (
    PreparedProcessLaunch,
    ProcessContainer,
    ProcessLaunchSpec,
    ProcessOutputRetention,
    ProcessParametricTestClientFactory,
    extract_archive,
    find_embedded_runtime,
    python_otel_exporter_endpoint,
)


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
    environments: list[dict[str, str]] = []

    def popen(command: list[str], **kwargs: object) -> _Process:
        del command
        environments.append(cast("dict[str, str]", kwargs["env"]))
        return processes.pop(0)

    monkeypatch.setattr("utils.parametric.process.subprocess.Popen", popen)
    monkeypatch.setattr("utils.parametric.process.os.killpg", lambda pid, sig: killed.append((pid, sig)))
    monkeypatch.setenv("TEST_TMPDIR", str(tmp_path))
    container = ProcessContainer(
        name="lifecycle",
        proot=Path("/proot"),
        launch=PreparedProcessLaunch.prepare(ProcessLaunchSpec.executable(Path("/server"))),
        environment={},
        arguments=[],
        output_directory=tmp_path / "outputs",
    )
    root = container._root
    assert environments[0]["TMPDIR"] == "/tmp"

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


def _zip_info(name: str, mode: int) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name)
    info.create_system = 3
    info.external_attr = mode << 16
    return info


def _write_runtime_archive(archive: Path) -> None:
    with zipfile.ZipFile(archive, "w") as zip_file:
        zip_file.writestr(_zip_info("runtime/python3", stat.S_IFREG | 0o755), b"interpreter")
        zip_file.writestr(_zip_info("venv/pyvenv.cfg", stat.S_IFREG | 0o644), b"home = runtime\n")
        zip_file.writestr(_zip_info("venv/bin/python3", stat.S_IFLNK | 0o777), "../../runtime/python3")
        zip_file.writestr(
            _zip_info("runfiles/workspace/bazel/parametric/python_server.py", stat.S_IFREG | 0o644),
            b"print('server')\n",
        )


@scenarios.test_the_test
def test_archive_extraction_preserves_modes_and_validated_symlinks(tmp_path: Path) -> None:
    archive = tmp_path / "runtime.zip"
    with zipfile.ZipFile(archive, "w") as zip_file:
        zip_file.writestr(_zip_info("runtime/python3", stat.S_IFREG | 0o755), b"interpreter")
        zip_file.writestr(_zip_info("venv/pyvenv.cfg", stat.S_IFREG | 0o644), b"home = runtime\n")
        zip_file.writestr(_zip_info("venv/bin/python3", stat.S_IFLNK | 0o777), "../../runtime/python3")

    destination = tmp_path / "extracted"
    extract_archive(archive, destination)

    interpreter = destination / "runtime/python3"
    assert stat.S_IMODE(interpreter.stat().st_mode) == 0o755
    assert (destination / "venv/bin/python3").readlink() == Path("../../runtime/python3")
    assert find_embedded_runtime(destination) == destination / "venv/bin/python3"


@scenarios.test_the_test
def test_prepared_archive_is_extracted_once_shared_sealed_and_cleaned(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    archive = tmp_path / "runtime.zip"
    _write_runtime_archive(archive)
    extraction_count = 0
    original_extract_archive = extract_archive

    def counted_extract_archive(source: Path, destination: Path) -> None:
        nonlocal extraction_count
        extraction_count += 1
        original_extract_archive(source, destination)

    commands: list[list[str]] = []
    environments: list[dict[str, str]] = []
    processes = [_Process(100), _Process(101)]
    cleanups: list[Any] = []

    def popen(command: list[str], **kwargs: object) -> _Process:
        commands.append(command)
        environments.append(cast("dict[str, str]", kwargs["env"]))
        return processes.pop(0)

    monkeypatch.setattr("utils.parametric.process.extract_archive", counted_extract_archive)
    monkeypatch.setattr("utils.parametric.process.subprocess.Popen", popen)
    monkeypatch.setattr("utils.parametric.process.os.killpg", lambda _pid, _signal: None)
    monkeypatch.setenv("TEST_TMPDIR", str(tmp_path))
    config = SimpleNamespace(add_cleanup=cleanups.append)
    factory = ProcessParametricTestClientFactory(
        launch=ProcessLaunchSpec.archive(archive, entrypoint="bazel/parametric/python_server.py"),
        proot=Path("/proot"),
        library="python",
    )
    factory.configure(str(tmp_path / "logs"), cast("Any", config))
    prepared = factory._launch
    assert prepared is not None
    assert extraction_count == 1
    assert cleanups == [prepared.cleanup]
    assert prepared.temporary_root is not None
    assert stat.S_IMODE(prepared.bind_source.stat().st_mode) & 0o222 == 0
    assert all(
        path.is_symlink() or stat.S_IMODE(path.stat().st_mode) & 0o222 == 0 for path in prepared.bind_source.rglob("*")
    )

    containers = [
        ProcessContainer(
            name=f"shared-{index}",
            proot=Path("/proot"),
            launch=prepared,
            environment={},
            arguments=[],
            output_directory=tmp_path / f"outputs-{index}",
        )
        for index in range(2)
    ]
    roots = [container._root for container in containers]
    ready_files = [container._ready_file for container in containers]
    for container in containers:
        container.stop()
        container.remove()

    bind = f"{prepared.bind_source}:/opt/parametric/archive"
    assert all(bind in command for command in commands)
    assert len(set(roots)) == 2
    assert len(set(ready_files)) == 2
    assert all(environment["PYTHONDONTWRITEBYTECODE"] == "1" for environment in environments)
    assert len({environment["PROOT_TMP_DIR"] for environment in environments}) == 2
    assert extraction_count == 1
    temporary_root = prepared.temporary_root
    cleanups[0]()
    cleanups[0]()
    assert not temporary_root.exists()


@scenarios.test_the_test
def test_prepared_static_executable_does_not_extract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "utils.parametric.process.extract_archive",
        lambda _source, _destination: pytest.fail("static executables must not be extracted"),
    )

    prepared = PreparedProcessLaunch.prepare(ProcessLaunchSpec.executable(Path("/server")))

    assert prepared.bind_source == Path("/server")
    assert prepared.command == ("/opt/parametric/server",)
    assert prepared.temporary_root is None


@scenarios.test_the_test
@pytest.mark.parametrize(
    ("member", "content"),
    [
        (_zip_info("../outside", stat.S_IFREG | 0o644), b"escape"),
        (_zip_info("venv/bin/python3", stat.S_IFLNK | 0o777), "../../../outside"),
    ],
)
def test_archive_extraction_rejects_escapes(
    tmp_path: Path,
    member: zipfile.ZipInfo,
    content: bytes | str,
) -> None:
    archive = tmp_path / "malicious.zip"
    with zipfile.ZipFile(archive, "w") as zip_file:
        zip_file.writestr(member, content)

    with pytest.raises(ValueError, match="escapes"):
        extract_archive(archive, tmp_path / "extracted")


@scenarios.test_the_test
def test_python_launcher_publishes_assigned_port(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ready_file = tmp_path / "server.ready"
    monkeypatch.setenv("APM_TEST_CLIENT_READY_FILE", str(ready_file))
    server_socket = SimpleNamespace(getsockname=lambda: ("127.0.0.1", 43123))

    _publish_port(cast("Any", server_socket))

    assert ready_file.read_text(encoding="utf-8") == "43123"


@scenarios.test_the_test
def test_process_library_configuration_selects_static_go_and_python_archive() -> None:
    go = process_library_configuration("golang")
    python = process_library_configuration("python")

    assert go.archive_entrypoint is None
    assert go.version_environment_variable == "SYSTEM_TESTS_GO_LIBRARY_VERSION"
    assert python.archive_entrypoint == "bazel/parametric/python_server.py"
    assert python.version_environment_variable == "SYSTEM_TESTS_PYTHON_LIBRARY_VERSION"
    assert dict(python.environment)["DD_PATCH_MODULES"] == "fastapi:false,startlette:false"
    with pytest.raises(ValueError, match="supports only"):
        process_library_configuration("ruby")


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
    assert python_otel_exporter_endpoint({}, api) == "http://agent.internal:4317"
    assert (
        python_otel_exporter_endpoint({"OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf"}, api)
        == "http://agent.internal:4318"
    )


@scenarios.test_the_test
def test_wait_for_telemetry_metrics_returns_after_first_matching_poll(monkeypatch: pytest.MonkeyPatch) -> None:
    api = cast("TestAgentAPI", object.__new__(TestAgentAPI))
    metric = {"metric": "otel.log_records", "tags": ["protocol:http"]}
    responses = [
        [],
        [
            {
                "request_type": "generate-metrics",
                "payload": {"series": [{"metric": "other", "tags": []}, metric]},
            }
        ],
        pytest.fail,
    ]
    clear_calls = 0

    def telemetry(*, clear: bool = False) -> list[dict[str, Any]]:
        assert not clear
        response = responses.pop(0)
        assert isinstance(response, list), "telemetry was polled after a matching metric was found"
        return response

    def clear() -> None:
        nonlocal clear_calls
        clear_calls += 1

    monkeypatch.setattr(api, "telemetry", telemetry)
    monkeypatch.setattr(api, "clear", clear)
    monkeypatch.setattr("utils.docker_fixtures._test_agent.time.sleep", lambda _seconds: None)

    assert api.wait_for_telemetry_metrics("otel.log_records", clear=True) == [metric]
    assert clear_calls == 1
    assert responses == [pytest.fail]


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


def _report(nodeid: str, when: str, outcome: str, *, wasxfail: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        nodeid=nodeid,
        when=when,
        failed=outcome == "failed",
        passed=outcome == "passed",
        skipped=outcome == "skipped",
        wasxfail="expected failure" if wasxfail else None,
    )


@scenarios.test_the_test
@pytest.mark.parametrize(
    ("reports", "retained"),
    [
        ([("setup", "passed", False), ("call", "passed", False), ("teardown", "passed", False)], False),
        ([("setup", "skipped", False), ("teardown", "passed", False)], False),
        ([("setup", "passed", False), ("call", "skipped", True), ("teardown", "passed", False)], False),
        ([("setup", "passed", False), ("call", "failed", False), ("teardown", "passed", False)], True),
        ([("setup", "failed", False), ("teardown", "passed", False)], True),
        ([("setup", "passed", False), ("call", "passed", True), ("teardown", "passed", False)], True),
    ],
)
def test_process_output_retention_classifies_pytest_outcomes(
    tmp_path: Path,
    reports: list[tuple[str, str, bool]],
    retained: bool,  # noqa: FBT001
) -> None:
    item = SimpleNamespace(
        nodeid="test_file.py::Test_Class::test_case", cls=type("Test_Class", (), {}), name="test_case"
    )
    output = tmp_path / "Test_Class" / "test_case"
    output.mkdir(parents=True)
    (output / "process.log").write_text("diagnostics", encoding="utf-8")
    retention = ProcessOutputRetention(tmp_path, keep_success_outputs=False)
    retention.pytest_collection_modifyitems([cast("Any", item)])

    for when, outcome, wasxfail in reports:
        retention.pytest_runtest_logreport(cast("Any", _report(item.nodeid, when, outcome, wasxfail=wasxfail)))

    assert output.exists() is retained


@scenarios.test_the_test
def test_process_output_retention_keeps_toggle_and_interrupted_tests(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    items = [
        SimpleNamespace(nodeid="test_file.py::test_toggle", cls=None, name="test_toggle"),
        SimpleNamespace(nodeid="test_file.py::test_interrupted", cls=None, name="test_interrupted"),
    ]
    for item in items:
        output = tmp_path / "NoClass" / item.name
        output.mkdir(parents=True)
        (output / "process.log").write_text("diagnostics", encoding="utf-8")

    monkeypatch.setenv("SYSTEM_TESTS_PARAMETRIC_KEEP_SUCCESS_OUTPUTS", "1")
    keep_all = ProcessOutputRetention(tmp_path)
    keep_all.pytest_collection_modifyitems([cast("Any", items[0])])
    for when in ("setup", "call", "teardown"):
        keep_all.pytest_runtest_logreport(cast("Any", _report(items[0].nodeid, when, "passed")))

    interrupted = ProcessOutputRetention(tmp_path, keep_success_outputs=False)
    interrupted.pytest_collection_modifyitems([cast("Any", items[1])])
    interrupted.pytest_runtest_logreport(cast("Any", _report(items[1].nodeid, "setup", "passed")))

    assert (tmp_path / "NoClass" / "test_toggle").exists()
    assert (tmp_path / "NoClass" / "test_interrupted").exists()


@scenarios.test_the_test
def test_bazel_shards_map_to_every_pytest_split_group_once() -> None:
    duration_manifest = Path("go_test_durations.json")
    groups = [pytest_split_arguments(32, shard_index, duration_manifest) for shard_index in range(32)]

    assert groups == [
        [
            "--splitting-algorithm=least_duration",
            "--durations-path=go_test_durations.json",
            "--splits=32",
            f"--group={group}",
        ]
        for group in range(1, 33)
    ]
    assert len({tuple(arguments) for arguments in groups}) == 32

    round_robin_groups = [round_robin_indices(825, 32, shard_index)[0] for shard_index in range(32)]
    assert sorted(index for group in round_robin_groups for index in group) == list(range(825))
    assert len({index for group in round_robin_groups for index in group}) == 825
