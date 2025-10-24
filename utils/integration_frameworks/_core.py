import base64
from collections.abc import Generator
import contextlib
from http import HTTPStatus
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import TextIO, TypedDict, Any
import urllib.parse

from docker.models.containers import Container
import pytest
import requests

from utils._logger import logger
from utils._context.docker import get_docker_client
from utils.parametric.spec.trace import Trace


IGNORE_PARAMS_FOR_TEST_NAME = (
    "test_agent",
    "test_library",
)


def _get_host_port(worker_id: str, base_port: int) -> int:
    """Deterministic port allocation for each worker"""

    if worker_id == "master":  # xdist disabled
        return base_port

    if worker_id.startswith("gw"):
        return base_port + int(worker_id[2:])

    raise ValueError(f"Unexpected worker_id: {worker_id}")


def _compute_volumes(volumes: dict[str, str]) -> dict[str, dict]:
    """Convert volumes to the format expected by the docker-py API"""
    fixed_volumes: dict[str, dict] = {}
    for key, value in volumes.items():
        if isinstance(value, dict):
            fixed_volumes[key] = value
        elif isinstance(value, str):
            fixed_volumes[key] = {"bind": value, "mode": "rw"}
        else:
            raise TypeError(f"Unexpected type for volume {key}: {type(value)}")

    return fixed_volumes


@contextlib.contextmanager
def docker_run(
    image: str,
    name: str,
    env: dict[str, str],
    volumes: dict[str, str],
    network: str,
    ports: dict[str, int],
    log_file: TextIO,
    command: list[str] | None = None,
) -> Generator[Container, None, None]:
    logger.info(f"Run container {name} from image {image} with ports {ports}")

    try:
        container: Container = get_docker_client().containers.run(
            image,
            name=name,
            environment=env,
            volumes=_compute_volumes(volumes),
            network=network,
            ports=ports,
            command=command,
            detach=True,
        )
        logger.debug(f"Container {name} successfully started")
    except Exception as e:
        # at this point, even if it failed to start, the container may exists!
        for container in get_docker_client().containers.list(filters={"name": name}, all=True):
            container.remove(force=True)

        pytest.fail(f"Failed to run container {name}: {e}")

    try:
        yield container
    finally:
        logger.info(f"Stopping {name}")
        container.stop(timeout=1)
        logs = container.logs()
        log_file.write(logs.decode("utf-8"))
        log_file.flush()
        container.remove(force=True)


class AgentRequest(TypedDict):
    method: str
    url: str
    headers: dict[str, str]
    body: str


