from collections.abc import Generator
import contextlib

import pytest

from utils.integration_frameworks import (
    FrameworkTestClientFactory,
    TestAgentFactory,
    TestAgentAPI,
    FrameworkTestClientApi,
)
from utils._logger import logger
from utils._context.component_version import ComponentVersion
from utils._context.docker import get_docker_client
from .core import Scenario, scenario_groups

_NETWORK_PREFIX = "framework_shared_tests_network"


class IntegrationFrameworksScenario(Scenario):
    _test_client_factory: FrameworkTestClientFactory
    _test_agent_factory: TestAgentFactory

    def __init__(self, name: str, doc: str) -> None:
        super().__init__(name, doc=doc, github_workflow="endtoend", scenario_groups=[scenario_groups.tracer_release])

        self.environment = {
            "DD_TRACE_DEBUG": "true",
            "DD_TRACE_OTEL_ENABLED": "true",
        }

    def configure(self, config: pytest.Config):
        library: str = config.option.library
        weblog: str = config.option.weblog

        if not library:
            pytest.exit("No library specified, please set -L option", 1)

        if not weblog:
            pytest.exit("No framework specified, please set -W option", 1)

        if "@" not in weblog:
            pytest.exit("Weblog must be of the form : openai@2.0.0.", 1)

        framework, framework_version = weblog.split("@", 1)

        self._test_agent_factory = TestAgentFactory(self.host_log_folder)
        self._test_client_factory = FrameworkTestClientFactory(
            host_log_folder=self.host_log_folder,
            library=library,
            framework=framework,
            framework_version=framework_version,
            container_env=self.environment,
            container_volumes={f"./utils/build/docker/{library}/{framework}_app": "/app/integration_frameworks"},
        )

        # Set library version - for now use a placeholder, will be updated after building
        self._library = ComponentVersion(library, "0.0.0")
        logger.debug(f"Library: {library}, Framework: {framework}=={framework_version}")

        if self.is_main_worker:
            # Build the framework test server image
            self._test_client_factory.build(self.host_log_folder, github_token_file=config.option.github_token_file)
            self._test_agent_factory.pull()
            self._clean_containers()
            self._clean_networks()

    @contextlib.contextmanager
    def get_test_agent_api(
        self,
        request: pytest.FixtureRequest,
        test_id: str,
        worker_id: str,
    ) -> Generator[TestAgentAPI, None, None]:
        with (
            self._get_docker_network(test_id) as docker_network,
            self._test_agent_factory.get_test_agent_api(
                request=request,
                worker_id=worker_id,
                container_name=f"ddapm-test-agent-{test_id}",
                docker_network=docker_network,
            ) as result,
        ):
            yield result

    @contextlib.contextmanager
    def get_client(
        self,
        request: pytest.FixtureRequest,
        worker_id: str,
        test_id: str,
        library_env: dict[str, str],
        test_agent: TestAgentAPI,
    ) -> Generator[FrameworkTestClientApi, None, None]:
        with self._test_client_factory.get_client(
            request=request,
            library_env=library_env,
            worker_id=worker_id,
            test_id=test_id,
            test_agent=test_agent,
        ) as client:
            yield client

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
    def _get_docker_network(self, test_id: str) -> Generator[str, None, None]:
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
