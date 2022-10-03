import base64
import contextlib
import dataclasses
import os
import shutil
import subprocess
import sys
import time
from typing import Callable, Dict, Generator, List, TextIO, Tuple, TypedDict
import urllib.parse

import grpc

import requests
import pytest

from parametric.protos import apm_test_client_pb2 as pb
from parametric.protos import apm_test_client_pb2_grpc
from parametric.spec.trace import V06StatsPayload
from parametric.spec.trace import decode_v06_stats


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


@pytest.fixture(autouse=True)
def skip_library(request, apm_test_server):
    for marker in request.node.iter_markers("skip_library"):
        skip_library = marker.args[0]
        reason = marker.args[1]
        if apm_test_server.lang == skip_library:
            pytest.skip("skipped {} on {}: {}".format(request.function.__name__, apm_test_server.lang, reason))


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "snapshot(*args, **kwargs): mark test to run as a snapshot test which sends traces to the test agent"
    )
    config.addinivalue_line("markers", "skip_library(library, reason): skip test for library")


def _request_token(request):
    token = ""
    token += request.module.__name__
    token += ".%s" % request.cls.__name__ if request.cls else ""
    token += ".%s" % request.node.name
    return token


@dataclasses.dataclass
class APMLibraryTestServer:
    lang: str
    container_name: str
    container_tag: str
    container_img: str
    container_cmd: List[str]
    container_build_dir: str
    port: str = "50051"
    env: Dict[str, str] = dataclasses.field(default_factory=dict)
    volumes: List[Tuple[str, str]] = dataclasses.field(default_factory=list)


@pytest.fixture
def apm_test_server_env() -> Dict[str, str]:
    return {}


ClientLibraryServerFactory = Callable[[Dict[str, str]], APMLibraryTestServer]


def python_library_server_factory(env: Dict[str, str]) -> APMLibraryTestServer:
    python_dir = os.path.join(os.path.dirname(__file__), "apps", "python")
    python_package = os.getenv("PYTHON_DDTRACE_PACKAGE", "ddtrace")
    return APMLibraryTestServer(
        lang="python",
        container_name="python-test-library",
        container_tag="py39-test-library",
        container_img="""
FROM datadog/dd-trace-py:buster
WORKDIR /client
RUN pyenv global 3.9.11
RUN python3.9 -m pip install grpcio==1.46.3 grpcio-tools==1.46.3
RUN python3.9 -m pip install %s
"""
        % (python_package,),
        container_cmd="python3.9 -m apm_test_client".split(" "),
        container_build_dir=python_dir,
        volumes=[(os.path.join(python_dir, "apm_test_client"), "/client/apm_test_client"),],
        env=env,
    )


def golang_library_server_factory(env: Dict[str, str]):
    go_appdir = os.path.join("apps", "golang")
    go_dir = os.path.join(os.path.dirname(__file__), go_appdir)
    go_reldir = os.path.join("parametric", go_appdir)
    return APMLibraryTestServer(
        lang="golang",
        container_name="go-test-library",
        container_tag="go118-test-library",
        container_img=f"""
FROM golang:1.18
WORKDIR /client
COPY {go_reldir}/go.mod /client
COPY {go_reldir}/go.sum /client
RUN go mod download
COPY {go_reldir} /client
RUN go get gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer
RUN go install
""",
        container_cmd=["main"],
        container_build_dir=go_dir,
        volumes=[(os.path.join(go_dir), "/client"),],
        env=env,
    )


def dotnet_library_server_factory(env: Dict[str, str]):
    dotnet_appdir = os.path.join("apps", "dotnet")
    dotnet_dir = os.path.join(os.path.dirname(__file__), dotnet_appdir)
    dotnet_reldir = os.path.join("parametric", dotnet_appdir)
    env["ASPNETCORE_URLS"] = "http://localhost:50051"
    return APMLibraryTestServer(
        lang="dotnet",
        container_name="dotnet-test-client",
        container_tag="dotnet6_0-test-client",
        container_img=f"""
FROM mcr.microsoft.com/dotnet/sdk:6.0
WORKDIR /client
COPY ["{dotnet_reldir}/ApmTestClient.csproj", "."]
RUN dotnet restore "./ApmTestClient.csproj"
COPY {dotnet_reldir} .
WORKDIR "/client/."
""",
        container_cmd=["dotnet", "run"],
        container_build_dir=dotnet_dir,
        volumes=[(os.path.join(dotnet_dir), "/client"),],
        env=env,
    )


