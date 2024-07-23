import base64
import contextlib
import dataclasses
import os
import shutil
import json
import socket
import subprocess
import tempfile
import time
from typing import Dict, Generator, List, TextIO, Tuple, TypedDict
import urllib.parse

import requests
import pytest

from utils.parametric.spec.trace import V06StatsPayload
from utils.parametric.spec.trace import Trace
from utils.parametric.spec.trace import decode_v06_stats
from utils.parametric.spec import remoteconfig
from utils.parametric._library_client import APMLibraryClientGRPC
from utils.parametric._library_client import APMLibraryClientHTTP
from utils.parametric._library_client import APMLibrary

from utils import context, scenarios
from utils.tools import logger

from utils._context._scenarios.parametric import APMLibraryTestServer

# Max timeout in seconds to keep a container running
default_subprocess_run_timeout = 300


@pytest.fixture
def test_id():
    import uuid

    yield str(uuid.uuid4())[0:6]


class AgentRequest(TypedDict):
    method: str
    url: str
    headers: Dict[str, str]
    body: str


class AgentRequestV06Stats(AgentRequest):
    method: str
    url: str
    headers: Dict[str, str]
    body: V06StatsPayload


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "snapshot(*args, **kwargs): mark test to run as a snapshot test which sends traces to the test agent"
    )


def _request_token(request):
    token = ""
    token += request.module.__name__
    token += ".%s" % request.cls.__name__ if request.cls else ""
    token += ".%s" % request.node.name
    return token


@pytest.fixture
def library_env() -> Dict[str, str]:
    return {}


def get_open_port():
    # Not very nice and also not 100% correct but it works for now.
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    s.listen(1)
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def apm_test_server(request, library_env, test_id):
    """Request level definition of the library test server with the session Docker image built"""
    apm_test_server_image = scenarios.parametric.apm_test_server_definition
    new_env = dict(library_env)
    context.scenario.parametrized_tests_metadata[request.node.nodeid] = new_env

    new_env.update(apm_test_server_image.env)
    yield dataclasses.replace(
        apm_test_server_image,
        container_name="%s-%s" % (apm_test_server_image.container_name, test_id),
        env=new_env,
        port=get_open_port(),
    )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()


@pytest.fixture
def test_server_log_file(apm_test_server, request) -> Generator[TextIO, None, None]:
    log_path = f"{context.scenario.host_log_folder}/outputs/{request.cls.__name__}/{request.node.name}/server_log.log"
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w+") as f:
        yield f
        f.seek(0)
        request.node._report_sections.append(
            ("teardown", f"{apm_test_server.lang.capitalize()} Library Output", "".join(f.readlines()))
        )


