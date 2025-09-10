import contextlib
import dataclasses
from typing import TextIO, Any
from collections.abc import Generator

import json
import glob
from functools import lru_cache
import os
from pathlib import Path
import shutil
import subprocess

import pytest
from _pytest.outcomes import Failed
import docker
from docker.errors import DockerException
from docker.models.containers import Container
from docker.models.networks import Network

from utils._context.component_version import ComponentVersion
from utils._logger import logger

from .core import Scenario, scenario_groups


def _fail(message: str):
    """Used to mak a test as failed"""
    logger.error(message)
    raise Failed(message, pytrace=False) from None


# Max timeout in seconds to keep a container running
default_subprocess_run_timeout = 300
_NETWORK_PREFIX = "apm_shared_tests_network"
# _TEST_CLIENT_PREFIX = "apm_shared_tests_container"


@lru_cache
def _get_client() -> docker.DockerClient:
    try:
        return docker.DockerClient.from_env()
    except DockerException:
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
            logger.exception("No more success with docker contexts")

        raise


@dataclasses.dataclass
class APMLibraryTestServer:
    # The library of the interface.
    lang: str
    container_name: str
    container_tag: str
    container_img: str
    container_cmd: list[str]
    container_build_dir: str
    container_build_context: str = "."

    container_port: int = 8080
    host_port: int | None = None  # Will be assigned by get_host_port()

    env: dict[str, str] = dataclasses.field(default_factory=dict)
    volumes: dict[str, str] = dataclasses.field(default_factory=dict)

    container: Container | None = None


