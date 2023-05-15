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

from utils import context
from utils.tools import logger


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


ClientLibraryServerFactory = Callable[[Dict[str, str]], APMLibraryTestServer]


def python_library_factory(env: Dict[str, str], container_id: str, port: str) -> APMLibraryTestServer:
    python_appdir = os.path.join("utils", "build", "docker", "python", "parametric")
    python_absolute_appdir = os.path.join(os.getcwd(), python_appdir)
    # By default run parametric tests against the development branch
    python_package = os.getenv("PYTHON_DDTRACE_PACKAGE", "ddtrace")
    return APMLibraryTestServer(
        lang="python",
        protocol="grpc",
        container_name="python-test-library-%s" % container_id,
        container_tag="python-test-library",
        container_img="""
FROM ghcr.io/datadog/dd-trace-py/testrunner:7ce49bd78b0d510766fc5db12756a8840724febc
WORKDIR /client
RUN pyenv global 3.9.11
RUN python3.9 -m pip install grpcio==1.46.3 grpcio-tools==1.46.3
RUN python3.9 -m pip install %s
"""
        % (python_package,),
        container_cmd="python3.9 -m apm_test_client".split(" "),
        container_build_dir=python_absolute_appdir,
        container_build_context=python_absolute_appdir,
        volumes=[(os.path.join(python_absolute_appdir, "apm_test_client"), "/client/apm_test_client"),],
        env=env,
        port=port,
    )


def python_http_library_factory(env: Dict[str, str], container_id: str, port: str) -> APMLibraryTestServer:
    python_appdir = os.path.join("utils", "build", "docker", "python", "parametric_http")
    python_absolute_appdir = os.path.join(os.getcwd(), python_appdir)
    # By default run parametric tests against the development branch
    python_package = os.getenv("PYTHON_DDTRACE_PACKAGE", "ddtrace")
    return APMLibraryTestServer(
        lang="python",
        protocol="http",
        container_name="python-test-library-http-%s" % container_id,
        container_tag="python-test-library",
        container_img="""
FROM ghcr.io/datadog/dd-trace-py/testrunner:7ce49bd78b0d510766fc5db12756a8840724febc
WORKDIR /client
RUN pyenv global 3.9.11
RUN python3.9 -m pip install fastapi==0.89.1 uvicorn==0.20.0
RUN python3.9 -m pip install %s
"""
        % (python_package,),
        container_cmd="python3.9 -m apm_test_client".split(" "),
        container_build_dir=python_absolute_appdir,
        container_build_context=python_absolute_appdir,
        volumes=[(os.path.join(python_absolute_appdir, "apm_test_client"), "/client/apm_test_client"),],
        env=env,
        port=port,
    )


def node_library_factory(env: Dict[str, str], container_id: str, port: str) -> APMLibraryTestServer:
    nodejs_appdir = os.path.join("utils", "build", "docker", "nodejs", "parametric")
    nodejs_absolute_appdir = os.path.join(os.getcwd(), nodejs_appdir)
    node_module = os.getenv("NODEJS_DDTRACE_MODULE", "dd-trace")
    return APMLibraryTestServer(
        lang="nodejs",
        protocol="grpc",
        container_name="node-test-client-%s" % container_id,
        container_tag="node-test-client",
        container_img=f"""
FROM node:18.10-slim
WORKDIR /client
COPY ./package.json /client/
COPY ./package-lock.json /client/
COPY ./*.js /client/
COPY ./npm/* /client/
RUN npm install
RUN npm install {node_module}
""",
        container_cmd=["node", "server.js"],
        container_build_dir=nodejs_absolute_appdir,
        container_build_context=nodejs_absolute_appdir,
        volumes=[
            (
                os.path.join(os.getcwd(), "utils", "parametric", "protos", "apm_test_client.proto"),
                "/client/apm_test_client.proto",
            ),
        ],
        port=port,
        env=env,
    )