class _TestAgentAPI:
    def __init__(self, base_url: str, pytest_request: None):
        self._base_url = base_url
        self._session = requests.Session()
        self._pytest_request = pytest_request
        self.log_path = f"{context.scenario.host_log_folder}/outputs/{pytest_request.cls.__name__}/{pytest_request.node.name}/agent_api.log"
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def _url(self, path: str) -> str:
        return urllib.parse.urljoin(self._base_url, path)

    def _write_log(self, type, json_trace):
        with open(self.log_path, "a") as log:
            log.write(f"\n{type}>>>>\n")
            log.write(json.dumps(json_trace))

    def traces(self, clear=False, **kwargs):
        resp = self._session.get(self._url("/test/session/traces"), **kwargs)
        if clear:
            self.clear()
        json = resp.json()
        self._write_log("traces", json)
        return json

    def set_remote_config(self, path, payload):
        resp = self._session.post(
            self._url("/test/session/responses/config/path"), json={"path": path, "msg": payload,},
        )
        assert resp.status_code == 202

    def raw_telemetry(self, clear=False, **kwargs):
        raw_reqs = self.requests()
        reqs = []
        for req in raw_reqs:
            if req["url"].endswith("/telemetry/proxy/api/v2/apmtelemetry"):
                reqs.append(req)
        if clear:
            self.clear()
        return reqs

    def telemetry(self, clear=False, **kwargs):
        resp = self._session.get(self._url("/test/session/apmtelemetry"), **kwargs)
        if clear:
            self.clear()
        return resp.json()

    def tracestats(self, **kwargs):
        resp = self._session.get(self._url("/test/session/stats"), **kwargs)
        json = resp.json()
        self._write_log("tracestats", json)
        return json

    def requests(self, **kwargs) -> List[AgentRequest]:
        resp = self._session.get(self._url("/test/session/requests"), **kwargs)
        json = resp.json()
        self._write_log("requests", json)
        return json

    def rc_requests(self):
        reqs = self.requests()
        rc_reqs = [r for r in reqs if r["url"].endswith("/v0.7/config")]
        for r in rc_reqs:
            r["body"] = json.loads(base64.b64decode(r["body"]).decode("utf-8"))
        return rc_reqs

    def get_tracer_flares(self, **kwargs):
        resp = self._session.get(self._url("/test/session/tracerflares"), **kwargs)
        json = resp.json()
        self._write_log("tracerflares", json)
        return json

    def v06_stats_requests(self) -> List[AgentRequestV06Stats]:
        raw_requests = [r for r in self.requests() if "/v0.6/stats" in r["url"]]
        requests = []
        for raw in raw_requests:
            requests.append(
                AgentRequestV06Stats(
                    method=raw["method"],
                    url=raw["url"],
                    headers=raw["headers"],
                    body=decode_v06_stats(base64.b64decode(raw["body"])),
                )
            )
        return requests

    def clear(self, **kwargs) -> None:
        self._session.get(self._url("/test/session/clear"), **kwargs)

    def info(self, **kwargs):
        resp = self._session.get(self._url("/info"), **kwargs)
        json = resp.json()
        self._write_log("info", json)
        return json

    @contextlib.contextmanager
    def snapshot_context(self, token, ignores=None):
        ignores = ignores or []
        try:
            resp = self._session.get(self._url("/test/session/start?test_session_token=%s" % token))
            if resp.status_code != 200:
                # The test agent returns nice error messages we can forward to the user.
                pytest.fail(resp.text.decode("utf-8"), pytrace=False)
        except Exception as e:
            pytest.fail("Could not connect to test agent: %s" % str(e), pytrace=False)
        else:
            yield self
            # Query for the results of the test.
            resp = self._session.get(
                self._url("/test/session/snapshot?ignores=%s&test_session_token=%s" % (",".join(ignores), token))
            )
            if resp.status_code != 200:
                pytest.fail(resp.text.decode("utf-8"), pytrace=False)

    def wait_for_num_traces(
        self, num: int, clear: bool = False, wait_loops: int = 30, sort_by_start: bool = True
    ) -> List[Trace]:
        """Wait for `num` traces to be received from the test agent.

        Returns after the number of traces has been received or raises otherwise after 2 seconds of polling.

        Returned traces are sorted by the first span start time to simplify assertions for more than one trace by knowing that returned traces are in the same order as they have been created.
        """
        num_received = None
        for i in range(wait_loops):
            try:
                traces = self.traces(clear=False)
            except requests.exceptions.RequestException:
                pass
            else:
                num_received = len(traces)
                if num_received == num:
                    if clear:
                        self.clear()
                    if sort_by_start:
                        for trace in traces:
                            # The testagent may receive spans and trace chunks in any order,
                            # so we sort the spans by start time if needed
                            trace.sort(key=lambda x: x["start"])
                        return sorted(traces, key=lambda trace: trace[0]["start"])
                    return traces
            time.sleep(0.1)
        raise ValueError(
            "Number (%r) of traces not available from test agent, got %r:\n%r" % (num, num_received, traces)
        )

    def wait_for_num_spans(
        self, num: int, clear: bool = False, wait_loops: int = 30, sort_by_start: bool = True
    ) -> List[Trace]:
        """Wait for `num` spans to be received from the test agent.

        Returns after the number of spans has been received or raises otherwise after 2 seconds of polling.

        Returned traces are sorted by the first span start time to simplify assertions for more than one trace by knowing that returned traces are in the same order as they have been created.
        """
        num_received = None
        for i in range(wait_loops):
            try:
                traces = self.traces(clear=False)
            except requests.exceptions.RequestException:
                pass
            else:
                num_received = 0
                for trace in traces:
                    num_received += len(trace)
                if num_received == num:
                    if clear:
                        self.clear()

                    if sort_by_start:
                        for trace in traces:
                            # The testagent may receive spans and trace chunks in any order,
                            # so we sort the spans by start time if needed
                            trace.sort(key=lambda x: x["start"])
                        return sorted(traces, key=lambda trace: trace[0]["start"])
                    return traces
            time.sleep(0.1)
        raise ValueError("Number (%r) of spans not available from test agent, got %r" % (num, num_received))

    def wait_for_telemetry_event(self, event_name: str, clear: bool = False, wait_loops: int = 200):
        """Wait for and return the given telemetry event from the test agent."""
        for i in range(wait_loops):
            try:
                events = self.telemetry(clear=False)
            except requests.exceptions.RequestException:
                pass
            else:
                for event in events:
                    if event["request_type"] == "message-batch":
                        for message in event["payload"]:
                            if message["request_type"] == event_name:
                                if message.get("application", {}).get("language_version") != "SIDECAR":
                                    if clear:
                                        self.clear()
                                    return message
                    elif event["request_type"] == event_name:
                        if event.get("application", {}).get("language_version") != "SIDECAR":
                            if clear:
                                self.clear()
                            return event
            time.sleep(0.01)
        raise AssertionError("Telemetry event %r not found" % event_name)

    def wait_for_rc_apply_state(
        self, product: str, state: remoteconfig.APPLY_STATUS, clear: bool = False, wait_loops: int = 100
    ):
        """Wait for the given RemoteConfig apply state to be received by the test agent."""
        rc_reqs = []
        for i in range(wait_loops):
            try:
                rc_reqs = self.rc_requests()
            except requests.exceptions.RequestException:
                pass
            else:
                # Look for the given apply state in the requests.
                for req in rc_reqs:
                    if req["body"]["client"]["state"].get("config_states") is None:
                        continue
                    for cfg_state in req["body"]["client"]["state"]["config_states"]:
                        if cfg_state["product"] == product and cfg_state["apply_state"] == state:
                            if clear:
                                self.clear()
                            return cfg_state
            time.sleep(0.01)
        raise AssertionError("No RemoteConfig apply status found, got requests %r" % rc_reqs)

    def wait_for_rc_capabilities(self, capabilities: List[int] = [], wait_loops: int = 100):
        """Wait for the given RemoteConfig apply state to be received by the test agent."""
        rc_reqs = []
        capabilities_seen = set()
        for i in range(wait_loops):
            try:
                rc_reqs = self.rc_requests()
            except requests.exceptions.RequestException:
                pass
            else:
                # Look for capabilities in the requests.
                for req in rc_reqs:
                    raw_caps = req["body"]["client"].get("capabilities")
                    if raw_caps:
                        # Capabilities can be a base64 encoded string or an array of numbers. This is due
                        # to the Go json library used in the trace agent accepting and being able to decode
                        # both: https://go.dev/play/p/fkT5Q7GE5VD

                        # byte-array:
                        if isinstance(raw_caps, list):
                            decoded_capabilities = bytes(raw_caps)
                        # base64-encoded string:
                        else:
                            decoded_capabilities = base64.b64decode(raw_caps)
                        int_capabilities = int.from_bytes(decoded_capabilities, byteorder="big")
                        capabilities_seen.add(remoteconfig.human_readable_capabilities(int_capabilities))
                        if all((int_capabilities >> c) & 1 for c in capabilities):
                            return int_capabilities
            time.sleep(0.01)
        raise AssertionError("No RemoteConfig capabilities found, got capabilites %r" % capabilities_seen)

    def wait_for_tracer_flare(self, case_id: str = None, clear: bool = False, wait_loops: int = 100):
        """Wait for the tracer-flare to be received by the test agent."""
        for i in range(wait_loops):
            try:
                tracer_flares = self.get_tracer_flares()
            except requests.exceptions.RequestException:
                pass
            else:
                # Look for the given case_id in the tracer-flares.
                for tracer_flare in tracer_flares:
                    if case_id is None or tracer_flare["case_id"] == case_id:
                        if clear:
                            self.clear()
                        return tracer_flare
            time.sleep(0.01)
        raise AssertionError("No tracer-flare received")