class ParametricScenario(Scenario):
    TEST_AGENT_IMAGE = "ghcr.io/datadog/dd-apm-test-agent/ddapm-test-agent:v1.32.0"
    apm_test_server_definition: APMLibraryTestServer

    class PersistentParametricTestConf(dict):
        """Parametric tests are executed in multiple thread, we need a mechanism to persist
        each parametrized_tests_metadata on a file
        """

        def __init__(self, outer_inst: "ParametricScenario"):
            self.outer_inst = outer_inst
            # To handle correctly we need to add data by default
            self.update({"scenario": outer_inst.name})

        def __setitem__(self, item: Any, value: Any):  # noqa: ANN401
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
                with open(ctx_filename) as f:
                    file_content = f.read()
                    # Remove last carriage return and the last comma. Wrap into json array.
                    all_params = json.loads(f"[{file_content[:-2]}]")
                    # Change from array to unique dict
                    for d in all_params:
                        result.update(d)
            return result

    def __init__(self, name: str, doc: str) -> None:
        super().__init__(
            name,
            doc=doc,
            github_workflow="parametric",
            scenario_groups=[scenario_groups.all, scenario_groups.tracer_release],
        )
        self._parametric_tests_confs = ParametricScenario.PersistentParametricTestConf(self)

    @property
    def parametrized_tests_metadata(self):
        return self._parametric_tests_confs

    def configure(self, config: pytest.Config):
        if config.option.library:
            library = config.option.library
        elif "TEST_LIBRARY" in os.environ:
            library = os.getenv("TEST_LIBRARY")
        else:
            pytest.exit("No library specified, please set -L option", 1)

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
            "rust": rust_library_factory,
        }[library]

        self.apm_test_server_definition = factory()

        if self.is_main_worker:
            # https://github.com/pytest-dev/pytest-xdist/issues/271#issuecomment-826396320
            # we are in the main worker, not in a xdist sub-worker
            self._build_apm_test_server_image()
            self._pull_test_agent_image()
            self._clean_containers()
            self._clean_networks()

        # https://github.com/DataDog/system-tests/issues/2799
        if library in ("nodejs", "python", "golang", "ruby", "dotnet", "rust"):
            output = _get_client().containers.run(
                self.apm_test_server_definition.container_tag,
                remove=True,
                command=["./system_tests_library_version.sh"],
                volumes=self.compute_volumes(self.apm_test_server_definition.volumes),
            )
        else:
            output = _get_client().containers.run(
                self.apm_test_server_definition.container_tag,
                remove=True,
                command=["cat", "SYSTEM_TESTS_LIBRARY_VERSION"],
            )

        self._library = ComponentVersion(library, output.decode("utf-8"))
        logger.debug(f"Library version is {self._library}")

    def get_warmups(self):
        result = super().get_warmups()
        result.append(lambda: logger.stdout(f"Library: {self.library}"))

        return result

    def _pull_test_agent_image(self):
        logger.stdout("Pulling test agent image...")
        _get_client().images.pull(self.TEST_AGENT_IMAGE)

    def _clean_containers(self):
        """Some containers may still exists from previous unfinished sessions"""

        for container in _get_client().containers.list(all=True):
            if "test-client" in container.name or "test-agent" in container.name or "test-library" in container.name:
                logger.info(f"Removing {container}")

                container.remove(force=True)

    def _clean_networks(self):
        """Some network may still exists from previous unfinished sessions"""
        logger.info("Removing unused network")
        _get_client().networks.prune()
        logger.info("Removing unused network done")

    @property
    def library(self):
        return self._library

    @property
    def weblog_variant(self):
        return f"parametric-{self.library.name}"

    def _build_apm_test_server_image(self) -> None:
        logger.stdout("Build tested container...")

        apm_test_server_definition: APMLibraryTestServer = self.apm_test_server_definition

        log_path = f"{self.host_log_folder}/outputs/docker_build_log.log"
        Path.mkdir(Path(log_path).parent, exist_ok=True, parents=True)

        # Write dockerfile to the build directory
        # Note that this needs to be done as the context cannot be
        # specified if Dockerfiles are read from stdin.
        dockf_path = os.path.join(apm_test_server_definition.container_build_dir, "Dockerfile")
        with open(dockf_path, "w", encoding="utf-8") as f:
            f.write(apm_test_server_definition.container_img)

        with open(log_path, "w+", encoding="utf-8") as log_file:
            # Build the container
            docker = shutil.which("docker")

            if docker is None:
                raise FileNotFoundError("Docker not found in PATH")

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
            log_file.write(f"running {cmd} in {root_path}\n")
            log_file.flush()

            env = os.environ.copy()
            env["DOCKER_SCAN_SUGGEST"] = "false"  # Docker outputs an annoying synk message on every build

            # python and golang tracer takes more than 5mn to build
            timeout = (
                default_subprocess_run_timeout if apm_test_server_definition.lang not in ("python", "golang") else 600
            )

            p = subprocess.run(
                cmd,
                cwd=root_path,
                text=True,
                input=apm_test_server_definition.container_img,
                stdout=log_file,
                stderr=log_file,
                env=env,
                timeout=timeout,
                check=False,
            )

            if p.returncode != 0:
                log_file.seek(0)
                failure_text = "".join(log_file.readlines())
                pytest.exit(f"Failed to build the container: {failure_text}", 1)

            logger.debug("Build tested container finished")

    def create_docker_network(self, test_id: str) -> Network:
        docker_network_name = f"{_NETWORK_PREFIX}_{test_id}"

        return _get_client().networks.create(name=docker_network_name, driver="bridge")

    @staticmethod
    def get_host_port(worker_id: str, base_port: int) -> int:
        """Deterministic port allocation for each worker"""

        if worker_id == "master":  # xdist disabled
            return base_port

        if worker_id.startswith("gw"):
            return base_port + int(worker_id[2:])

        raise ValueError(f"Unexpected worker_id: {worker_id}")

    @staticmethod
    def compute_volumes(volumes: dict[str, str]) -> dict[str, dict]:
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
        self,
        image: str,
        name: str,
        env: dict[str, str],
        volumes: dict[str, str],
        network: str,
        host_port: int,
        container_port: int,
        command: list[str],
        log_file: TextIO,
    ) -> Generator[Container, None, None]:
        logger.info(f"Run container {name} from image {image} with host port {host_port}")

        try:
            container: Container = _get_client().containers.run(
                image,
                name=name,
                environment=env,
                volumes=self.compute_volumes(volumes),
                network=network,
                ports={f"{container_port}/tcp": host_port},
                command=command,
                detach=True,
            )
            logger.debug(f"Container {name} successfully started")
        except Exception as e:
            # at this point, even if it failed to start, the container may exists!
            for container in _get_client().containers.list(filters={"name": name}, all=True):
                container.remove(force=True)

            _fail(f"Failed to run container {name}: {e}")

        try:
            yield container
        finally:
            logger.info(f"Stopping {name}")
            container.stop(timeout=1)
            logs = container.logs()
            log_file.write(logs.decode("utf-8"))
            log_file.flush()
            container.remove(force=True)