def golang_library_factory(env: Dict[str, str], container_id: str, port: str):

    golang_appdir = os.path.join("utils", "build", "docker", "golang", "parametric")
    golang_absolute_appdir = os.path.join(os.getcwd(), golang_appdir)

    return APMLibraryTestServer(
        lang="golang",
        protocol="grpc",
        container_name="go-test-library-%s" % container_id,
        container_tag="go118-test-library",
        container_img=f"""
FROM golang:1.18
WORKDIR /client
COPY ./go.mod /client
COPY ./go.sum /client
COPY . /client
RUN go install
""",
        container_cmd=["main"],
        container_build_dir=golang_absolute_appdir,
        container_build_context=golang_absolute_appdir,
        volumes=[(os.path.join(golang_absolute_appdir), "/client"),],
        env=env,
        port=port,
    )


def dotnet_library_factory(env: Dict[str, str], container_id: str, port: str):
    dotnet_appdir = os.path.join("utils", "build", "docker", "dotnet", "parametric")
    dotnet_absolute_appdir = os.path.join(os.getcwd(), dotnet_appdir)
    server = APMLibraryTestServer(
        lang="dotnet",
        protocol="grpc",
        container_name="dotnet-test-client-%s" % container_id,
        container_tag="dotnet6_0-test-client",
        container_img=f"""
FROM mcr.microsoft.com/dotnet/sdk:6.0
WORKDIR /client
COPY ["./ApmTestClient.csproj","./nuget.config","./*.nupkg", "./"]
RUN dotnet restore "./ApmTestClient.csproj"
COPY . .
WORKDIR "/client/."
""",
        container_cmd=["dotnet", "run"],
        container_build_dir=dotnet_absolute_appdir,
        container_build_context=dotnet_absolute_appdir,
        volumes=[(os.path.join(dotnet_absolute_appdir), "/client"),],
        env=env,
        port=port,
    )
    server.env["ASPNETCORE_URLS"] = "http://localhost:%s" % server.port
    return server


def java_library_factory(env: Dict[str, str], container_id: str, port: str):
    java_appdir = os.path.join("utils", "build", "docker", "java", "parametric")
    java_absolute_appdir = os.path.join(os.getcwd(), java_appdir)

    # Create the relative path and substitute the Windows separator, to allow running the Docker build on Windows machines
    java_reldir = java_appdir.replace("\\", "/")
    protofile = os.path.join("utils", "parametric", "protos", "apm_test_client.proto").replace("\\", "/")

    return APMLibraryTestServer(
        lang="java",
        protocol="grpc",
        container_name="java-test-client-%s" % container_id,
        container_tag="java8-test-client",
        container_img=f"""
# FROM ghcr.io/datadog/dd-trace-java/dd-trace-java:latest as apm_library_latest
FROM maven:3-jdk-8
WORKDIR /client
# COPY --from=apm_library_latest /dd-java-agent.jar ./tracer/
# COPY --from=apm_library_latest /LIBRARY_VERSION ./tracer/
RUN mkdir ./tracer/ && wget -O ./tracer/dd-java-agent.jar https://github.com/DataDog/dd-trace-java/releases/download/v1.12.1/dd-java-agent-1.12.1.jar
COPY {java_reldir}/src src
COPY {java_reldir}/build.sh .
COPY {java_reldir}/pom.xml .
COPY {java_reldir}/run.sh .
COPY {protofile} src/main/proto/
COPY binaries /binaries
RUN bash build.sh
""",
        container_cmd=["./run.sh"],
        container_build_dir=java_absolute_appdir,
        container_build_context=os.getcwd(),
        volumes=[],
        env=env,
        port=port,
    )