_libs = {
    "dotnet": dotnet_library_server_factory,
    "golang": golang_library_server_factory,
    "python": python_library_server_factory,
}
_enabled_libs: List[Tuple[str, ClientLibraryServerFactory]] = []
for _lang in os.getenv("CLIENTS_ENABLED", "python,dotnet,golang").split(","):
    if _lang not in _libs:
        raise ValueError("Incorrect client %r specified, must be one of %r" % (_lang, ",".join(_libs.keys())))
    _enabled_libs.append((_lang, _libs[_lang]))


@pytest.fixture(
    params=list(factory for lang, factory in _enabled_libs), ids=list(lang for lang, factory in _enabled_libs)
)
def apm_test_server(request, apm_test_server_env):
    # Have to do this funky request.param stuff as this is the recommended way to do parametrized fixtures
    # in pytest.
    apm_test_server_factory = request.param
    yield apm_test_server_factory(apm_test_server_env)


@pytest.fixture
def test_server_log_file(apm_test_server, tmp_path) -> TextIO:
    # timestr = time.strftime("%Y%m%d-%H%M%S")
    # yield tmp_path / ("%s_%s.out" % (apm_test_server.container_name, timestr))
    return sys.stderr


class _TestAgentAPI:
    def __init__(self, base_url: str):
        self._base_url = base_url
        self._session = requests.Session()

    def _url(self, path: str) -> str:
        return urllib.parse.urljoin(self._base_url, path)

    def traces(self, **kwargs):
        resp = self._session.get(self._url("/test/session/traces"), **kwargs)
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

    def clear(self, **kwargs):
        resp = self._session.get(self._url("/test/session/clear"), **kwargs)
        return resp.json()

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
                pytest.fail(to_unicode(resp.text), pytrace=False)
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
    log_file.write("$ " + " ".join(_cmd) + "\n\n")
    log_file.flush()
    docker = shutil.which("docker")

    # Run the docker container
    r = subprocess.run(_cmd, stdout=log_file, stderr=log_file)
    if r.returncode != 0:
        pytest.fail(
            "Could not start docker container %r with image %r, see the log file %r" % (name, image, log_file),
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
        log_file.write(" ".join(_cmd) + "\n\n")
        log_file.flush()
        subprocess.run(
            _cmd, stdout=log_file, stderr=log_file, check=True,
        )


@pytest.fixture
def docker() -> None:
    """Fixture to ensure docker is ready to use on the system."""
    # Redirect output to /dev/null since we just care if we get a successful response code.
    r = subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if r.returncode != 0:
        pytest.fail(
            "Docker is not running and is required to run the shared APM library tests. Start docker and try running the tests again."
        )


@pytest.fixture
def docker_network_log_file() -> TextIO:
    return sys.stderr


@pytest.fixture
def docker_network_name() -> str:
    return "apm_shared_tests_network"


@pytest.fixture
def docker_network(docker_network_log_file: TextIO, docker_network_name: str) -> str:
    # Initial check to see if docker network already exists
    cmd = [
        shutil.which("docker"),
        "network",
        "inspect",
        docker_network_name,
    ]
    docker_network_log_file.write("$ " + " ".join(cmd) + "\n\n")
    docker_network_log_file.flush()
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
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
                % (docker_network_name, docker_network_log_file),
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
            "Failed to remove docker network %r, see the log file %r" % (docker_network_name, docker_network_log_file),
            pytrace=False,
        )


@pytest.fixture
def test_agent_port() -> str:
    return "8126"


@pytest.fixture
def test_agent_log_file() -> TextIO:
    return sys.stderr


@pytest.fixture
def test_agent_container_name() -> str:
    return "ddapm-test-agent"