def _get_base_directory() -> str:
    return str(Path.cwd())


def python_library_factory() -> APMLibraryTestServer:
    python_appdir = os.path.join("utils", "build", "docker", "python", "parametric")
    python_absolute_appdir = os.path.join(_get_base_directory(), python_appdir)
    return APMLibraryTestServer(
        lang="python",
        container_name="python-test-library",
        container_tag="python-test-library",
        container_img="""
FROM ghcr.io/datadog/dd-trace-py/testrunner:bca6869fffd715ea9a731f7b606807fa1b75cb71
WORKDIR /app
RUN pyenv global 3.11
RUN python3.11 -m pip install fastapi==0.89.1 uvicorn==0.20.0
COPY utils/build/docker/python/parametric/system_tests_library_version.sh system_tests_library_version.sh
COPY utils/build/docker/python/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh
RUN mkdir /parametric-tracer-logs
ENV DD_PATCH_MODULES="fastapi:false,startlette:false"
""",
        container_cmd=["ddtrace-run", "python3.11", "-m", "apm_test_client"],
        container_build_dir=python_absolute_appdir,
        container_build_context=_get_base_directory(),
        volumes={os.path.join(python_absolute_appdir, "apm_test_client"): "/app/apm_test_client"},
    )


def node_library_factory() -> APMLibraryTestServer:
    nodejs_appdir = os.path.join("utils", "build", "docker", "nodejs", "parametric")
    nodejs_absolute_appdir = os.path.join(_get_base_directory(), nodejs_appdir)
    nodejs_reldir = nodejs_appdir.replace("\\", "/")
    volumes = {}

    try:
        with open("./binaries/nodejs-load-from-local", encoding="utf-8") as f:
            path = f.read().strip(" \r\n")
            source = os.path.join(_get_base_directory(), path)
            volumes[str(Path(source).resolve())] = "/volumes/dd-trace-js"
    except FileNotFoundError:
        logger.info("No local dd-trace-js found, do not mount any volume")

    return APMLibraryTestServer(
        lang="nodejs",
        container_name="node-test-client",
        container_tag="node-test-client",
        container_img=f"""
FROM node:18.10-slim
RUN apt-get update && apt-get -y install bash curl git jq \\
  || sleep 60 && apt-get update && apt-get -y install bash curl git jq
WORKDIR /usr/app
COPY {nodejs_reldir}/package.json /usr/app/
COPY {nodejs_reldir}/package-lock.json /usr/app/
COPY {nodejs_reldir}/*.js /usr/app/
COPY {nodejs_reldir}/*.sh /usr/app/
COPY {nodejs_reldir}/npm/* /usr/app/

RUN npm install || sleep 60 && npm install

COPY {nodejs_reldir}/../install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh
RUN mkdir /parametric-tracer-logs

""",
        container_cmd=["./app.sh"],
        container_build_dir=nodejs_absolute_appdir,
        container_build_context=_get_base_directory(),
        volumes=volumes,
    )


