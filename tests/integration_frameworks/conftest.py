import base64
from collections.abc import Generator
import contextlib
import dataclasses
import os
import shutil
import json
import subprocess
import time
from pathlib import Path
from typing import TextIO, TypedDict, Any
import urllib.parse

import requests
import pytest

from utils._context._scenarios.integration_frameworks import FrameworkTestServer
from utils.integration_frameworks._framework_client import FrameworkClient, FrameworkLibraryClient

from utils.parametric.spec.trace import V06StatsPayload
from utils.parametric.spec.trace import Trace

from utils import context, scenarios, logger

# Max timeout in seconds to keep a container running
default_subprocess_run_timeout = 300

IGNORE_PARAMS_FOR_TEST_NAME = (
    "test_agent",
    "test_library",
)


@pytest.fixture
def test_id(request: pytest.FixtureRequest) -> str:
    import uuid

    result = str(uuid.uuid4())[0:6]
    logger.info(f"Test {request.node.nodeid} ID: {result}")
    return result


class AgentRequest(TypedDict):
    method: str
    url: str
    headers: dict[str, str]
    body: str


class AgentRequestV06Stats(AgentRequest):
    body: V06StatsPayload  # type: ignore[misc]


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "snapshot(*args, **kwargs): mark test to run as a snapshot test which sends traces to the test agent"
    )


def _request_token(request: pytest.FixtureRequest) -> str:
    token = ""
    token += request.module.__name__
    token += f".{request.cls.__name__}" if request.cls else ""
    token += f".{request.node.name}"
    return token


@pytest.fixture
def library_env() -> dict[str, str]:
    return {}


@pytest.fixture
def library_extra_command_arguments() -> list[str]:
    return []


@pytest.fixture
def framework_test_server(
    request: pytest.FixtureRequest,
    library_env: dict[str, str],
    library_extra_command_arguments: list[str],
    test_id: str,
) -> FrameworkTestServer:
    """Request level definition of the library test server with the session Docker image built"""
    framework_test_server_image = scenarios.integration_frameworks.framework_test_server_definition
    new_env = dict(library_env)
    scenarios.integration_frameworks.parametrized_tests_metadata[request.node.nodeid] = new_env

    new_env.update(framework_test_server_image.env)

    command = framework_test_server_image.container_cmd

    if len(library_extra_command_arguments) > 0:
        if framework_test_server_image.lang not in ("nodejs", "java", "php"):
            # TODO : all test server should call directly the target without using a sh script
            command += library_extra_command_arguments
        else:
            # temporary workaround for the test server to be able to run the command
            new_env["SYSTEM_TESTS_EXTRA_COMMAND_ARGUMENTS"] = " ".join(library_extra_command_arguments)

    return dataclasses.replace(
        framework_test_server_image,
        container_name=f"{framework_test_server_image.container_name}-{test_id}",
        env=new_env,
    )


@pytest.fixture
def test_server_log_file(
    framework_test_server: FrameworkTestServer, request: pytest.FixtureRequest
) -> Generator[TextIO, None, None]:
    log_path = f"{context.scenario.host_log_folder}/outputs/{request.cls.__name__}/{request.node.name}/server_log.log"
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w+", encoding="utf-8") as f:
        yield f
    request.node.add_report_section(
        "teardown", f"{framework_test_server.lang.capitalize()} Library Output", f"Log file:\n./{log_path}"
    )