class _TestAgentAPI:
    """Abstracts everything about test agent. TODO : share this with parametric test"""

    def __init__(self, host_log_folder: str, host: str, worker_id: str, pytest_request: pytest.FixtureRequest):
        self.host = host
        self.agent_port = _get_host_port(worker_id, 4600)
        self._session = requests.Session()
        self._pytest_request = pytest_request
        self.log_path = (
            f"{host_log_folder}/outputs/{pytest_request.cls.__name__}/{pytest_request.node.name}/agent_api.log"
        )
        Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)

    def _url(self, path: str) -> str:
        return urllib.parse.urljoin(f"http://{self.host}:{self.agent_port}", path)

    def _write_log(self, log_type: str, json_trace: dict | list | None):
        with open(self.log_path, "a") as log:
            log.write(f"\n{log_type}>>>>\n")
            log.write(json.dumps(json_trace))

    def traces(self, **kwargs: dict) -> list[Trace]:
        resp = self._session.get(self._url("/test/session/traces"), **kwargs)  # type: ignore[arg-type]
        resp_json = resp.json()
        self._write_log("traces", resp_json)
        return resp_json

    def requests(self) -> list[AgentRequest]:
        resp = self._session.get(self._url("/test/session/requests"))
        resp_json = resp.json()
        self._write_log("requests", resp_json)
        return resp_json

    def clear(self) -> None:
        self._session.get(self._url("/test/session/clear"))

    def info(self):
        resp = self._session.get(self._url("/info"))

        if resp.status_code != HTTPStatus.OK:
            message = f"Test agent unexpected {resp.status_code} response: {resp.text}"
            logger.error(message)
            raise ValueError(message)

        resp_json = resp.json()
        self._write_log("info", resp_json)
        return resp_json

    def llmobs_requests(self) -> list[Any]:
        reqs = [r for r in self.requests() if r["url"].endswith("/evp_proxy/v2/api/v2/llmobs")]

        events = []
        for r in reqs:
            decoded_body = base64.b64decode(r["body"])
            events.append(json.loads(decoded_body))
        return events

    def llmobs_evaluations_requests(self):
        reqs = [
            r
            for r in self.requests()
            if r["url"].endswith("/evp_proxy/v2/api/intake/llm-obs/v1/eval-metric")
            or r["url"].endswith("/evp_proxy/v2/api/intake/llm-obs/v2/eval-metric")
        ]

        return [json.loads(base64.b64decode(r["body"])) for r in reqs]

    @contextlib.contextmanager
    def snapshot_context(self, token: str, ignores: list[str] | None = None):
        ignores = ignores or []
        try:
            resp = self._session.get(self._url(f"/test/session/start?test_session_token={token}"))
            resp.raise_for_status()
        except Exception as e:
            raise RuntimeError(f"Could not connect to test agent: {e}") from e
        else:
            yield self
            # Query for the results of the test.
            resp = self._session.get(
                self._url(f"/test/session/snapshot?ignores={','.join(ignores)}&test_session_token={token}")
            )
            if resp.status_code != HTTPStatus.OK:
                raise RuntimeError(resp.text)

    @contextlib.contextmanager
    def vcr_context(self, cassette_prefix: str = ""):
        """Starts a VCR context manager, which will prefix all recorded cassettes from the test agent with the
        given prefix. If no prefix is provided, the test name will be used.
        """
        test_name = cassette_prefix or self._pytest_request.node.originalname

        for param in self._pytest_request.node.callspec.params:
            if param not in IGNORE_PARAMS_FOR_TEST_NAME:
                param_value = self._pytest_request.node.callspec.params[param]
                test_name += f"_{param}_{param_value}"

        try:
            resp = self._session.post(self._url("/vcr/test/start"), json={"test_name": test_name})
            resp.raise_for_status()
        except Exception as e:
            raise RuntimeError(f"Could not connect to test agent: {e}") from e
        else:
            yield self
            resp = self._session.post(self._url("/vcr/test/stop"))
            resp.raise_for_status()

    def wait_for_num_traces(self, num: int, *, wait_loops: int = 30, sort_by_start: bool = True) -> list[Trace]:
        """Wait for `num` traces to be received from the test agent.

        Returns after the number of traces has been received or raises otherwise after 2 seconds of polling.

        When sort_by_start=True returned traces are sorted by the span start time to simplify assertions by knowing that
        returned traces are in the same order as they have been created.
        """
        num_received = None
        traces = []
        for _ in range(wait_loops):
            try:
                traces = self.traces()
            except requests.exceptions.RequestException:
                pass
            else:
                num_received = len(traces)
                if num_received == num:
                    if sort_by_start:
                        for trace in traces:
                            # The testagent may receive spans and trace chunks in any order,
                            # so we sort the spans by start time if needed
                            trace.sort(key=lambda x: x["start"])
                        return sorted(traces, key=lambda t: t[0]["start"])
                    return traces
            time.sleep(0.1)
        raise ValueError(f"Number ({num}) of traces not available from test agent, got {num_received}:\n{traces}")

    def wait_for_llmobs_requests(self, num: int, *, wait_loops: int = 30, sort_by_start: bool = True) -> list[Any]:
        """Wait for `num` LLMobs requests to be received from the test agent."""
        num_received = None
        llmobs_requests = []
        for _ in range(wait_loops):
            try:
                llmobs_requests = self.llmobs_requests()
            except requests.exceptions.RequestException:
                pass
            else:
                num_received = len(llmobs_requests)
                if num_received == num:
                    if sort_by_start:
                        for trace in llmobs_requests:
                            # The testagent may receive spans and trace chunks in any order,
                            # so we sort the spans by start time if needed
                            trace.sort(key=lambda x: x["start_ns"])
                        return sorted(llmobs_requests, key=lambda t: t[0]["start_ns"])
                    return llmobs_requests
            time.sleep(0.1)
        raise ValueError(
            f"Number ({num}) of traces not available from test agent, got {num_received}:\n{llmobs_requests}"
        )

    def wait_for_llmobs_evaluations_requests(self, num: int, *, wait_loops: int = 30) -> list[Any]:
        """Wait for `num` LLMobs evaluations requests to be received from the test agent."""
        num_received = None
        llmobs_evaluations_requests = []
        for _ in range(wait_loops):
            try:
                llmobs_evaluations_requests = self.llmobs_evaluations_requests()
            except requests.exceptions.RequestException:
                pass
            else:
                num_received = len(llmobs_evaluations_requests)
                if num_received == num:
                    return llmobs_evaluations_requests
            time.sleep(0.1)
        raise ValueError(
            f"""Number ({num}) of LLMobs evaluations requests not available from test agent, got {num_received}:
            {llmobs_evaluations_requests}"""
        )