def golang_library_factory():
    golang_appdir = os.path.join("utils", "build", "docker", "golang", "parametric")
    golang_absolute_appdir = os.path.join(_get_base_directory(), golang_appdir)
    golang_reldir = golang_appdir.replace("\\", "/")
    return APMLibraryTestServer(
        lang="golang",
        container_name="go-test-library",
        container_tag="go-oldstable-test-library",
        container_img=f"""
FROM golang:1.24

# install jq
RUN apt-get update && apt-get -y install jq
WORKDIR /app
COPY {golang_reldir}/go.mod /app
COPY {golang_reldir}/go.sum /app
COPY {golang_reldir}/. /app
# download the proper tracer version
COPY utils/build/docker/golang/install_ddtrace.sh binaries* /binaries/
COPY utils/build/docker/golang/parametric/system_tests_library_version.sh system_tests_library_version.sh
RUN /binaries/install_ddtrace.sh
RUN mkdir /parametric-tracer-logs

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
    return APMLibraryTestServer(
        lang="dotnet",
        container_name="dotnet-test-api",
        container_tag="dotnet8_0-test-api",
        container_img=f"""
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build-app
WORKDIR /app

# Opt-out of .NET SDK CLI telemetry
ENV DOTNET_CLI_TELEMETRY_OPTOUT=1

# dotnet restore
COPY {dotnet_reldir}/ApmTestApi.csproj {dotnet_reldir}/nuget.config ./
RUN dotnet restore "./ApmTestApi.csproj"

# dotnet publish
COPY {dotnet_reldir} ./
RUN dotnet publish --no-restore -c Release -o out

##################

FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build-version-tool
WORKDIR /app

# Opt-out of .NET SDK CLI telemetry
ENV DOTNET_CLI_TELEMETRY_OPTOUT=1

COPY {dotnet_reldir}/../GetAssemblyVersion ./
RUN dotnet publish -c Release -o out

##################

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y curl

# install dd-trace-dotnet (must be done before setting LD_PRELOAD)
COPY utils/build/docker/dotnet/install_ddtrace.sh binaries/ /binaries/
RUN /binaries/install_ddtrace.sh

# Opt-out of .NET SDK CLI telemetry (prevent unexpected http client spans)
ENV DOTNET_CLI_TELEMETRY_OPTOUT=1

# Set up automatic instrumentation
ENV CORECLR_ENABLE_PROFILING=1
ENV CORECLR_PROFILER='{{846F5F1C-F9AE-4B07-969E-05C26BC060D8}}'
ENV CORECLR_PROFILER_PATH=/opt/datadog/Datadog.Trace.ClrProfiler.Native.so
ENV LD_PRELOAD=/opt/datadog/continuousprofiler/Datadog.Linux.ApiWrapper.x64.so
ENV DD_DOTNET_TRACER_HOME=/opt/datadog

# disable gRPC, ASP.NET Core, and other auto-instrumentations (to prevent unexpected spans)
ENV DD_TRACE_Grpc_ENABLED=false
ENV DD_TRACE_AspNetCore_ENABLED=false
ENV DD_TRACE_Process_ENABLED=false

# copy custom tool used to get library version (built above)
COPY utils/build/docker/dotnet/parametric/system_tests_library_version.sh ./
COPY --from=build-version-tool /app/out /app

# copy the dotnet app (built above)
COPY --from=build-app /app/out /app

RUN mkdir /parametric-tracer-logs
""",
        container_cmd=["./ApmTestApi"],
        container_build_dir=dotnet_absolute_appdir,
        container_build_context=_get_base_directory(),
    )


def java_library_factory():
    java_appdir = os.path.join("utils", "build", "docker", "java", "parametric")
    java_absolute_appdir = os.path.join(_get_base_directory(), java_appdir)

    # Create the relative path and substitute the Windows separator,
    # to allow running the Docker build on Windows machines.
    java_reldir = java_appdir.replace("\\", "/")

    # TODO : use official install_ddtrace.sh
    return APMLibraryTestServer(
        lang="java",
        container_name="java-test-client",
        container_tag="java-test-client",
        container_img=f"""
FROM maven:3-eclipse-temurin-21
WORKDIR /client
RUN mkdir ./tracer
COPY {java_reldir}/src src
COPY {java_reldir}/install_ddtrace.sh .
COPY {java_reldir}/pom.xml .
COPY binaries /binaries
RUN bash install_ddtrace.sh
COPY {java_reldir}/run.sh .
RUN mkdir /parametric-tracer-logs
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
        container_name="php-test-library",
        container_tag="php-test-library",
        container_img=f"""
FROM datadog/dd-trace-ci:php-8.2_buster
RUN switch-php nts
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
# RUN mkdir /parametric-tracer-logs
""",
        container_cmd=[
            "bash",
            "-c",
            "php server.php ${SYSTEM_TESTS_EXTRA_COMMAND_ARGUMENTS:-} || sleep 2s",
        ],  # In case of crash, give time to the sidecar to upload the crash report
        container_build_dir=php_absolute_appdir,
        container_build_context=_get_base_directory(),
        volumes={os.path.join(php_absolute_appdir, "server.php"): "/client/server.php"},
        env={},
    )