@pytest.fixture
def test_agent(
    docker,
    docker_network: str,
    request,
    tmp_path,
    test_agent_container_name: str,
    test_agent_port,
    test_agent_log_file: TextIO,
):
    env = {}
    if os.getenv("DEV_MODE") is not None:
        env["SNAPSHOT_CI"] = "0"

    # Not all clients (go for example) submit the tracer version
    # go client doesn't submit content length header
    env["DISABLED_CHECKS"] = "meta_tracer_version_header,trace_content_length"

    with docker_run(
        image="ghcr.io/datadog/dd-apm-test-agent/ddapm-test-agent:latest",
        name=test_agent_container_name,
        cmd=[],
        env=env,
        volumes=[("%s/snapshots" % os.getcwd(), "/snapshots")],
        ports=[(test_agent_port, test_agent_port)],
        log_file=test_agent_log_file,
        network_name=docker_network,
    ):
        client = _TestAgentAPI(base_url="http://localhost:%s" % test_agent_port)
        # Wait for the agent to start
        for i in range(200):
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
            pytest.fail("Could not connect to test agent, check the log file %r." % test_agent_log_file, pytrace=False)

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
    # Write dockerfile to the build directory
    # Note that this needs to be done as the context cannot be
    # specified if Dockerfiles are read from stdin.
    dockf_path = os.path.join(apm_test_server.container_build_dir, "Dockerfile")
    test_server_log_file.write("writing dockerfile %r\n" % dockf_path)
    with open(dockf_path, "w") as dockf:
        dockf.write(apm_test_server.container_img)
    # Build the container
    docker = shutil.which("docker")
    root_path = ".."
    cmd = [
        docker,
        "build",
        "--progress=plain",  # use plain output to assist in debugging
        "-t",
        apm_test_server.container_tag,
        "-f",
        dockf_path,
        ".",
    ]
    test_server_log_file.write("running %r in %r\n\n" % (" ".join(cmd), root_path))
    test_server_log_file.flush()
    subprocess.run(
        cmd,
        cwd=root_path,
        stdout=test_server_log_file,
        stderr=test_server_log_file,
        check=True,
        text=True,
        input=apm_test_server.container_img,
    )

    env = {
        "DD_TRACE_DEBUG": "true",
        "DD_TRACE_AGENT_URL": "http://%s:%s" % (test_agent_container_name, test_agent_port),
        "DD_AGENT_HOST": test_agent_container_name,
        "DD_TRACE_AGENT_PORT": test_agent_port,
    }
    env.update(apm_test_server.env)

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

    # Clean up generated files
    os.remove(dockf_path)


class _TestSpan:
    def __init__(self, client: apm_test_client_pb2_grpc.APMClientStub, span_id: int):
        self._client = client
        self.span_id = span_id

    def set_meta(self, key: str, val: str):
        self._client.SpanSetMeta(pb.SpanSetMetaArgs(span_id=self.span_id, key=key, value=val,))

    def set_metric(self, key: str, val: float):
        self._client.SpanSetMetric(pb.SpanSetMetricArgs(span_id=self.span_id, key=key, value=val,))

    def set_error(self, typestr: str = "", message: str = "", stack: str = ""):
        self._client.SpanSetError(
            pb.SpanSetErrorArgs(span_id=self.span_id, type=typestr, message=message, stack=stack,)
        )

    def finish(self):
        self._client.FinishSpan(pb.FinishSpanArgs(id=self.span_id,))


class _TestTracer:
    def __init__(self, client: apm_test_client_pb2_grpc.APMClientStub):
        self._client = client

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Only attempt a flush if there was no exception raised.
        if exc_type is None:
            self.flush()

    @contextlib.contextmanager
    def start_span(
        self, name: str, service: str = "", resource: str = "", parent_id: int = 0, typestr: str = "", origin: str = ""
    ) -> Generator[_TestSpan, None, None]:
        resp = self._client.StartSpan(
            pb.StartSpanArgs(
                name=name, service=service, resource=resource, parent_id=parent_id, type=typestr, origin=origin,
            )
        )
        span = _TestSpan(self._client, resp.span_id)
        yield span
        span.finish()

    def flush(self):
        self._client.FlushSpans(pb.FlushSpansArgs())
        self._client.FlushTraceStats(pb.FlushTraceStatsArgs())


@pytest.fixture
def test_server_timeout() -> int:
    return 60


@pytest.fixture
def test_client(test_server: APMLibraryTestServer, test_server_timeout: int) -> Generator[_TestTracer, None, None]:
    channel = grpc.insecure_channel("localhost:%s" % test_server.port)
    grpc.channel_ready_future(channel).result(timeout=test_server_timeout)
    client = apm_test_client_pb2_grpc.APMClientStub(channel)
    tracer = _TestTracer(client)
    yield tracer