class _TestAgentAPI:
    def __init__(self, host: str, agent_port: int, otlp_port: int, pytest_request: pytest.FixtureRequest):
        self.host = host
        self.agent_port = agent_port
        self.otlp_port = otlp_port
        self._session = requests.Session()
        self._pytest_request = pytest_request
        self.log_path = f"{context.scenario.host_log_folder}/outputs/{pytest_request.cls.__name__}/{pytest_request.node.name}/agent_api.log"
        Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)

    def _url(self, path: str) -> str:
        return urllib.parse.urljoin(f"http://{self.host}:{self.agent_port}", path)

    def _write_log(self, log_type: str, json_trace: Any):  # noqa: ANN401
        with open(self.log_path, "a") as log:
            log.write(f"\n{log_type}>>>>\n")
            log.write(json.dumps(json_trace))

    def traces(self, **kwargs: Any) -> list[Trace]:  # noqa: ANN401
        resp = self._session.get(self._url("/test/session/traces"), **kwargs)
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

        if resp.status_code != 200:
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
            if resp.status_code != 200:
                raise RuntimeError(resp.text)

    @contextlib.contextmanager
    def vcr_context(self, cassette_prefix: str = ""):
        """Starts a VCR context manager, which will prefix all recorded cassettes from the test agent with the given prefix.
        If no prefix is provided, the test name will be used.
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

        When sort_by_start=True returned traces are sorted by the span start time to simplify assertions by knowing that returned traces are in the same order as they have been created.
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
            f"Number ({num}) of LLMobs evaluations requests not available from test agent, got {num_received}:\n{llmobs_evaluations_requests}"
        )


@pytest.fixture(scope="session")
def docker() -> str | None:
    """Fixture to ensure docker is ready to use on the system."""
    # Redirect output to /dev/null since we just care if we get a successful response code.
    r = subprocess.run(
        ["docker", "info"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=default_subprocess_run_timeout,
        check=False,
    )
    if r.returncode != 0:
        pytest.exit(
            "Docker is not running and is required to run the shared APM library tests. Start docker and try running the tests again.",
            returncode=1,
        )
    return shutil.which("docker")


@pytest.fixture
def docker_network(test_id: str) -> Generator[str, None, None]:
    network = scenarios.integration_frameworks.create_docker_network(test_id)

    try:
        yield network.name
    finally:
        try:
            network.remove()
        except:
            # It's possible (why?) of having some container not stopped.
            # If it happens, failing here makes stdout tough to understand.
            # Let's ignore this, later calls will clean the mess
            logger.info("Failed to remove network, ignoring the error")


@pytest.fixture
def test_agent_port() -> int:
    """Returns the port exposed inside the agent container"""
    return 8126


@pytest.fixture
def test_agent_log_file(request: pytest.FixtureRequest) -> Generator[TextIO, None, None]:
    log_path = f"{context.scenario.host_log_folder}/outputs/{request.cls.__name__}/{request.node.name}/agent_log.log"
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w+", encoding="utf-8") as f:
        yield f
    request.node.add_report_section("teardown", "Test Agent Output", f"Log file:\n./{log_path}")


@pytest.fixture
def test_agent_container_name(test_id: str) -> str:
    return f"ddapm-test-agent-{test_id}"


@pytest.fixture
def test_agent_hostname(test_agent_container_name: str) -> str:
    return test_agent_container_name


@pytest.fixture
def test_agent_otlp_http_port() -> int:
    return 4318


@pytest.fixture
def test_agent_otlp_grpc_port() -> int:
    return 4317


@pytest.fixture
def test_agent(
    worker_id: str,
    docker_network: str,
    request: pytest.FixtureRequest,
    test_agent_container_name: str,
    test_agent_port: int,
    test_agent_otlp_http_port: int,
    test_agent_otlp_grpc_port: int,
    test_agent_log_file: TextIO,
) -> Generator[_TestAgentAPI, None, None]:
    env = {}
    if os.getenv("DEV_MODE") is not None:
        env["SNAPSHOT_CI"] = "0"

    # (meta_tracer_version_header) Not all clients (go for example) submit the tracer version
    # (trace_content_length) go client doesn't submit content length header
    env["ENABLED_CHECKS"] = "trace_count_header"
    env["OTLP_HTTP_PORT"] = str(test_agent_otlp_http_port)
    env["OTLP_GRPC_PORT"] = str(test_agent_otlp_grpc_port)

    # vcr environment variables
    env["VCR_CASSETTES_DIRECTORY"] = "/vcr-cassettes"

    core_host_port = scenarios.integration_frameworks.get_host_port(worker_id, 4600)
    otlp_http_host_port = scenarios.integration_frameworks.get_host_port(worker_id, 4701)
    otlp_grpc_host_port = scenarios.integration_frameworks.get_host_port(worker_id, 4802)
    ports = {
        f"{test_agent_port}/tcp": core_host_port,
        f"{test_agent_otlp_http_port}/tcp": otlp_http_host_port,
        f"{test_agent_otlp_grpc_port}/tcp": otlp_grpc_host_port,
    }

    with scenarios.integration_frameworks.docker_run(
        image=scenarios.integration_frameworks.TEST_AGENT_IMAGE,
        name=test_agent_container_name,
        command=[],
        env=env,
        volumes={f"{Path.cwd()!s}/snapshots": "/snapshots", f"{Path.cwd()!s}/vcr-cassettes": "/vcr-cassettes"},
        ports=ports,
        log_file=test_agent_log_file,
        network=docker_network,
    ):
        client = _TestAgentAPI("localhost", core_host_port, otlp_http_host_port, pytest_request=request)
        time.sleep(0.2)  # initial wait time, the trace agent takes 200ms to start
        for _ in range(100):
            try:
                resp = client.info()
            except Exception as e:
                logger.debug(f"Wait for 0.1s for the test agent to be ready {e}")
                time.sleep(0.1)
            else:
                if resp["version"] != "test":
                    message = f"""Agent version {resp['version']} is running instead of the test agent.
                    Stop the agent on port {test_agent_port} and try again."""
                    pytest.fail(message, pytrace=False)

                logger.info("Test agent is ready")
                break
        else:
            logger.error("Could not connect to test agent")
            pytest.fail(
                f"Could not connect to test agent, check the log file {test_agent_log_file.name}.", pytrace=False
            )

        # If the snapshot mark is on the test case then do a snapshot test
        marks = [m for m in request.node.iter_markers(name="snapshot")]
        assert len(marks) < 2, "Multiple snapshot marks detected"
        if marks:
            snap = marks[0]
            assert len(snap.args) == 0, "only keyword arguments are supported by the snapshot decorator"
            if "token" not in snap.kwargs:
                snap.kwargs["token"] = _request_token(request).replace(" ", "_").replace(os.path.sep, "_")
            with client.snapshot_context(**snap.kwargs):
                yield client
        else:
            yield client


@pytest.fixture
def test_client(
    worker_id: str,
    docker_network: str,
    test_agent_port: str,
    test_agent_container_name: str,
    framework_test_server: FrameworkTestServer,
    test_server_log_file: TextIO,
) -> Generator[FrameworkClient, None, None]:
    env = {
        "DD_TRACE_DEBUG": "true",
        "DD_TRACE_AGENT_URL": f"http://{test_agent_container_name}:{test_agent_port}",
        "DD_AGENT_HOST": test_agent_container_name,
        "DD_TRACE_AGENT_PORT": test_agent_port,
        "FRAMEWORK_TEST_CLIENT_SERVER_PORT": str(framework_test_server.container_port),
        "DD_TRACE_OTEL_ENABLED": "true",
        # provider api keys
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", "<not-a-real-key>"),
    }

    for k, v in framework_test_server.env.items():
        # Don't set env vars with a value of None
        if v is not None:
            env[k] = v
        elif k in env:
            del env[k]

    framework_test_server.host_port = scenarios.integration_frameworks.get_host_port(worker_id, 4500)

    with scenarios.integration_frameworks.docker_run(
        image=framework_test_server.container_tag,
        name=framework_test_server.container_name,
        command=framework_test_server.container_cmd,
        env=env,
        ports={f"{framework_test_server.container_port}/tcp": framework_test_server.host_port},
        volumes=framework_test_server.volumes,
        log_file=test_server_log_file,
        network=docker_network,
    ) as container:
        framework_test_server.container = container

        test_server_timeout = 60

        if framework_test_server.host_port is None:
            raise RuntimeError("Internal error, no port has been assigned", 1)

        client = FrameworkLibraryClient(
            f"http://localhost:{framework_test_server.host_port}", test_server_timeout, framework_test_server.container
        )

        framework_client = FrameworkClient(client, framework_test_server.lang)
        yield framework_client