def ruby_library_factory() -> APMLibraryTestServer:
    ruby_appdir = os.path.join("utils", "build", "docker", "ruby", "parametric")
    ruby_absolute_appdir = os.path.join(_get_base_directory(), ruby_appdir)
    ruby_reldir = ruby_appdir.replace("\\", "/")
    return APMLibraryTestServer(
        lang="ruby",
        container_name="ruby-test-client",
        container_tag="ruby-test-client",
        container_img=f"""
            FROM --platform=linux/amd64 ruby:3.2.1-bullseye
            WORKDIR /app
            COPY {ruby_reldir} .
            COPY {ruby_reldir}/../install_ddtrace.sh binaries* /binaries/
            COPY {ruby_reldir}/system_tests_library_version.sh system_tests_library_version.sh
            RUN bundle install
            RUN /binaries/install_ddtrace.sh
            COPY {ruby_reldir}/server.rb /app/
            RUN mkdir /parametric-tracer-logs
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
RUN mkdir /parametric-tracer-logs
"""

    return APMLibraryTestServer(
        lang="cpp",
        container_name="cpp-test-client",
        container_tag="cpp-test-client",
        container_img=dockerfile_content,
        container_cmd=["parametric-http-server"],
        container_build_dir=cpp_absolute_appdir,
        container_build_context=_get_base_directory(),
        env={},
    )


def rust_library_factory() -> APMLibraryTestServer:
    rust_appdir = os.path.join("utils", "build", "docker", "rust", "parametric")
    rust_absolute_appdir = os.path.join(_get_base_directory(), rust_appdir)
    rust_reldir = rust_appdir.replace("\\", "/")

    return APMLibraryTestServer(
        lang="rust",
        container_name="rust-test-client",
        container_tag="rust-test-client",
        container_img=f"""
FROM rust:1.84.1-slim-bookworm AS builder
WORKDIR /usr/app
COPY {rust_reldir} .
COPY {rust_reldir}/../install_ddtrace.sh ./binaries/ /binaries/
COPY {rust_reldir}/Cargo.toml /usr/app/
COPY {rust_reldir}/src /usr/app/

RUN apt-get update && apt-get install -y --no-install-recommends openssh-client git

RUN /binaries/install_ddtrace.sh

RUN \
    --mount=type=cache,target=/usr/app/target/ \
    --mount=type=cache,target=/usr/local/cargo/registry/ \
    cargo build --release && cp ./target/release/ddtrace-rs-client /usr/app

FROM debian:bookworm-slim AS final
COPY --from=builder /usr/app/ddtrace-rs-client /usr/app/ddtrace-rs-client
COPY --from=builder /usr/app/Cargo.lock /usr/app/Cargo.lock
COPY {rust_reldir}/system_tests_library_version.sh /usr/app/system_tests_library_version.sh
RUN mkdir /parametric-tracer-logs
WORKDIR /usr/app
            """,
        container_cmd=["./ddtrace-rs-client"],
        container_build_dir=rust_absolute_appdir,
        container_build_context=_get_base_directory(),
        env={},
    )
