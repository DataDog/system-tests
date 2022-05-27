import contextlib
import dataclasses
import os
import shutil
import subprocess
import sys
import time
from typing import Dict, List, Tuple
import urllib.parse

import grpc

import attr
import requests
from ddtrace.internal.compat import parse, to_unicode
from ddtrace.internal.compat import httplib
import pytest

from apm_client.protos import apm_test_client_pb2 as pb
from apm_client.protos import apm_test_client_pb2_grpc


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "snapshot(*args, **kwargs): mark test to run as a snapshot test which sends traces to the test agent"
    )


@attr.s
class SnapshotTest(object):
    token = attr.ib(type=str)

    def clear(self):
        """Clear any traces sent that were sent for this snapshot."""
        parsed = parse.urlparse(self.tracer.agent_trace_url)
        conn = httplib.HTTPConnection(parsed.hostname, parsed.port)
        conn.request("GET", "/test/session/clear?test_session_token=%s" % self.token)
        resp = conn.getresponse()
        assert resp.status == 200


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
    port: str = "50051"
    env: Dict[str, str] = dataclasses.field(default_factory=dict)
    volumes: List[Tuple[str, str]] = dataclasses.field(default_factory=list)


@pytest.fixture
def apm_test_server_env():
    yield {}


@pytest.fixture
def apm_test_server(apm_test_server_env):
    python_dir = os.path.join(os.getcwd(), "python")
    yield APMClientTestServer(
        container_name="python-test-client",
        container_tag="py39-test-client",
        container_img="""
FROM python:3.9
WORKDIR /client
RUN pip install grpcio==1.46.3 grpcio-tools==1.46.3
RUN pip install ddtrace
""",
        container_cmd="python -m apm_test_client".split(" "),
        volumes=[
            (os.path.join(python_dir, "apm_test_client"), "/client/apm_test_client"),
        ],
        env=apm_test_server_env,
    )


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
            yield SnapshotTest(token=token)
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
        yield
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
        for i in range(50):
            try:
                client.traces()
            except requests.exceptions.ConnectionError as e:
                time.sleep(0.2)
            else:
                break
        else:
            pytest.fail("Could not connect to test agent: %s" % str(e), pytrace=False)

        # If the snapshot mark is on the test case then do a snapshot test
        marks = [m for m in request.node.iter_markers(name="snapshot")]
        assert len(marks) < 2, "Multiple snapshot marks detected"
        if marks:
            snap = marks[0]
            token = _request_token(request).replace(" ", "_").replace(os.path.sep, "_")
            with client.snapshot_context(token, *snap.args, **snap.kwargs):
                yield client
        else:
            yield client


@pytest.fixture
def test_server(tmp_path, apm_test_server: APMClientTestServer, test_server_log_file):
    print(test_server_log_file)
    with open(test_server_log_file, "w") as f:
        # Build the container
        docker = shutil.which("docker")
        cmd = [
            docker,
            "build",
            "-t",
            apm_test_server.container_tag,
            "-",
        ]
        subprocess.run(
            cmd,
            stdout=f,
            stderr=f,
            check=True,
            text=True,
            input=apm_test_server.container_img,
        )

        env = {}
        if sys.platform == "darwin":
            env["DD_TRACE_AGENT_URL"] = "http://host.docker.internal:8126"
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


@pytest.fixture
def test_server_timeout():
    yield 10


@pytest.fixture
def test_client(test_server, test_server_timeout):
    channel = grpc.insecure_channel("localhost:%s" % test_server.port)
    grpc.channel_ready_future(channel).result(timeout=test_server_timeout)
    client = apm_test_client_pb2_grpc.APMClientStub(channel)
    yield client
    client.FlushSpans(pb.FlushSpansArgs())
