import base64
import contextlib
import dataclasses
import os
import shutil
import socket
import subprocess
import tempfile
import time
from typing import Callable, Dict, Generator, List, Literal, TextIO, Tuple, TypedDict, Union
import urllib.parse

import requests
import pytest

from utils.parametric.spec.trace import V06StatsPayload
from utils.parametric.spec.trace import Trace
from utils.parametric.spec.trace import decode_v06_stats
from utils.parametric._library_client import APMLibraryClientGRPC
from utils.parametric._library_client import APMLibraryClientHTTP
from utils.parametric._library_client import APMLibrary
from tests.parametric.conftest import (
    test_id,
    AgentRequest,
    AgentRequestV06Stats,
    _request_token,
    APMLibraryTestServer,
    library_env,
    node_library_factory,
    python_library_factory,
    python_http_library_factory,
    golang_library_factory,
    dotnet_library_factory,
    java_library_factory,
    php_library_factory,
    ruby_library_factory,
    get_open_port,
    pytest_runtest_makereport,
    test_server_log_file,
    test_server,
)


@pytest.fixture(autouse=True)
def skip_library(request, apm_test_server):
    overrides = set([s.strip() for s in os.getenv("OVERRIDE_SKIPS", "").split(",")])
    for marker in request.node.iter_markers("skip_library"):
        skip_library = marker.args[0]
        reason = marker.args[1]

        # Have to use `originalname` since `name` will contain the parameterization
        # eg. test_case[python]
        if apm_test_server.lang == skip_library and request.node.originalname not in overrides:
            pytest.skip("skipped {} on {}: {}".format(request.function.__name__, apm_test_server.lang, reason))


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "snapshot(*args, **kwargs): mark test to run as a snapshot test which sends traces to the test agent"
    )
    config.addinivalue_line("markers", "skip_library(library, reason): skip test for library")


ClientLibraryServerFactory = Callable[[Dict[str, str]], APMLibraryTestServer]

_libs = {
    "dotnet": dotnet_library_factory,
    "golang": golang_library_factory,
    "java": java_library_factory,
    "nodejs": node_library_factory,
    "php": php_library_factory,
    "python": python_library_factory,
    "python_http": python_http_library_factory,
    "ruby": ruby_library_factory,
}
_enabled_libs: List[Tuple[str, ClientLibraryServerFactory]] = []
for _lang in os.getenv("CLIENTS_ENABLED", "dotnet,golang,java,nodejs,php,python,python_http,ruby").split(","):
    if _lang not in _libs:
        raise ValueError("Incorrect client %r specified, must be one of %r" % (_lang, ",".join(_libs.keys())))
    _enabled_libs.append((_lang, _libs[_lang]))


@pytest.fixture(
    params=list(factory for lang, factory in _enabled_libs), ids=list(lang for lang, factory in _enabled_libs)
)
def apm_test_server(request, library_env, test_id):
    # Have to do this funky request.param stuff as this is the recommended way to do parametrized fixtures
    # in pytest.
    apm_test_library = request.param

    yield apm_test_library(library_env, test_id, get_open_port())


class _TestAgentAPI:
    def __init__(self, base_url: str):
        self._base_url = base_url
        self._session = requests.Session()

    def _url(self, path: str) -> str:
        return urllib.parse.urljoin(self._base_url, path)

    def traces(self, clear=False, **kwargs):
        resp = self._session.get(self._url("/test/session/traces"), **kwargs)
        if clear:
            self.clear()
        return resp.json()

    def tracestats(self, **kwargs):
        resp = self._session.get(self._url("/test/session/stats"), **kwargs)
        return resp.json()

    def requests(self, **kwargs) -> List[AgentRequest]:
        resp = self._session.get(self._url("/test/session/requests"), **kwargs)
        return resp.json()

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
        return resp.json()

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

    def wait_for_num_traces(self, num: int, clear: bool = False, wait_loops: int = 20) -> List[Trace]:
        """Wait for `num` to be received from the test agent.

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
                    return sorted(traces, key=lambda trace: trace[0]["start"])
            time.sleep(0.1)
        raise ValueError("Number (%r) of traces not available from test agent, got %r" % (num, num_received))


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
):
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
        _cmd.extend(["-p", "%s:%s" % (k, v)])
    _cmd += [image]
    _cmd.extend(cmd)

    log_file.write("$ " + " ".join(_cmd) + "\n")
    log_file.flush()
    docker = shutil.which("docker")

    # Run the docker container
    r = subprocess.run(_cmd, stdout=log_file, stderr=log_file)
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
        subprocess.run(
            _cmd, stdout=log_file, stderr=log_file, check=True,
        )


@pytest.fixture(scope="session")
def docker() -> str:
    """Fixture to ensure docker is ready to use on the system."""
    # Redirect output to /dev/null since we just care if we get a successful response code.
    r = subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
    r = subprocess.run(cmd, stderr=docker_network_log_file)
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
        r = subprocess.run(cmd, stdout=docker_network_log_file, stderr=docker_network_log_file)
        if r.returncode != 0:
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
    r = subprocess.run(cmd, stdout=docker_network_log_file, stderr=docker_network_log_file)
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
    with tempfile.NamedTemporaryFile(mode="w+") as f:
        yield f
        f.seek(0)
        request.node._report_sections.append(("teardown", f"Test Agent Output", "".join(f.readlines())))


@pytest.fixture
def test_agent_container_name(test_id) -> str:
    return "ddapm-test-agent-%s" % test_id


@pytest.fixture
def test_agent(
    docker_network: str, request, test_agent_container_name: str, test_agent_port, test_agent_log_file: TextIO,
):
    env = {}
    if os.getenv("DEV_MODE") is not None:
        env["SNAPSHOT_CI"] = "0"

    # Not all clients (go for example) submit the tracer version
    # go client doesn't submit content length header
    env["DISABLED_CHECKS"] = "meta_tracer_version_header,trace_content_length"

    test_agent_external_port = get_open_port()
    with docker_run(
        image="ghcr.io/datadog/dd-apm-test-agent/ddapm-test-agent:latest",
        name=test_agent_container_name,
        cmd=[],
        env=env,
        volumes=[("%s/snapshots" % os.getcwd(), "/snapshots")],
        ports=[(test_agent_external_port, test_agent_port)],
        log_file=test_agent_log_file,
        network_name=docker_network,
    ):
        client = _TestAgentAPI(base_url="http://localhost:%s" % test_agent_external_port)
        # Wait for the agent to start
        for i in range(20):
            try:
                resp = client.info()
            except requests.exceptions.ConnectionError:
                time.sleep(0.1)
            else:
                if resp["version"] != "test":
                    pytest.fail(
                        "Agent version %r is running instead of the test agent. Stop the agent on port %r and try again."
                        % (resp["version"], test_agent_port)
                    )
                break
        else:
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
