from collections.abc import Generator
import contextlib
from pathlib import Path

import pytest

from utils.integration_frameworks import FrameworkTestClientFactory, TestAgentFactory
from utils._logger import logger
from utils._context.component_version import ComponentVersion
from utils._context.docker import get_docker_client
from .core import Scenario

_NETWORK_PREFIX = "framework_shared_tests_network"


class IntegrationFrameworksScenario(Scenario):
    test_client_factory: FrameworkTestClientFactory
    test_agent_factory: TestAgentFactory

    def __init__(self, name: str, doc: str) -> None:
        super().__init__(
            name,
            doc=doc,
            github_workflow="integration_frameworks",
        )

        self.environment = {
            "DD_TRACE_DEBUG": "true",
            "DD_TRACE_OTEL_ENABLED": "true",
        }

    def configure(self, config: pytest.Config):
        library = config.option.library
        framework = config.option.framework
        framework_version = config.option.framework_version

        if not library:
            pytest.exit("No library specified, please set -L option", 1)

        if not framework or not framework_version:
            pytest.exit("No framework specified, please set -F option", 1)

        self.test_agent_factory = TestAgentFactory(self.host_log_folder)
        self.test_client_factory = FrameworkTestClientFactory(
            host_log_folder=self.host_log_folder,
            library=library,
            framework=framework,
            framework_version=framework_version,
            container_env=self.environment,
            container_volumes={
                str(
                    Path.cwd().joinpath("utils", "build", "docker", library, f"{framework}_app")
                ): "/app/integration_frameworks"
            },
        )

        # Set library version - for now use a placeholder, will be updated after building
        self._library = ComponentVersion(library, "0.0.0")
        logger.debug(f"Library: {library}, Framework: {framework}=={framework_version}")

        if self.is_main_worker:
            # Build the framework test server image
            self._build_framework_test_server_image(config.option.github_token_file)
            self.test_agent_factory.pull()
            self._clean_containers()
            self._clean_networks()

    def _build_framework_test_server_image(self, github_token_file: str) -> None:
        logger.stdout("Build framework test container...")
        self.test_client_factory.build(self.host_log_folder, github_token_file=github_token_file)
        logger.stdout("Build complete")

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

    @contextlib.contextmanager
    def get_docker_network(self, test_id: str) -> Generator[str, None, None]:
        docker_network_name = f"{_NETWORK_PREFIX}_{test_id}"
        network = get_docker_client().networks.create(name=docker_network_name, driver="bridge")

        try:
            yield network.name
        finally:
            try:
                network.remove()
            except:
                # It's possible (why?) of having some container not stopped.
                # If it happens, failing here makes stdout tough to understand.
                # Let's ignore this, later calls will clean the mess
                logger.info("Failed to remove network, ignoring the error")
