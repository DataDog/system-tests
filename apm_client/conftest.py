import base64
import contextlib
import dataclasses
import os
import shutil
import subprocess
import sys
import time
from typing import Dict, Generator, List, Tuple, TypedDict
import urllib.parse

import grpc

import requests
from ddtrace.internal.compat import to_unicode
import pytest

from apm_client.protos import apm_test_client_pb2 as pb
from apm_client.protos import apm_test_client_pb2_grpc
from .trace import V06StatsPayload
from .trace import decode_v06_stats


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


@dataclasses.dataclass
class APMClientTestServer:
    container_name: str
    container_tag: str
    container_img: str
    container_cmd: List[str]
    container_build_dir: str
    port: str = "50051"
    env: Dict[str, str] = dataclasses.field(default_factory=dict)
    volumes: List[Tuple[str, str]] = dataclasses.field(default_factory=list)


@pytest.fixture
def apm_test_server_env():
    yield {}


def python_library_server_factory(env: Dict[str, str]):
    python_dir = os.path.join(os.path.dirname(__file__), "python")
    return APMClientTestServer(
        container_name="python-test-client",
        container_tag="py39-test-client",
        container_img="""
FROM python:3.9
WORKDIR /client
RUN pip install grpcio==1.46.3 grpcio-tools==1.46.3
RUN pip install ddtrace
""",
        container_cmd="python -m apm_test_client".split(" "),
        container_build_dir=python_dir,
        volumes=[
            (os.path.join(python_dir, "apm_test_client"), "/client/apm_test_client"),
        ],
        env=env,
    )


def golang_library_server_factory(env: Dict[str, str]):
    go_dir = os.path.join(os.path.dirname(__file__), "go")
    return APMClientTestServer(
        container_name="go-test-client",
        container_tag="go118-test-client",
        container_img="""
FROM golang:1.18
WORKDIR /client
COPY go.mod /client
COPY go.sum /client
RUN go mod download
COPY . /client
RUN go get gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer
RUN go install
""",
        container_cmd=["main"],
        container_build_dir=go_dir,
        volumes=[
            (os.path.join(go_dir), "/client"),
        ],
        env=env,
    )


def dotnet_library_server_factory(env: Dict[str, str]):
    dotnet_dir = os.path.join(os.path.dirname(__file__), "dotnet")
    env["ASPNETCORE_URLS"] = "http://localhost:50051"
    return APMClientTestServer(
        container_name="dotnet-test-client",
        container_tag="dotnet6_0-test-client",
        container_img="""
FROM mcr.microsoft.com/dotnet/sdk:6.0
WORKDIR /client
COPY ["ApmTestClient.csproj", "."]
RUN dotnet restore "./ApmTestClient.csproj"
COPY . .
WORKDIR "/client/."
""",
        # container_cmd=["bash", "-c", "go install && main"],
        container_cmd=["dotnet", "run"],
        container_build_dir=dotnet_dir,
        volumes=[
            (os.path.join(dotnet_dir), "/client"),
        ],
        env=env,
    )


@pytest.fixture
def apm_test_server_factory():
    yield python_library_server_factory


@pytest.fixture
def apm_test_server(apm_test_server_factory, apm_test_server_env):
    yield apm_test_server_factory(apm_test_server_env)


@pytest.fixture
def test_server_log_file(apm_test_server, tmp_path):
    timestr = time.strftime("%Y%m%d-%H%M%S")
    yield tmp_path / ("%s_%s.out" % (apm_test_server.container_name, timestr))


class TestAgentAPI:
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
                pytest.fail(to_unicode(resp.text), pytrace=False)


@contextlib.contextmanager
def docker_run(
    image: str,
    name: str,
    cmd: List[str],
    env: Dict[str, str],
    volumes: List[Tuple[str, str]],
    ports: List[Tuple[str, str]],
    log_file_path: str,
):
    _cmd: List[str] = [
        shutil.which("docker"),
        "run",
        "--rm",
        "--name=%s" % name,
    ]
    with open(log_file_path, "w") as f:
        for k, v in env.items():
            _cmd.extend(["-e", "%s=%s" % (k, v)])
        for k, v in volumes:
            _cmd.extend(["-v", "%s:%s" % (k, v)])
        for k, v in ports:
            _cmd.extend(["-p", "%s:%s" % (k, v)])
        _cmd += [image]
        _cmd.extend(cmd)
        f.write(" ".join(_cmd) + "\n\n")
        f.flush()
        docker = shutil.which("docker")
        subprocess.Popen(_cmd, stdout=f, stderr=f)
        try:
            yield
        finally:
            subprocess.run(
                [docker, "kill", name],
                stdout=f,
                stderr=f,
                check=True,
            )


