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
from utils.parametric.spec import remoteconfig
from utils.parametric._library_client import APMLibraryClientGRPC
from utils.parametric._library_client import APMLibraryClientHTTP
from utils.parametric._library_client import APMLibrary

from utils import context
from utils.tools import logger
import json

from filelock import FileLock

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


@dataclasses.dataclass
class APMLibraryTestServer:
    # The library of the interface.
    lang: str
    # The interface that this test server implements.
    protocol: Union[Literal["grpc"], Literal["http"]]
    container_name: str
    container_tag: str
    container_img: str
    container_cmd: List[str]
    container_build_dir: str
    container_build_context: str = "."
    port: str = os.getenv("APM_LIBRARY_SERVER_PORT", "50052")
    env: Dict[str, str] = dataclasses.field(default_factory=dict)
    volumes: List[Tuple[str, str]] = dataclasses.field(default_factory=list)


@pytest.fixture
def library_env() -> Dict[str, str]:
    return {}


ClientLibraryServerFactory = Callable[[], APMLibraryTestServer]


def _get_base_directory():
    """Workaround until the parametric tests are fully migrated"""
    current_directory = os.getcwd()
    return f"{current_directory}/.." if current_directory.endswith("parametric") else current_directory


def python_library_factory() -> APMLibraryTestServer:
    python_appdir = os.path.join("utils", "build", "docker", "python", "parametric")
    python_absolute_appdir = os.path.join(_get_base_directory(), python_appdir)
    return APMLibraryTestServer(
        lang="python",
        protocol="http",
        container_name="python-test-library",
        container_tag="python-test-library",
        container_img="""
FROM ghcr.io/datadog/dd-trace-py/testrunner:7ce49bd78b0d510766fc5db12756a8840724febc
WORKDIR /app
RUN pyenv global 3.9.11
RUN python3.9 -m pip install fastapi==0.89.1 uvicorn==0.20.0
COPY utils/build/docker/python/install_ddtrace.sh utils/build/docker/python/get_appsec_rules_version.py binaries* /binaries/
RUN /binaries/install_ddtrace.sh
ENV DD_PATCH_MODULES="fastapi:false"
""",
        container_cmd="ddtrace-run python3.9 -m apm_test_client".split(" "),
        container_build_dir=python_absolute_appdir,
        container_build_context=_get_base_directory(),
        volumes=[(os.path.join(python_absolute_appdir, "apm_test_client"), "/app/apm_test_client"),],
        env={},
        port="",
    )


def node_library_factory() -> APMLibraryTestServer:
    nodejs_appdir = os.path.join("utils", "build", "docker", "nodejs", "parametric")
    nodejs_absolute_appdir = os.path.join(_get_base_directory(), nodejs_appdir)
    nodejs_reldir = nodejs_appdir.replace("\\", "/")

    return APMLibraryTestServer(
        lang="nodejs",
        protocol="http",
        container_name="node-test-client",
        container_tag="node-test-client",
        container_img=f"""
FROM node:18.10-slim
RUN apt-get update && apt-get install -y jq git
WORKDIR /usr/app
COPY {nodejs_reldir}/package.json /usr/app/
COPY {nodejs_reldir}/package-lock.json /usr/app/
COPY {nodejs_reldir}/*.js /usr/app/
COPY {nodejs_reldir}/npm/* /usr/app/

RUN npm install

COPY {nodejs_reldir}/../install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

""",
        container_cmd=["node", "server.js"],
        container_build_dir=nodejs_absolute_appdir,
        container_build_context=_get_base_directory(),
        env={},
        port="",
    )


def golang_library_factory():

    golang_appdir = os.path.join("utils", "build", "docker", "golang", "parametric")
    golang_absolute_appdir = os.path.join(_get_base_directory(), golang_appdir)
    golang_reldir = golang_appdir.replace("\\", "/")
    return APMLibraryTestServer(
        lang="golang",
        protocol="grpc",
        container_name="go-test-library",
        container_tag="go118-test-library",
        container_img=f"""
FROM golang:1.20

# install jq
RUN apt-get update && apt-get -y install jq
WORKDIR /app
COPY {golang_reldir}/go.mod /app
COPY {golang_reldir}/go.sum /app
COPY {golang_reldir}/. /app
# download the proper tracer version
COPY utils/build/docker/golang/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

RUN go install
""",
        container_cmd=["main"],
        container_build_dir=golang_absolute_appdir,
        container_build_context=_get_base_directory(),
        volumes=[(os.path.join(golang_absolute_appdir), "/client"),],
        env={},
        port="",
    )