def php_library_factory(env: Dict[str, str], container_id: str, port: str) -> APMLibraryTestServer:
    php_appdir = os.path.join("utils", "build", "docker", "php", "parametric")
    php_absolute_appdir = os.path.join(os.getcwd(), php_appdir)
    php_reldir = php_appdir.replace("\\", "/")
    env = env.copy()
    # env["DD_TRACE_AGENT_DEBUG_VERBOSE_CURL"] = "1"
    return APMLibraryTestServer(
        lang="php",
        protocol="http",
        container_name="php-test-library-%s" % container_id,
        container_tag="php-test-library",
        container_img=f"""
FROM datadog/dd-trace-ci:php-8.2_buster
WORKDIR /tmp
ENV DD_TRACE_CLI_ENABLED=1
ADD {php_reldir}/composer.json .
ADD {php_reldir}/composer.lock .
ADD {php_reldir}/server.php .
ADD {php_reldir}/install.sh .
COPY binaries /binaries
RUN ./install.sh
RUN composer install
""",
        container_cmd=["php", "server.php"],
        container_build_dir=php_absolute_appdir,
        container_build_context=os.getcwd(),
        volumes=[(os.path.join(php_absolute_appdir, "server.php"), "/client/server.php"),],
        env=env,
        port=port,
    )


def ruby_library_factory(env: Dict[str, str], container_id: str, port: str) -> APMLibraryTestServer:

    ruby_appdir = os.path.join("utils", "build", "docker", "ruby", "parametric")
    ruby_absolute_appdir = os.path.join(os.getcwd(), ruby_appdir)

    ddtrace_sha = os.getenv("RUBY_DDTRACE_SHA", "")

    shutil.copyfile(
        os.path.join("utils", "parametric", "protos", "apm_test_client.proto"),
        os.path.join(ruby_absolute_appdir, "apm_test_client.proto"),
    )
    return APMLibraryTestServer(
        lang="ruby",
        protocol="grpc",
        container_name="ruby-test-client-%s" % container_id,
        container_tag="ruby-test-client",
        container_img=f"""
            FROM ruby:3.2.1-bullseye
            WORKDIR /client
            RUN gem install ddtrace # Install a baseline ddtrace version, to cache all dependencies
            COPY ./Gemfile /client/
            COPY ./install_dependencies.sh /client/
            ENV RUBY_DDTRACE_SHA='{ddtrace_sha}'
            RUN bash install_dependencies.sh # Cache dependencies before copying application code
            COPY ./apm_test_client.proto /client/
            COPY ./generate_proto.sh /client/
            RUN bash generate_proto.sh
            COPY ./server.rb /client/
            """,
        container_cmd=["bundle", "exec", "ruby", "server.rb"],
        container_build_dir=ruby_absolute_appdir,
        container_build_context=ruby_absolute_appdir,
        env=env,
        port=port,
    )


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
    # Have to do this funky request.param stuff as this is the recommended way to do parametrized fixtures
    # in pytest.
    apm_test_library = _libs[context.scenario.library.library]

    yield apm_test_library(library_env, test_id, get_open_port())


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()


@pytest.fixture
def test_server_log_file(apm_test_server, request) -> Generator[TextIO, None, None]:
    with tempfile.NamedTemporaryFile(mode="w+") as f:
        yield f
        f.seek(0)
        request.node._report_sections.append(
            ("teardown", f"{apm_test_server.lang.capitalize()} Library Output", "".join(f.readlines()))
        )


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
        apm_test_server.container_build_context,
    ]
    test_server_log_file.write("running %r in %r\n" % (" ".join(cmd), root_path))
    test_server_log_file.flush()

    env = os.environ.copy()
    env["DOCKER_SCAN_SUGGEST"] = "false"  # Docker outputs an annoying synk message on every build

    p = subprocess.run(
        cmd,
        cwd=root_path,
        text=True,
        input=apm_test_server.container_img,
        stdout=test_server_log_file,
        stderr=test_server_log_file,
        env=env,
    )
    if p.returncode != 0:
        test_server_log_file.seek(0)
        pytest.fail("".join(test_server_log_file.readlines()), pytrace=False)

    env = {
        "DD_TRACE_DEBUG": "true",
        "DD_TRACE_AGENT_URL": "http://%s:%s" % (test_agent_container_name, test_agent_port),
        "DD_AGENT_HOST": test_agent_container_name,
        "DD_TRACE_AGENT_PORT": test_agent_port,
        "APM_TEST_CLIENT_SERVER_PORT": apm_test_server.port,
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
