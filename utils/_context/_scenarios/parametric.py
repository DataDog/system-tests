import dataclasses
from typing import Dict, List, Literal, Union

import json
import glob
from functools import lru_cache
import os
import shutil
import subprocess
import time

import pytest
import docker
from docker.errors import DockerException
from docker.models.containers import Container
from docker.models.networks import Network

from utils._context.library_version import LibraryVersion
from utils.tools import logger

from .core import Scenario, ScenarioGroup


# Max timeout in seconds to keep a container running
default_subprocess_run_timeout = 300
_NETWORK_PREFIX = "apm_shared_tests_network"
# _TEST_CLIENT_PREFIX = "apm_shared_tests_container"


@lru_cache
def _get_client() -> docker.DockerClient:
    try:
        return docker.DockerClient.from_env()
    except DockerException as e:
        # Failed to start the default Docker client... Let's see if we have
        # better luck with docker contexts...
        try:
            ctx_name = subprocess.run(
                ["docker", "context", "show"], capture_output=True, check=True, text=True
            ).stdout.strip()
            endpoint = subprocess.run(
                ["docker", "context", "inspect", ctx_name, "-f", "{{ .Endpoints.docker.Host }}"],
                capture_output=True,
                check=True,
                text=True,
            ).stdout.strip()
            return docker.DockerClient(base_url=endpoint)
        except:
            pass

        raise e


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

    container_port: str = int(os.getenv("APM_LIBRARY_SERVER_PORT", "50052"))
    host_port: int = None  # docker will choose this port at startup

    env: Dict[str, str] = dataclasses.field(default_factory=dict)
    volumes: Dict[str, str] = dataclasses.field(default_factory=dict)