def dotnet_library_factory():
    dotnet_appdir = os.path.join("utils", "build", "docker", "dotnet", "parametric")
    dotnet_absolute_appdir = os.path.join(_get_base_directory(), dotnet_appdir)
    dotnet_reldir = dotnet_appdir.replace("\\", "/")
    server = APMLibraryTestServer(
        lang="dotnet",
        protocol="grpc",
        container_name="dotnet-test-client",
        container_tag="dotnet7_0-test-client",
        container_img=f"""
FROM mcr.microsoft.com/dotnet/sdk:7.0
RUN apt-get update && apt-get install dos2unix
WORKDIR /app

# Opt-out of .NET SDK CLI telemetry (prevent unexpected http client spans)
ENV DOTNET_CLI_TELEMETRY_OPTOUT=1

# ensure that the Datadog.Trace.dlls are installed from /binaries
COPY utils/build/docker/dotnet/install_ddtrace.sh utils/build/docker/dotnet/query-versions.fsx binaries* /binaries/
RUN dos2unix /binaries/install_ddtrace.sh
RUN /binaries/install_ddtrace.sh

# restore nuget packages
COPY ["{dotnet_reldir}/ApmTestClient.csproj", "{dotnet_reldir}/nuget.config", "{dotnet_reldir}/*.nupkg", "./"]
RUN dotnet restore "./ApmTestClient.csproj"

# build and publish
COPY {dotnet_reldir} ./
RUN dotnet publish --no-restore --configuration Release --output out
WORKDIR /app/out

# Set up automatic instrumentation (required for OpenTelemetry tests),
# but don't enable it globally
ENV CORECLR_ENABLE_PROFILING=0
ENV CORECLR_PROFILER={{846F5F1C-F9AE-4B07-969E-05C26BC060D8}}
ENV CORECLR_PROFILER_PATH=/opt/datadog/Datadog.Trace.ClrProfiler.Native.so
ENV DD_DOTNET_TRACER_HOME=/opt/datadog

# disable gRPC, ASP.NET Core, and other auto-instrumentations (to prevent unexpected spans)
ENV DD_TRACE_Grpc_ENABLED=false
ENV DD_TRACE_AspNetCore_ENABLED=false
ENV DD_TRACE_Process_ENABLED=false
ENV DD_TRACE_OTEL_ENABLED=false
""",
        container_cmd=["./ApmTestClient"],
        container_build_dir=dotnet_absolute_appdir,
        container_build_context=_get_base_directory(),
        volumes=[],
        env={},
        port="",
    )

    return server


def java_library_factory():
    java_appdir = os.path.join("utils", "build", "docker", "java", "parametric")
    java_absolute_appdir = os.path.join(_get_base_directory(), java_appdir)

    # Create the relative path and substitute the Windows separator, to allow running the Docker build on Windows machines
    java_reldir = java_appdir.replace("\\", "/")
    protofile = os.path.join("utils", "parametric", "protos", "apm_test_client.proto").replace("\\", "/")

    return APMLibraryTestServer(
        lang="java",
        protocol="grpc",
        container_name="java-test-client",
        container_tag="java-test-client",
        container_img=f"""
FROM maven:3.9.2-eclipse-temurin-17
WORKDIR /client
RUN mkdir ./tracer/ && wget -O ./tracer/dd-java-agent.jar https://github.com/DataDog/dd-trace-java/releases/latest/download/dd-java-agent.jar
COPY {java_reldir}/src src
COPY {java_reldir}/build.sh .
COPY {java_reldir}/pom.xml .
COPY {protofile} src/main/proto/
COPY binaries /binaries
RUN bash build.sh
COPY {java_reldir}/run.sh .
""",
        container_cmd=["./run.sh"],
        container_build_dir=java_absolute_appdir,
        container_build_context=_get_base_directory(),
        volumes=[],
        env={},
        port="",
    )


