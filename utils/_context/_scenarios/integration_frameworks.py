import contextlib
import dataclasses
import os
from pathlib import Path
import shutil
import subprocess
from typing import TextIO
from collections.abc import Generator

from docker.models.networks import Network
from docker.models.containers import Container
import pytest
from _pytest.outcomes import Failed

from utils._logger import logger
from utils._context.component_version import ComponentVersion
from utils._context.docker import get_docker_client
from .core import Scenario

_NETWORK_PREFIX = "framework_shared_tests_network"


def _fail(message: str):
    """Used to mak a test as failed"""
    logger.error(message)
    raise Failed(message, pytrace=False) from None


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

    def __init__(self, name: str, doc: str) -> None:
        super().__init__(
            name,
            doc=doc,
            github_workflow="integration_frameworks",
        )
        self.framework_factory = None

    def configure(self, config: pytest.Config):
        if not config.option.library:
            pytest.exit("No library specified, please set -L option", 1)

        library = config.option.library

        factory = {
            "python": python_library_factory,
            # TODO: add Node.js and Java as well - reuse parametric definitions?
        }[library]

        framework = config.option.framework
        framework_version = config.option.framework_version
        if framework is None or framework_version is None:
            pytest.exit("No framework specified, please set -F option", 1)

        self.framework_test_server_definition = factory(framework, framework_version)

        # Set library version - for now use a placeholder, will be updated after building
        self._library = ComponentVersion(library, "0.0.0")
        logger.debug(f"Library: {library}, Framework: {framework}=={framework_version}")

        if self.is_main_worker:
            # Build the framework test server image
            self._build_framework_test_server_image(config.option.github_token_file)
            self._pull_test_agent_image()
            self._clean_containers()
            self._clean_networks()

    def _build_framework_test_server_image(self, github_token_file: str) -> None:
        logger.stdout("Build framework test container...")

        framework_test_server_definition: FrameworkTestServer = self.framework_test_server_definition

        log_path = f"{self.host_log_folder}/outputs/docker_build_log.log"
        Path.mkdir(Path(log_path).parent, exist_ok=True, parents=True)

        # Write dockerfile to the build directory
        dockf_path = os.path.join(framework_test_server_definition.container_build_dir, "Dockerfile")
        with open(dockf_path, "w", encoding="utf-8") as f:
            f.write(framework_test_server_definition.container_img)

        with open(log_path, "w+", encoding="utf-8") as log_file:
            docker_bin = shutil.which("docker")

            if docker_bin is None:
                raise FileNotFoundError("Docker not found in PATH")

            root_path = ".."
            cmd = [
                docker_bin,
                "build",
                "--progress=plain",
            ]

            if github_token_file and github_token_file.strip():
                cmd += ["--secret", f"id=github_token,src={github_token_file}"]

            cmd += [
                "-t",
                framework_test_server_definition.container_tag,
                "-f",
                dockf_path,
                framework_test_server_definition.container_build_context,
            ]
            log_file.write(f"running {cmd} in {root_path}\n")
            log_file.flush()

            env = os.environ.copy()
            env["DOCKER_SCAN_SUGGEST"] = "false"

            timeout = 600  # Python tracer can take a while to build

            p = subprocess.run(
                cmd,
                cwd=root_path,
                text=True,
                stdout=log_file,
                stderr=log_file,
                env=env,
                timeout=timeout,
                check=False,
            )

            if p.returncode != 0:
                pytest.exit(f"Failed to build framework test server image. See {log_path} for details", 1)

        logger.stdout("Build complete")

    def _pull_test_agent_image(self) -> None:
        logger.stdout(f"Pull test agent image {self.TEST_AGENT_IMAGE}...")
        get_docker_client().images.pull(self.TEST_AGENT_IMAGE)

    def _clean_containers(self) -> None:
        for container in get_docker_client().containers.list(all=True):
            if _NETWORK_PREFIX in container.name:
                logger.info(f"Remove container {container.name}")
                container.remove(force=True)

    def _clean_networks(self) -> None:
        for network in get_docker_client().networks.list():
            if _NETWORK_PREFIX in network.name:
                logger.info(f"Remove network {network.name}")
                network.remove()

    @property
    def library(self):
        return self._library

    def create_docker_network(self, test_id: str) -> Network:
        docker_network_name = f"{_NETWORK_PREFIX}_{test_id}"

        return get_docker_client().networks.create(name=docker_network_name, driver="bridge")

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
            container: Container = get_docker_client().containers.run(
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
            for container in get_docker_client().containers.list(filters={"name": name}, all=True):
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
COPY utils/build/docker/python/integration_frameworks/system_tests_library_version.sh system_tests_library_version.sh
COPY utils/build/docker/python/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh
RUN mkdir /integration-framework-tracer-logs
ENV DD_PATCH_MODULES="fastapi:false,startlette:false"
        """,
        container_cmd=["ddtrace-run", "python3.11", "-m", "integration_frameworks", framework],
        container_build_dir=python_absolute_appdir,
        container_build_context=_get_base_directory(),
        volumes={os.path.join(python_absolute_appdir): "/app/integration_frameworks"},
    )
