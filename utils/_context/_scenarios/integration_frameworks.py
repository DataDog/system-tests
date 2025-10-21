import contextlib
from functools import lru_cache
import subprocess
from typing import Generator, TextIO
import docker
from docker.errors import DockerException
from docker.models.networks import Network
from _pytest.outcomes import Failed

from utils._logger import logger
from .core import Scenario
import pytest
import os
import dataclasses
from docker.models.containers import Container
from pathlib import Path

_NETWORK_PREFIX = "framework_shared_tests_network"

def _fail(message: str):
    """Used to mak a test as failed"""
    logger.error(message)
    raise Failed(message, pytrace=False) from None

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
class FrameworkTestServer:
    """The library of the interface."""
    lang: str
    framework: str
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

class IntegrationFrameworksScenario(Scenario):
    TEST_AGENT_IMAGE = "ghcr.io/datadog/dd-apm-test-agent/ddapm-test-agent:v1.36.0"
    framework_test_server_definition: FrameworkTestServer

    def __init__(self):
        super().__init__()
        self.framework_factory = None

    def configure(self, config: pytest.Config):
        if config.option.library:
            library = config.option.library
        elif "TEST_LIBRARY" in os.environ:
            library = os.getenv("TEST_LIBRARY")
        else:
            pytest.exit("No library specified, please set -L option", 1)

        factory = {
            "python": python_library_factory,
            # TODO: add Node.js and Java as well - reuse parametric definitions?
        }[library]

        framework = config.option.framework
        framework_version = config.option.framework_version
        if framework is None or framework_version is None:
            pytest.exit("No framework specified, please set -F option", 1)
        
        self.framework_test_server_definition = factory(framework, framework_version)

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

    @contextlib.contextmanager
    def docker_run(
        self,
        image: str,
        name: str,
        env: dict[str, str],
        volumes: dict[str, str],
        network: str,
        ports: dict[str, int],
        command: list[str],
        log_file: TextIO,
    ) -> Generator[Container, None, None]:
        logger.info(f"Run container {name} from image {image} with ports {ports}")

        try:
            container: Container = _get_client().containers.run(
                image,
                name=name,
                environment=env,
                volumes=self.compute_volumes(volumes),
                network=network,
                ports=ports,
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

def python_library_factory(framework: str, framework_version: str):
    python_appdir = os.path.join("utils", "build", "docker", "python", "integration_frameworks")
    python_absolute_appdir = os.path.join(_get_base_directory(), python_appdir)
    return FrameworkTestServer(
        lang="python",
        framework=framework,
        container_name=f"python-test-library-{framework}-{framework_version}",
        container_tag=f"python-test-library-{framework}-{framework_version}",
        container_img=f"""
FROM ghcr.io/datadog/dd-trace-py/testrunner:bca6869fffd715ea9a731f7b606807fa1b75cb71
WORKDIR /app
RUN pyenv global 3.11
RUN python3.11 -m pip install fastapi==0.89.1 uvicorn==0.20.0 opentelemetry-exporter-otlp==1.36.0
RUN python3.11 -m pip install {framework}=={framework_version}
COPY utils/build/docker/python/parametric/system_tests_library_version.sh system_tests_library_version.sh
COPY utils/build/docker/python/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh
RUN mkdir /parametric-tracer-logs
ENV DD_PATCH_MODULES="fastapi:false,startlette:false"
        """,
        container_cmd=["ddtrace-run", "python3.11", "-m", "integration_frameworks", framework],
        container_build_dir=python_absolute_appdir,
        container_build_context=_get_base_directory(),
    )