@contextlib.contextmanager
def docker_run(
    image: str,
    name: str,
    cmd: List[str],
    env: Dict[str, str],
    volumes: List[Tuple[str, str]],
    ports: List[Tuple[str, str]],
    log_file: TextIO,
    network_name: str,
) -> Generator[None, None, None]:
    _cmd: List[str] = [
        shutil.which("docker"),
        "run",
        "-d",
        "--rm",
        "--name=%s" % name,
        "--network=%s" % network_name,
    ]
    for k, v in env.items():
        _cmd.extend(["-e", "%s=%s" % (k, v)])
    for k, v in volumes:
        _cmd.extend(["-v", "%s:%s" % (k, v)])
    for k, v in ports:
        _cmd.extend(["-p", f"127.0.0.1:{k}:{v}"])
    _cmd += [image]
    _cmd.extend(cmd)

    log_file.write("$ " + " ".join(_cmd) + "\n")
    log_file.flush()
    docker = shutil.which("docker")

    # Run the docker container
    r = subprocess.run(_cmd, stdout=log_file, stderr=log_file, timeout=default_subprocess_run_timeout)
    if r.returncode != 0:
        log_file.flush()
        pytest.fail(
            "Could not start docker container %r with image %r, see the log file %r" % (name, image, log_file.name),
            pytrace=False,
        )

    # Start collecting the logs of the container
    _cmd = [
        "docker",
        "logs",
        "-f",
        name,
    ]
    docker_logs = subprocess.Popen(_cmd, stdout=log_file, stderr=log_file)
    try:
        yield
    finally:
        docker_logs.kill()
        _cmd = [docker, "kill", name]
        log_file.write("\n\n\n$ %s\n" % " ".join(_cmd))
        log_file.flush()
        # FIXME there is some weird problem when we try to kill the container. The test is blocked and the container was not killed
        # logger.stdout(f"Parametric: docker_run: before kill the container: {log_file}")
        try:
            subprocess.run(_cmd, stdout=log_file, stderr=log_file, check=True, timeout=30)
        except Exception as e:
            logger.stdout(f"Parametric docker_run ERROR for {cmd}  -  {log_file}")
            logger.error(e)
        # logger.stdout(f"Parametric: docker_run: After kill the container: {log_file} ")