def php_library_factory() -> APMLibraryTestServer:
    php_appdir = os.path.join("utils", "build", "docker", "php", "parametric")
    php_absolute_appdir = os.path.join(_get_base_directory(), php_appdir)
    php_reldir = php_appdir.replace("\\", "/")
    return APMLibraryTestServer(
        lang="php",
        protocol="http",
        container_name="php-test-library",
        container_tag="php-test-library",
        container_img=f"""
FROM datadog/dd-trace-ci:php-8.2_buster
WORKDIR /binaries
ENV DD_TRACE_CLI_ENABLED=1
ADD {php_reldir}/composer.json .
ADD {php_reldir}/composer.lock .
RUN composer install
ADD {php_reldir}/../common/install_ddtrace.sh .
COPY binaries /binaries
RUN NO_EXTRACT_VERSION=Y ./install_ddtrace.sh
ADD {php_reldir}/server.php .
""",
        container_cmd=["php", "server.php"],
        container_build_dir=php_absolute_appdir,
        container_build_context=_get_base_directory(),
        volumes=[(os.path.join(php_absolute_appdir, "server.php"), "/client/server.php"),],
        env={},
        port="",
    )


def ruby_library_factory() -> APMLibraryTestServer:

    ruby_appdir = os.path.join("utils", "build", "docker", "ruby", "parametric")
    ruby_absolute_appdir = os.path.join(_get_base_directory(), ruby_appdir)
    ruby_reldir = ruby_appdir.replace("\\", "/")

    shutil.copyfile(
        os.path.join(_get_base_directory(), "utils", "parametric", "protos", "apm_test_client.proto"),
        os.path.join(ruby_absolute_appdir, "apm_test_client.proto"),
    )
    return APMLibraryTestServer(
        lang="ruby",
        protocol="grpc",
        container_name="ruby-test-client",
        container_tag="ruby-test-client",
        container_img=f"""
            FROM ruby:3.2.1-bullseye
            WORKDIR /app
            COPY {ruby_reldir} .           
            COPY {ruby_reldir}/../install_ddtrace.sh binaries* /binaries/
            RUN bundle install 
            RUN /binaries/install_ddtrace.sh
            COPY {ruby_reldir}/apm_test_client.proto /app/
            COPY {ruby_reldir}/generate_proto.sh /app/
            RUN bash generate_proto.sh
            COPY {ruby_reldir}/server.rb /app/
            """,
        container_cmd=["bundle", "exec", "ruby", "server.rb"],
        container_build_dir=ruby_absolute_appdir,
        container_build_context=_get_base_directory(),
        env={},
        port="",
    )


def cpp_library_factory() -> APMLibraryTestServer:
    cpp_appdir = os.path.join("utils", "build", "docker", "cpp", "parametric", "http")
    cpp_absolute_appdir = os.path.join(_get_base_directory(), cpp_appdir)
    cpp_reldir = cpp_appdir.replace("\\", "/")
    dockerfile_content = f"""
FROM datadog/docker-library:dd-trace-cpp-ci AS build

RUN apt-get update && apt-get -y install pkg-config libabsl-dev curl jq
WORKDIR /usr/app
COPY {cpp_reldir}/../install_ddtrace.sh binaries* /binaries/
ADD {cpp_reldir}/CMakeLists.txt \
    {cpp_reldir}/developer_noise.cpp \
    {cpp_reldir}/developer_noise.h \
    {cpp_reldir}/httplib.h \
    {cpp_reldir}/json.hpp \
    {cpp_reldir}/main.cpp \
    {cpp_reldir}/manual_scheduler.h \
    {cpp_reldir}/request_handler.cpp \
    {cpp_reldir}/request_handler.h \
    {cpp_reldir}/utils.h \
    /usr/app
RUN sh /binaries/install_ddtrace.sh
RUN cmake -B .build -DCMAKE_BUILD_TYPE=Release . && cmake --build .build -j $(nproc) && cmake --install .build --prefix dist

FROM ubuntu:22.04
COPY --from=build /usr/app/dist/bin/cpp-parametric-http-test /usr/local/bin/cpp-parametric-test
"""

    return APMLibraryTestServer(
        lang="cpp",
        protocol="http",
        container_name="cpp-test-client",
        container_tag="cpp-test-client",
        container_img=dockerfile_content,
        container_cmd=["cpp-parametric-test"],
        container_build_dir=cpp_absolute_appdir,
        container_build_context=_get_base_directory(),
        env={},
        port="",
    )


_libs: Dict[str, ClientLibraryServerFactory] = {
    "cpp": cpp_library_factory,
    "dotnet": dotnet_library_factory,
    "golang": golang_library_factory,
    "java": java_library_factory,
    "nodejs": node_library_factory,
    "php": php_library_factory,
    "python": python_library_factory,
    "ruby": ruby_library_factory,
}