class ParametricScenario(Scenario):
    apm_test_server_definition: APMLibraryTestServer

    class PersistentParametricTestConf(dict):
        """Parametric tests are executed in multiple thread, we need a mechanism to persist each parametrized_tests_metadata on a file"""

        def __init__(self, outer_inst):
            self.outer_inst = outer_inst
            # To handle correctly we need to add data by default
            self.update({"scenario": outer_inst.name})

        def __setitem__(self, item, value):
            super().__setitem__(item, value)
            # Append to the context file
            ctx_filename = f"{self.outer_inst.host_log_folder}/{os.environ.get('PYTEST_XDIST_WORKER')}_context.json"
            with open(ctx_filename, "a") as f:
                json.dump({item: value}, f)
                f.write(",")
                f.write(os.linesep)

        def deserialize(self):
            result = {}
            for ctx_filename in glob.glob(f"{self.outer_inst.host_log_folder}/*_context.json"):
                with open(ctx_filename, "r") as f:
                    fileContent = f.read()
                    # Remove last carriage return and the last comma. Wrap into json array.
                    all_params = json.loads(f"[{fileContent[:-2]}]")
                    # Change from array to unique dict
                    for d in all_params:
                        result.update(d)
            return result

    def __init__(self, name, doc) -> None:
        super().__init__(
            name, doc=doc, github_workflow="parametric", scenario_groups=[ScenarioGroup.ALL, ScenarioGroup.PARAMETRIC]
        )
        self._parametric_tests_confs = ParametricScenario.PersistentParametricTestConf(self)

    @property
    def parametrized_tests_metadata(self):
        return self._parametric_tests_confs

    def configure(self, config):
        super().configure(config)
        assert "TEST_LIBRARY" in os.environ
        library = os.getenv("TEST_LIBRARY")

        # get tracer version info building and executing the ddtracer-version.docker file

        factory = {
            "cpp": cpp_library_factory,
            "dotnet": dotnet_library_factory,
            "golang": golang_library_factory,
            "java": java_library_factory,
            "nodejs": node_library_factory,
            "php": php_library_factory,
            "python": python_library_factory,
            "ruby": ruby_library_factory,
        }[library]

        self.apm_test_server_definition = factory()

        if not hasattr(config, "workerinput"):
            # https://github.com/pytest-dev/pytest-xdist/issues/271#issuecomment-826396320
            # we are in the main worker, not in a xdist sub-worker
            self._build_apm_test_server_image()
            self._clean_containers()
            self._clean_networks()

        output = _get_client().containers.run(
            self.apm_test_server_definition.container_tag, remove=True, command=["cat", "SYSTEM_TESTS_LIBRARY_VERSION"],
        )

        self._library = LibraryVersion(library, output.decode("utf-8"))
        logger.debug(f"Library version is {self._library}")

    def _get_warmups(self):
        result = super()._get_warmups()
        result.append(lambda: logger.stdout(f"Library: {self.library}"))

        return result

    def _clean_containers(self):
        """ some containers may still exists from previous unfinished sessions """

        for container in _get_client().containers.list(all=True):
            if "test-client" in container.name or "test-agent" in container.name or "test-library" in container.name:
                logger.info(f"Removing {container}")

                container.remove(force=True)

    def _clean_networks(self):
        """ some network may still exists from previous unfinished sessions """

        for network in _get_client().networks.list():
            if network.name.startswith(_NETWORK_PREFIX):
                logger.info(f"Removing {network}")
                network.remove()

    @property
    def library(self):
        return self._library

    def _build_apm_test_server_image(self) -> str:

        logger.stdout("Build tested container...")

        apm_test_server_definition: APMLibraryTestServer = self.apm_test_server_definition

        log_path = f"{self.host_log_folder}/outputs/docker_build_log.log"
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

        # Write dockerfile to the build directory
        # Note that this needs to be done as the context cannot be
        # specified if Dockerfiles are read from stdin.
        dockf_path = os.path.join(apm_test_server_definition.container_build_dir, "Dockerfile")
        with open(dockf_path, "w", encoding="utf-8") as f:
            f.write(apm_test_server_definition.container_img)

        with open(log_path, "w+", encoding="utf-8") as log_file:

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
                check=False,
            )

            failure_text: str = None
            if p.returncode != 0:
                log_file.seek(0)
                failure_text = "".join(log_file.readlines())
                pytest.exit(f"Failed to build the container: {failure_text}", 1)

            logger.debug("Build tested container finished")

    def create_docker_network(self, test_id: str) -> Network:
        docker_network_name = f"{_NETWORK_PREFIX}_{test_id}"

        return _get_client().networks.create(name=docker_network_name, driver="bridge",)

    def docker_run(
        self,
        image: str,
        name: str,
        env: Dict[str, str],
        volumes: Dict[str, str],
        network: str,
        container_port: int,
        command: List[str],
    ) -> Container:

        # Convert volumes to the format expected by the docker-py API
        fixed_volumes = {}
        for key, value in volumes.items():
            if isinstance(value, dict):
                fixed_volumes[key] = value
            elif isinstance(value, str):
                fixed_volumes[key] = {"bind": value, "mode": "rw"}
            else:
                raise TypeError(f"Unexpected type for volume {key}: {type(value)}")

        logger.debug(f"Run container {name} from image {image}")
        container: Container = _get_client().containers.run(
            image,
            name=name,
            environment=env,
            volumes=fixed_volumes,
            network=network,
            ports={f"{container_port}/tcp": None},  # let docker choose an host port
            command=command,
            detach=True,
        )

        # on first calls, the container does not know yet the published port on host
        for _ in range(10):
            container.reload()

            if f"{container_port}/tcp" in container.attrs["NetworkSettings"]["Ports"]:
                if len(container.attrs["NetworkSettings"]["Ports"][f"{container_port}/tcp"]) != 0:
                    logger.debug(f"container {name} started")

                    return container

            time.sleep(0.1)

        pytest.exit(f"Docker incorrectly bind ports for {name}", 1)  # if this happen, increase the sleep time


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
FROM ghcr.io/datadog/dd-trace-py/testrunner:9e3bd1fb9e42a4aa143cae661547517c7fbd8924
WORKDIR /app
RUN pyenv global 3.9.16
RUN python3.9 -m pip install fastapi==0.89.1 uvicorn==0.20.0
COPY utils/build/docker/python/install_ddtrace.sh utils/build/docker/python/get_appsec_rules_version.py binaries* /binaries/
RUN /binaries/install_ddtrace.sh
ENV DD_PATCH_MODULES="fastapi:false"
""",
        container_cmd="ddtrace-run python3.9 -m apm_test_client".split(" "),
        container_build_dir=python_absolute_appdir,
        container_build_context=_get_base_directory(),
        volumes={os.path.join(python_absolute_appdir, "apm_test_client"): "/app/apm_test_client"},
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
    )


def golang_library_factory():
    golang_appdir = os.path.join("utils", "build", "docker", "golang", "parametric")
    golang_absolute_appdir = os.path.join(_get_base_directory(), golang_appdir)
    golang_reldir = golang_appdir.replace("\\", "/")
    return APMLibraryTestServer(
        lang="golang",
        protocol="grpc",
        container_name="go-test-library",
        container_tag="go122-test-library",
        container_img=f"""
FROM golang:1.22

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
        volumes={os.path.join(golang_absolute_appdir): "/client"},
    )