@pytest.fixture
def test_agent(request, tmp_path):
    # Build the container
    log_file_path = tmp_path / "ddapm_test_agent.out"
    print("ddapm_test_agent output: %s" % log_file_path)

    env = {}
    if os.getenv("DEV_MODE") is not None:
        env["SNAPSHOT_CI"] = "0"

    # Not all clients (go for example) submit the tracer version
    # go client doesn't submit content length header
    env["DISABLED_CHECKS"] = "meta_tracer_version_header,trace_content_length"

    with docker_run(
        image="ghcr.io/datadog/dd-apm-test-agent/ddapm-test-agent:latest",
        name="ddapm-test-agent",
        cmd=[],
        env=env,
        volumes=[("%s/snapshots" % os.getcwd(), "/snapshots")],
        ports=[("8126", "8126")],
        log_file_path=log_file_path,
    ):
        client = TestAgentAPI(base_url="http://localhost:8126")
        # Wait for the agent to start
        for i in range(200):
            try:
                client.traces()
            except requests.exceptions.ConnectionError:
                time.sleep(0.1)
            else:
                break
        else:
            pytest.fail("Could not connect to test agent, check the log file %r." % log_file_path, pytrace=False)

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
def test_server(tmp_path, apm_test_server: APMClientTestServer, test_server_log_file):
    print("library output: %s" % test_server_log_file)

    with open(test_server_log_file, "w") as f:
        # Write dockerfile to the build directory
        # Note that this needs to be done as the context cannot be
        # specified if Dockerfiles are read from stdin.
        dockf_path = os.path.join(apm_test_server.container_build_dir, "Dockerfile")
        print("writing dockerfile %r" % dockf_path, file=f)
        with open(dockf_path, "w") as dockf:
            dockf.write(apm_test_server.container_img)
        # Build the container
        docker = shutil.which("docker")
        cmd = [
            docker,
            "build",
            "-t",
            apm_test_server.container_tag,
            ".",
        ]
        print("running %r in %r\n\n" % (" ".join(cmd), apm_test_server.container_build_dir), file=f)
        f.flush()
        subprocess.run(
            cmd,
            cwd=apm_test_server.container_build_dir,
            stdout=f,
            stderr=f,
            check=True,
            text=True,
            input=apm_test_server.container_img,
        )

        env = {}
        env["DD_TRACE_DEBUG"] = "true"
        if sys.platform == "darwin" or sys.platform == "win32":
            env["DD_TRACE_AGENT_URL"] = "http://host.docker.internal:8126"
            # Not all clients support DD_TRACE_AGENT_URL
            env["DD_AGENT_HOST"] = "host.docker.internal"
            env["DD_TRACE_AGENT_PORT"] = "8126"
        else:
            env["DD_TRACE_AGENT_URL"] = "http://localhost:8126"
        env.update(apm_test_server.env)

    with docker_run(
        image=apm_test_server.container_tag,
        name=apm_test_server.container_name,
        cmd=apm_test_server.container_cmd,
        env=env,
        ports=[(apm_test_server.port, apm_test_server.port)],
        volumes=apm_test_server.volumes,
        log_file_path=test_server_log_file,
    ):
        yield apm_test_server


class _TestSpan:
    def __init__(self, client: apm_test_client_pb2_grpc.APMClientStub, span_id: int):
        self._client = client
        self.span_id = span_id

    def set_meta(self, key: str, val: str):
        self._client.SpanSetMeta(
            pb.SpanSetMetaArgs(
                span_id=self.span_id,
                key=key,
                value=val,
            )
        )

    def set_metric(self, key: str, val: float):
        self._client.SpanSetMetric(
            pb.SpanSetMetricArgs(
                span_id=self.span_id,
                key=key,
                value=val,
            )
        )

    def set_error(self, typestr: str = "", message: str = "", stack: str = ""):
        self._client.SpanSetError(
            pb.SpanSetErrorArgs(
                span_id=self.span_id,
                type=typestr,
                message=message,
                stack=stack,
            )
        )

    def finish(self):
        self._client.FinishSpan(
            pb.FinishSpanArgs(
                id=self.span_id,
            )
        )


class _TestTracer:
    def __init__(self, client: apm_test_client_pb2_grpc.APMClientStub):
        self._client = client

    @contextlib.contextmanager
    def start_span(
        self, name: str, service: str = "", resource: str = "", parent_id: int = 0, typestr: str = "", origin: str = ""
    ) -> Generator[_TestSpan, None, None]:
        resp = self._client.StartSpan(
            pb.StartSpanArgs(
                name=name,
                service=service,
                resource=resource,
                parent_id=parent_id,
                type=typestr,
                origin=origin,
            )
        )
        span = _TestSpan(self._client, resp.span_id)
        yield span
        span.finish()

    def flush(self):
        self._client.FlushSpans(pb.FlushSpansArgs())
        self._client.FlushTraceStats(pb.FlushTraceStatsArgs())


@pytest.fixture
def test_server_timeout():
    yield 20


@pytest.fixture
def test_client(test_server, test_server_timeout):
    channel = grpc.insecure_channel("localhost:%s" % test_server.port)
    grpc.channel_ready_future(channel).result(timeout=test_server_timeout)
    client = apm_test_client_pb2_grpc.APMClientStub(channel)
    tracer = _TestTracer(client)
    yield tracer
    tracer.flush()
