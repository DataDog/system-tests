from __future__ import annotations

import contextlib
import fnmatch
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import tempfile
import time
from typing import TYPE_CHECKING, Any

from utils.docker_fixtures._test_agent import TestAgentAPI, _request_token
from utils.docker_fixtures._test_clients._test_client_parametric import ParametricTestClientApi

if TYPE_CHECKING:
    from collections.abc import Generator

    import pytest


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class ProcessContainer:
    """Small Docker Container-compatible adapter backed by PRoot and subprocess."""

    def __init__(
        self,
        *,
        name: str,
        proot: Path,
        executable: Path,
        environment: dict[str, str],
        arguments: list[str],
        output_directory: Path,
    ) -> None:
        self.name = name
        self._proot = proot
        self._executable = executable
        self._environment = environment
        self._arguments = arguments
        self._output_directory = output_directory
        self._output_directory.mkdir(parents=True, exist_ok=True)
        test_tmp = os.environ.get("TEST_TMPDIR")
        self._root = Path(tempfile.mkdtemp(prefix=f"{name}-", dir=test_tmp))
        for path in (
            "etc/datadog-agent/managed/datadog-agent/stable",
            "parametric-tracer-logs",
            "tmp",
            "opt/parametric",
        ):
            (self._root / path).mkdir(parents=True, exist_ok=True)
        (self._root / "opt/parametric/server").touch()
        self._ready_file = self._root / "tmp/server.ready"
        self._stdout_path = self._output_directory / "server.stdout.log"
        self._stderr_path = self._output_directory / "server.stderr.log"
        self._process: subprocess.Popen[bytes] | None = None
        self._assigned_port: int | None = None
        self.status = "created"
        self._start()

    def _start(self) -> None:
        self._ready_file.unlink(missing_ok=True)
        env = os.environ.copy()
        env.update(self._environment)
        env["APM_TEST_CLIENT_SERVER_PORT"] = str(self._assigned_port or 0)
        env["APM_TEST_CLIENT_READY_FILE"] = "/tmp/server.ready"  # noqa: S108 - private PRoot path
        env["PROOT_TMP_DIR"] = str(self._root / "tmp")
        command = [
            str(self._proot),
            "-0",
            "-r",
            str(self._root),
            "-b",
            f"{self._executable}:/opt/parametric/server",
            "-b",
            "/proc",
        ]
        for library_directory in ("/lib", "/lib64", "/usr/lib", "/usr/lib64"):
            if Path(library_directory).is_dir():
                command.extend(["-b", library_directory])
        command.extend(
            [
                "-w",
                "/tmp",  # noqa: S108 - private PRoot path
                "/opt/parametric/server",
                *self._arguments,
            ]
        )
        stdout = self._stdout_path.open("ab")
        stderr = self._stderr_path.open("ab")
        try:
            self._process = subprocess.Popen(
                command,
                env=env,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
            )
        finally:
            stdout.close()
            stderr.close()
        self.status = "running"

    def assigned_port(self, timeout: float = 60) -> int:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.reload()
            if self.status != "running":
                raise RuntimeError(f"Process {self.name} exited before publishing its port:\n{self.logs().decode()}")
            try:
                self._assigned_port = int(self._ready_file.read_text().strip())
                return self._assigned_port
            except (FileNotFoundError, ValueError):
                time.sleep(0.01)
        raise TimeoutError(f"Process {self.name} did not publish its port within {timeout}s")

    def reload(self) -> None:
        if self._process is None:
            self.status = "exited"
        elif self._process.poll() is None:
            self.status = "running"
        else:
            self.status = "exited"

    def restart(self) -> None:
        self.stop()
        self._start()

    def stop(self, timeout: int = 5) -> None:
        process = self._process
        if process is None or process.poll() is not None:
            self.status = "exited"
            return
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        self.status = "exited"

    def remove(self, force: bool = False) -> None:  # noqa: FBT001, FBT002
        if force:
            self.stop()
        shutil.rmtree(self._root, ignore_errors=True)

    def wait(self, timeout: float | None = None) -> dict[str, int]:
        if self._process is None:
            return {"StatusCode": -1}
        return {"StatusCode": self._process.wait(timeout=timeout)}

    def logs(self, *, stderr: bool = True, stdout: bool = True) -> bytes:
        result = b""
        if stdout and self._stdout_path.exists():
            result += self._stdout_path.read_bytes()
        if stderr and self._stderr_path.exists():
            result += self._stderr_path.read_bytes()
        return result

    def _translate(self, path: str) -> Path:
        if path == "/proc" or path.startswith("/proc/"):
            return Path(path)
        relative = path.removeprefix("/")
        translated = (self._root / relative).resolve()
        if self._root.resolve() not in (translated, *translated.parents):
            raise ValueError(f"Path escapes process sandbox: {path}")
        return translated

    def write_file(self, path: str, content: str) -> None:
        target = self._translate(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def list_files(self, path: str, pattern: str) -> list[str]:
        root = self._translate(path)
        if not root.exists():
            return []
        result: list[str] = []
        for candidate in root.rglob("*"):
            if candidate.is_file() and fnmatch.fnmatch(candidate.name, pattern):
                result.append("/" + str(candidate.relative_to(self._root)))
        return result

    def read_file(self, path: str, *, binary: bool = False) -> str | bytes:
        target = self._translate(path)
        return target.read_bytes() if binary else target.read_text()

    def _descendants(self) -> list[int]:
        if self._process is None:
            return []
        result: list[int] = []
        pending = [self._process.pid]
        while pending:
            pid = pending.pop()
            try:
                children = [int(value) for value in Path(f"/proc/{pid}/task/{pid}/children").read_text().split()]
            except (FileNotFoundError, ProcessLookupError):
                continue
            result.extend(children)
            pending.extend(children)
        return result

    def process_id(self) -> int:
        descendants = self._descendants()
        if descendants:
            return descendants[-1]
        if self._process is None:
            raise ProcessLookupError(self.name)
        return self._process.pid

    def proc_fd_paths(self, pid: int, target_prefix: str) -> list[str]:
        result: list[str] = []
        for candidate in Path(f"/proc/{pid}/fd").iterdir():
            try:
                target = str(candidate.readlink())
            except OSError:
                continue
            if target_prefix in target:
                result.append(str(candidate))
        return result

    @staticmethod
    def read_link(path: str) -> str:
        return str(Path(path).readlink())

    def exec_run(self, command: str, *, demux: bool = False) -> tuple[int, tuple[bytes, bytes | None]]:
        del command, demux
        return 127, (b"", b"process runtime does not provide a sandbox shell")


class ProcessParametricTestClientFactory:
    def __init__(self, *, executable: Path, proot: Path, library: str = "golang") -> None:
        self.library = library
        self._executable = executable
        self._proot = proot
        self.host_log_folder = ""

    def configure(self, host_log_folder: str) -> None:
        self.host_log_folder = host_log_folder

    @contextlib.contextmanager
    def get_apm_library(
        self,
        request: pytest.FixtureRequest,
        worker_id: str,
        test_id: str,
        test_agent: TestAgentAPI,
        library_env: dict[str, str],
        library_extra_command_arguments: list[str],
    ) -> Generator[ParametricTestClientApi, None, None]:
        del worker_id
        env = {
            "DD_TRACE_DEBUG": "true",
            "DD_TRACE_AGENT_URL": test_agent.apm_url,
            "DD_AGENT_HOST": test_agent.host,
            "DD_TRACE_AGENT_PORT": str(test_agent.host_port),
            "DD_TRACE_OTEL_ENABLED": "true",
        }
        for key, value in library_env.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = str(value)
        output_directory = (
            Path(self.host_log_folder)
            / "outputs"
            / (request.cls.__name__ if request.cls is not None else "NoClass")
            / request.node.name
        )
        container = ProcessContainer(
            name=f"{self.library}-test-client-{test_id}",
            proot=self._proot,
            executable=self._executable,
            environment=env,
            arguments=library_extra_command_arguments,
            output_directory=output_directory,
        )
        try:
            port = container.assigned_port()
            yield ParametricTestClientApi(self.library, f"http://127.0.0.1:{port}", 60, container)  # type: ignore[arg-type]
        finally:
            container.stop()
            request.node.add_report_section(
                "teardown", f"{self.library.capitalize()} Library Output", f"Log directory:\n{output_directory}"
            )
            container.remove()


class ProcessTestAgentFactory:
    def __init__(self, *, executable: Path, default_ports: tuple[int, int, int]) -> None:
        self._executable = executable
        self._default_ports = default_ports
        self.host_log_folder = ""

    def configure(self, host_log_folder: str) -> None:
        self.host_log_folder = host_log_folder

    def _api(
        self,
        request: pytest.FixtureRequest,
        ports: tuple[int, int, int],
    ) -> TestAgentAPI:
        apm_port, otlp_http_port, otlp_grpc_port = ports
        return TestAgentAPI(
            "127.0.0.1",
            apm_port,
            self.host_log_folder,
            host_port=apm_port,
            otlp_http_host_port=otlp_http_port,
            otlp_grpc_host_port=otlp_grpc_port,
            pytest_request=request,
            network="",
            tracer_host="127.0.0.1",
            tracer_otlp_http_port=otlp_http_port,
            tracer_otlp_grpc_port=otlp_grpc_port,
        )

    @contextlib.contextmanager
    def default_agent(self, request: pytest.FixtureRequest) -> Generator[TestAgentAPI, None, None]:
        yield self._api(request, self._default_ports)

    @contextlib.contextmanager
    def get_test_agent_api(
        self,
        *,
        request: pytest.FixtureRequest,
        agent_env: dict[str, str],
        container_otlp_http_port: int,
        container_otlp_grpc_port: int,
    ) -> Generator[TestAgentAPI, None, None]:
        # Docker needs the requested values as container-internal ports. Ordinary
        # processes use topology-neutral endpoint properties, so choose unique host
        # ports instead and avoid collisions between concurrent remote shards.
        del container_otlp_http_port, container_otlp_grpc_port
        apm_port = _free_port()
        otlp_http_port = _free_port()
        otlp_grpc_port = _free_port()
        output_directory = (
            Path(self.host_log_folder)
            / "outputs"
            / (request.cls.__name__ if request.cls is not None else "NoClass")
            / request.node.name
        )
        output_directory.mkdir(parents=True, exist_ok=True)
        log_path = output_directory / "agent_process.log"
        env = os.environ.copy()
        env.update(
            {
                "ENABLED_CHECKS": "trace_count_header",
                "VCR_CASSETTES_DIRECTORY": str(Path.cwd() / "tests/integration_frameworks/utils/vcr-cassettes"),
                "VCR_PROVIDER_MAP": "aiguard=https://app.datadoghq.com/api/v2/ai-guard",
            }
        )
        env.update(agent_env)
        command = [
            str(self._executable),
            f"--port={apm_port}",
            f"--otlp-http-port={otlp_http_port}",
            f"--otlp-grpc-port={otlp_grpc_port}",
        ]
        with log_path.open("wb") as log_file:
            process = subprocess.Popen(
                command, env=env, stdout=log_file, stderr=subprocess.STDOUT, start_new_session=True
            )
        api = self._api(request, (apm_port, otlp_http_port, otlp_grpc_port))
        try:
            expected_version = agent_env.get("TEST_AGENT_VERSION", "test")
            for _ in range(600):
                if process.poll() is not None:
                    raise RuntimeError(f"Test agent exited during startup:\n{log_path.read_text()}")
                try:
                    actual_version = api.info()["version"]
                except Exception:
                    time.sleep(0.1)
                else:
                    if actual_version != expected_version:
                        raise RuntimeError(f"Agent version {actual_version} is running instead of {expected_version}.")
                    break
            else:
                raise TimeoutError(f"Test agent did not become ready; see {log_path}")

            marks = list(request.node.iter_markers(name="snapshot"))
            if len(marks) > 1:
                raise AssertionError("Multiple snapshot marks detected")
            if marks:
                mark = marks[0]
                if mark.args:
                    raise AssertionError("only keyword arguments are supported by the snapshot decorator")
                kwargs: dict[str, Any] = dict(mark.kwargs)
                kwargs.setdefault("token", _request_token(request).replace(" ", "_").replace(os.path.sep, "_"))
                with api.snapshot_context(**kwargs):
                    yield api
            else:
                yield api
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
            request.node.add_report_section("teardown", "Test Agent Output", f"Log file:\n{log_path}")