@pytest.fixture(scope="session")
def docker() -> str:
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
        pytest.fail(
            "Docker is not running and is required to run the shared APM library tests. Start docker and try running the tests again."
        )
    return shutil.which("docker")


@pytest.fixture()
def docker_network_log_file(request) -> TextIO:
    with tempfile.NamedTemporaryFile(mode="w+") as f:
        yield f


@pytest.fixture()
def docker_network_name(test_id) -> str:
    return "apm_shared_tests_network_%s" % test_id


@pytest.fixture()
def docker_network(docker: str, docker_network_log_file: TextIO, docker_network_name: str) -> str:
    # Initial check to see if docker network already exists
    cmd = [
        docker,
        "network",
        "inspect",
        docker_network_name,
    ]
    docker_network_log_file.write("$ " + " ".join(cmd) + "\n\n")
    docker_network_log_file.flush()
    r = subprocess.run(cmd, stderr=docker_network_log_file, timeout=default_subprocess_run_timeout)
    if r.returncode not in (0, 1):  # 0 = network exists, 1 = network does not exist
        pytest.fail(
            "Could not check for docker network %r, error: %r" % (docker_network_name, r.stderr), pytrace=False,
        )
    elif r.returncode == 1:
        cmd = [
            shutil.which("docker"),
            "network",
            "create",
            "--driver",
            "bridge",
            docker_network_name,
        ]
        docker_network_log_file.write("$ " + " ".join(cmd) + "\n\n")
        docker_network_log_file.flush()
        r = subprocess.run(
            cmd,
            stdout=docker_network_log_file,
            stderr=docker_network_log_file,
            timeout=default_subprocess_run_timeout,
            check=False,
        )
        if r.returncode != 0:
            # TODO : as it runs in CI, temp file are mnstly not available -> write this in stdout
            pytest.fail(
                "Could not create docker network %r, see the log file %r"
                % (docker_network_name, docker_network_log_file.name),
                pytrace=False,
            )
    yield docker_network_name
    cmd = [
        shutil.which("docker"),
        "network",
        "rm",
        docker_network_name,
    ]
    docker_network_log_file.write("$ " + " ".join(cmd) + "\n\n")
    docker_network_log_file.flush()
    r = subprocess.run(
        cmd,
        stdout=docker_network_log_file,
        stderr=docker_network_log_file,
        timeout=default_subprocess_run_timeout,
        check=False,
    )
    if r.returncode != 0:
        pytest.fail(
            "Failed to remove docker network %r, see the log file %r"
            % (docker_network_name, docker_network_log_file.name),
            pytrace=False,
        )


@pytest.fixture
def test_agent_port() -> str:
    return "8126"