def get_open_port():
    # Not very nice and also not 100% correct but it works for now.
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    s.listen(1)
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="session")
def apm_test_server_definition() -> APMLibraryTestServer:
    """Session level definition of the library test server"""
    # There is only one language at a time in a pytest run
    yield _libs[context.scenario.library.library]()


def build_apm_test_server_image(apm_test_server_definition: APMLibraryTestServer,) -> str:
    log_path = f"{context.scenario.host_log_folder}/outputs/docker_build_log.log"
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    log_file = open(log_path, "w+")
    # Write dockerfile to the build directory
    # Note that this needs to be done as the context cannot be
    # specified if Dockerfiles are read from stdin.
    dockf_path = os.path.join(apm_test_server_definition.container_build_dir, "Dockerfile")
    with open(dockf_path, "w") as dockf:
        dockf.write(apm_test_server_definition.container_img)
    # Build the container
    docker = shutil.which("docker")
    root_path = ".."
    cmd = [
        docker,
        "build",
        "--progress=plain",  # use plain output to assist in debugging
        "-t",
        apm_test_server_definition.container_tag,
        "-f",
        dockf_path,
        apm_test_server_definition.container_build_context,
    ]
    log_file.write("running %r in %r\n" % (" ".join(cmd), root_path))
    log_file.flush()

    env = os.environ.copy()
    env["DOCKER_SCAN_SUGGEST"] = "false"  # Docker outputs an annoying synk message on every build

    p = subprocess.run(
        cmd,
        cwd=root_path,
        text=True,
        input=apm_test_server_definition.container_img,
        stdout=log_file,
        stderr=log_file,
        env=env,
        timeout=default_subprocess_run_timeout,
    )

    failure_text: str = None
    if p.returncode != 0:
        log_file.seek(0)
        failure_text = "".join(log_file.readlines())
    log_file.close()

    return failure_text


@pytest.fixture(scope="session")
def apm_test_server_image(
    docker, apm_test_server_definition: APMLibraryTestServer, worker_id, tmp_path_factory
) -> APMLibraryTestServer:
    """Session level definition of the library test server with the Docker image built"""
    # all this is only needed since xdist will execute session scopes once for every worker
    # and here we want to make sure that we build the Docker image once and only once
    failure_text: str = None
    if worker_id == "master":
        # not executing with multiple workers just build the image
        failure_text = build_apm_test_server_image(apm_test_server_definition)
    else:
        # get the temp directory shared by all workers
        root_tmp_dir = tmp_path_factory.getbasetemp().parent
        fn = root_tmp_dir / apm_test_server_definition.container_tag
        with FileLock(str(fn) + ".lock"):
            if not fn.is_file():
                failure_text = build_apm_test_server_image(apm_test_server_definition)
                if failure_text == None:
                    fn.write_text("success")
                else:
                    fn.write_text("failure")
            else:
                if fn.read_text() == "failure":
                    failure_text = "Failed to build docker image. See output from other worker."

    if failure_text != None:
        pytest.fail(failure_text, pytrace=False)

    yield apm_test_server_definition


@pytest.fixture
def apm_test_server(request, library_env, test_id, apm_test_server_image):
    """Request level definition of the library test server with the session Docker image built"""
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
            self._url("/test/session/responses/config/path"), json={"path": path, "msg": payload,}
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

    def wait_for_num_traces(self, num: int, clear: bool = False, wait_loops: int = 30) -> List[Trace]:
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
                    return sorted(traces, key=lambda trace: trace[0]["start"])
            time.sleep(0.1)
        raise ValueError(
            "Number (%r) of traces not available from test agent, got %r:\n%r" % (num, num_received, traces)
        )

    def wait_for_num_spans(self, num: int, clear: bool = False, wait_loops: int = 30) -> List[Trace]:
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
                    return sorted(traces, key=lambda trace: trace[0]["start"])
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
                                if clear:
                                    self.clear()
                                return message
                    elif event["request_type"] == event_name:
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
        _cmd.extend(["-p", "%s:%s" % (k, v)])
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
        ["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=default_subprocess_run_timeout
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
            cmd, stdout=docker_network_log_file, stderr=docker_network_log_file, timeout=default_subprocess_run_timeout
        )
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
    r = subprocess.run(
        cmd, stdout=docker_network_log_file, stderr=docker_network_log_file, timeout=default_subprocess_run_timeout
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
        image="ghcr.io/datadog/dd-apm-test-agent/ddapm-test-agent:v1.15.0",
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