def dotnet_library_factory():
    dotnet_appdir = os.path.join("utils", "build", "docker", "dotnet", "parametric")
    dotnet_absolute_appdir = os.path.join(_get_base_directory(), dotnet_appdir)
    dotnet_reldir = dotnet_appdir.replace("\\", "/")
    server = APMLibraryTestServer(
        lang="dotnet",
        protocol="http",
        container_name="dotnet-test-api",
        container_tag="dotnet8_0-test-api",
        container_img=f"""
FROM mcr.microsoft.com/dotnet/sdk:8.0 as build

# `binutils` is required by 'install_ddtrace.sh' to call 'strings' command
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y curl binutils
WORKDIR /app

# ensure that the Datadog.Trace.dlls are installed from /binaries
COPY utils/build/docker/dotnet/install_ddtrace.sh utils/build/docker/dotnet/query-versions.fsx binaries* /binaries/
RUN /binaries/install_ddtrace.sh

# restore nuget packages
COPY {dotnet_reldir}/ApmTestApi.csproj {dotnet_reldir}/nuget.config ./
RUN dotnet restore "./ApmTestApi.csproj"

# build and publish
COPY {dotnet_reldir} ./
RUN dotnet publish --no-restore --configuration Release --output out

##################

FROM mcr.microsoft.com/dotnet/aspnet:8.0 as runtime
COPY --from=build /app/out /app
COPY --from=build /app/SYSTEM_TESTS_LIBRARY_VERSION /app/SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=build /opt/datadog /opt/datadog
WORKDIR /app

# Opt-out of .NET SDK CLI telemetry (prevent unexpected http client spans)
ENV DOTNET_CLI_TELEMETRY_OPTOUT=1

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

# "disable" rate limiting by default by setting it to a large value
ENV DD_TRACE_RATE_LIMIT=10000000

CMD ["./ApmTestApi"]
""",
        container_cmd=[],
        container_build_dir=dotnet_absolute_appdir,
        container_build_context=_get_base_directory(),
    )

    return server


def java_library_factory():
    java_appdir = os.path.join("utils", "build", "docker", "java", "parametric")
    java_absolute_appdir = os.path.join(_get_base_directory(), java_appdir)

    # Create the relative path and substitute the Windows separator, to allow running the Docker build on Windows machines
    java_reldir = java_appdir.replace("\\", "/")
    protofile = os.path.join("utils", "parametric", "protos", "apm_test_client.proto").replace("\\", "/")

    # TODO : use official install_ddtrace.sh
    return APMLibraryTestServer(
        lang="java",
        protocol="grpc",
        container_name="java-test-client",
        container_tag="java-test-client",
        container_img=f"""
FROM maven:3.9.2-eclipse-temurin-17
WORKDIR /client
RUN mkdir ./tracer/ && wget -O ./tracer/dd-java-agent.jar https://github.com/DataDog/dd-trace-java/releases/latest/download/dd-java-agent.jar
RUN java -jar ./tracer/dd-java-agent.jar > SYSTEM_TESTS_LIBRARY_VERSION
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
RUN php -d error_reporting='' -r 'echo phpversion("ddtrace");' > SYSTEM_TESTS_LIBRARY_VERSION
ADD {php_reldir}/server.php .
""",
        container_cmd=["php", "server.php"],
        container_build_dir=php_absolute_appdir,
        container_build_context=_get_base_directory(),
        volumes=[(os.path.join(php_absolute_appdir, "server.php"), "/client/server.php"),],
        env={},
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
            FROM --platform=linux/amd64 ruby:3.2.1-bullseye
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
    )


def cpp_library_factory() -> APMLibraryTestServer:
    cpp_appdir = os.path.join("utils", "build", "docker", "cpp", "parametric")
    cpp_absolute_appdir = os.path.join(_get_base_directory(), cpp_appdir)
    cpp_reldir = cpp_appdir.replace("\\", "/")
    dockerfile_content = f"""
FROM datadog/docker-library:dd-trace-cpp-ci AS build

RUN apt-get update && apt-get -y install pkg-config libabsl-dev curl jq
WORKDIR /usr/app
COPY {cpp_reldir}/install_ddtrace.sh binaries* /binaries/
RUN sh /binaries/install_ddtrace.sh
RUN cd /binaries/dd-trace-cpp \
 && cmake -B .build -DCMAKE_BUILD_TYPE=Release -DDD_TRACE_BUILD_TESTING=1 . \
 && cmake --build .build -j $(nproc) \
 && cmake --install .build --prefix /usr/app/

FROM ubuntu:22.04
COPY --from=build /usr/app/bin/parametric-http-server /usr/local/bin/parametric-http-server
COPY --from=build /usr/app/SYSTEM_TESTS_LIBRARY_VERSION /SYSTEM_TESTS_LIBRARY_VERSION
"""

    return APMLibraryTestServer(
        lang="cpp",
        protocol="http",
        container_name="cpp-test-client",
        container_tag="cpp-test-client",
        container_img=dockerfile_content,
        container_cmd=["parametric-http-server"],
        container_build_dir=cpp_absolute_appdir,
        container_build_context=_get_base_directory(),
        env={},
    )