@pytest.fixture
def test_agent_log_file(request) -> Generator[TextIO, None, None]:
    log_path = f"{context.scenario.host_log_folder}/outputs/{request.cls.__name__}/{request.node.name}/agent_log.log"
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w+") as f:
        yield f
        f.seek(0)
        agent_output = ""
        for line in f.readlines():
            # Remove log lines that are not relevant to the test
            if "GET /test/session/traces" in line:
                continue
            if "GET /test/session/requests" in line:
                continue
            if "GET /test/session/clear" in line:
                continue
            if "GET /test/session/apmtelemetry" in line:
                continue
            agent_output += line
        request.node._report_sections.append(("teardown", f"Test Agent Output", agent_output))


@pytest.fixture
def test_agent_container_name(test_id) -> str:
    return "ddapm-test-agent-%s" % test_id


@pytest.fixture
def test_agent_hostname(test_agent_container_name: str) -> str:
    return test_agent_container_name


@pytest.fixture
def test_agent(
    docker_network: str, request, test_agent_container_name: str, test_agent_port, test_agent_log_file: TextIO,
):
    env = {}
    if os.getenv("DEV_MODE") is not None:
        env["SNAPSHOT_CI"] = "0"

    # (meta_tracer_version_header) Not all clients (go for example) submit the tracer version
    # (trace_content_length) go client doesn't submit content length header
    env["ENABLED_CHECKS"] = "trace_count_header"

    test_agent_external_port = get_open_port()
    with docker_run(
        image="ghcr.io/datadog/dd-apm-test-agent/ddapm-test-agent:v1.17.0",
        name=test_agent_container_name,
        cmd=[],
        env=env,
        volumes=[("%s/snapshots" % os.getcwd(), "/snapshots")],
        ports=[(test_agent_external_port, test_agent_port)],
        log_file=test_agent_log_file,
        network_name=docker_network,
    ):
        client = _TestAgentAPI(base_url="http://localhost:%s" % test_agent_external_port, pytest_request=request)
        # Wait for the agent to start (potentially have to pull the image from the registry)
        for i in range(30):
            try:
                resp = client.info()
            except requests.exceptions.ConnectionError:
                time.sleep(0.5)
            else:
                if resp["version"] != "test":
                    pytest.fail(
                        "Agent version %r is running instead of the test agent. Stop the agent on port %r and try again."
                        % (resp["version"], test_agent_port)
                    )
                break
        else:
            with open(test_agent_log_file.name) as f:
                logger.error(f"Could not connect to test agent: {f.read()}")
            pytest.fail(
                "Could not connect to test agent, check the log file %r." % test_agent_log_file.name, pytrace=False
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
def test_server(
    docker,
    docker_network: str,
    tmp_path,
    test_agent_port: str,
    test_agent_container_name: str,
    apm_test_server: APMLibraryTestServer,
    test_server_log_file: TextIO,
):
    env = {
        "DD_TRACE_DEBUG": "true",
        "DD_TRACE_AGENT_URL": "http://%s:%s" % (test_agent_container_name, test_agent_port),
        "DD_AGENT_HOST": test_agent_container_name,
        "DD_TRACE_AGENT_PORT": test_agent_port,
        "APM_TEST_CLIENT_SERVER_PORT": apm_test_server.port,
    }
    test_server_env = {}
    for k, v in apm_test_server.env.items():
        # Don't set `None` env vars.
        if v is not None:
            test_server_env[k] = v
    env.update(test_server_env)

    with docker_run(
        image=apm_test_server.container_tag,
        name=apm_test_server.container_name,
        cmd=apm_test_server.container_cmd,
        env=env,
        ports=[(apm_test_server.port, apm_test_server.port)],
        volumes=apm_test_server.volumes,
        log_file=test_server_log_file,
        network_name=docker_network,
    ):
        yield apm_test_server


@pytest.fixture
def test_server_timeout() -> int:
    return 60


@pytest.fixture
def test_library(test_server: APMLibraryTestServer, test_server_timeout: int) -> Generator[APMLibrary, None, None]:
    if test_server.protocol == "grpc":
        client = APMLibraryClientGRPC("localhost:%s" % test_server.port, test_server_timeout)
    elif test_server.protocol == "http":
        client = APMLibraryClientHTTP("http://localhost:%s" % test_server.port, test_server_timeout)
    else:
        raise ValueError("interface %s not supported" % test_server.protocol)
    tracer = APMLibrary(client, test_server.lang)
    yield tracer