class TestImage:
    """Abstracts a docker image. TODO: share this with parametric tests"""

    def __init__(
        self,
        dockerfile: str,
        build_args: dict[str, str],
        tag: str,
        container_name: str,
        container_volumes: dict[str, str],
        container_env: dict[str, str],
    ):
        self.dockerfile = dockerfile
        self.build_args = build_args
        self.tag = tag

        self.container_name = container_name
        self.container_volumes = container_volumes
        self.container_env: dict[str, str] = dict(container_env)

    def build(self, host_log_folder: str, github_token_file: str) -> None:
        log_path = f"{host_log_folder}/outputs/docker_build_log.log"
        Path.mkdir(Path(log_path).parent, exist_ok=True, parents=True)

        with open(log_path, "w+", encoding="utf-8") as log_file:
            docker_bin = shutil.which("docker")

            if docker_bin is None:
                raise FileNotFoundError("Docker not found in PATH")

            cmd = [
                docker_bin,
                "build",
                "--progress=plain",
            ]

            if github_token_file and github_token_file.strip():
                cmd += ["--secret", f"id=github_token,src={github_token_file}"]

            for name, value in self.build_args.items():
                cmd += ["--build-arg", f"{name}={value}"]

            cmd += [
                "-t",
                self.tag,
                "-f",
                self.dockerfile,
                ".",
            ]
            log_file.write(f"running {cmd}\n")
            log_file.flush()

            env = os.environ.copy()
            env["DOCKER_SCAN_SUGGEST"] = "false"

            timeout = 600

            p = subprocess.run(
                cmd,
                text=True,
                stdout=log_file,
                stderr=log_file,
                env=env,
                timeout=timeout,
                check=False,
            )

            if p.returncode != 0:
                pytest.exit(f"Failed to build framework test server image. See {log_path} for details", 1)


class FrameworkTestImage(TestImage):
    """Abstracts the docker image that ship the tested tracer+framework."""

    def __init__(
        self,
        library: str,
        framework: str,
        framework_version: str,
        container_env: dict[str, str],
        container_volumes: dict[str, str],
    ):
        self.library = library
        self.framework = framework
        self.framework_version = framework_version
        super().__init__(
            dockerfile=f"utils/build/docker/{library}/{framework}.Dockerfile",
            build_args={"FRAMEWORK_VERSION": framework_version},
            tag=f"{library}-test-library-{framework}-{framework_version}",
            container_name=f"{library}-test-library-{framework}-{framework_version}",
            container_volumes=container_volumes,
            container_env=container_env,
        )

    def get_container(
        self, worker_id: str, test_id: str, test_agent_container_name: str, test_agent_port: int
    ) -> "FrameworkTestContainer":
        return FrameworkTestContainer(
            self,
            name=f"{self.container_name}-{test_id}",
            host_port=_get_host_port(worker_id, 4500),
            test_agent_container_name=test_agent_container_name,
            test_agent_port=test_agent_port,
        )


class FrameworkTestContainer:
    """Abstracts the docker container that ship the tested tracer+framework."""

    def __init__(
        self,
        server: FrameworkTestImage,
        name: str,
        host_port: int,
        test_agent_container_name: str,
        test_agent_port: int,
    ):
        self.server = server
        self.name = name
        self.environment = dict(server.container_env)
        self.volumes = dict(server.container_volumes)
        self.container_port: int = 8080
        self.host_port = host_port

        # TODO : we should not have to set those three values
        self.environment["DD_TRACE_AGENT_URL"] = f"http://{test_agent_container_name}:{test_agent_port}"
        self.environment["DD_AGENT_HOST"] = test_agent_container_name
        self.environment["DD_TRACE_AGENT_PORT"] = str(test_agent_port)

        self.environment["FRAMEWORK_TEST_CLIENT_SERVER_PORT"] = str(self.container_port)

    @contextlib.contextmanager
    def run(
        self,
        network: str,
        log_file: TextIO,
    ) -> Generator["FrameworkTestClient", None, None]:
        with docker_run(
            image=self.server.tag,
            name=self.name,
            env=self.environment,
            volumes=self.volumes,
            network=network,
            ports={f"{self.container_port}/tcp": self.host_port},
            log_file=log_file,
        ) as container:
            test_server_timeout = 60
            client = FrameworkTestClient(f"http://localhost:{self.host_port}", test_server_timeout, container)

            yield client


class FrameworkTestClient:
    def __init__(self, url: str, timeout: int, container: Container):
        self._base_url = url
        self._session = requests.Session()
        self.container = container
        self.timeout = timeout

        # wait for server to start
        self._wait(timeout)

    def container_restart(self):
        self.container.restart()
        self._wait(self.timeout)

    def _wait(self, timeout: float):
        delay = 0.01
        for _ in range(int(timeout / delay)):
            try:
                if self.is_alive():
                    break
            except Exception:
                if self.container.status != "running":
                    self._print_logs()
                    message = f"Container {self.container.name} status is {self.container.status}. Please check logs."
                    pytest.fail(message)
            time.sleep(delay)
        else:
            self._print_logs()
            message = f"Timeout of {timeout} seconds exceeded waiting for HTTP server to start. Please check logs."
            pytest.fail(message)

    def is_alive(self) -> bool:
        self.container.reload()
        return (
            self.container.status == "running"
            and self._session.get(self._url("/non-existent-endpoint-to-ping-until-the-server-starts")).status_code
            == HTTPStatus.NOT_FOUND
        )

    def request(self, method: str, url: str, body: dict | None = None) -> requests.Response:
        resp = self._session.request(method, self._url(url), json=body)
        resp.raise_for_status()
        return resp

    def _url(self, path: str) -> str:
        return urllib.parse.urljoin(self._base_url, path)

    def _print_logs(self):
        try:
            logs = self.container.logs().decode("utf-8")
            logger.debug(f"Logs from container {self.container.name}:\n\n{logs}")
        except Exception:
            logger.error(f"Failed to get logs from container {self.container.name}")
