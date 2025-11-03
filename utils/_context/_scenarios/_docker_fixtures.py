import contextlib
from collections.abc import Generator

import pytest

from utils.docker_fixtures._test_agent import TestAgentFactory, TestAgentAPI
from utils._context.docker import get_docker_client
from utils._logger import logger
from .core import Scenario, ScenarioGroup, scenario_groups as groups


_NETWORK_PREFIX = "apm_shared_tests_network"


class DockerFixturesScenario(Scenario):
    def __init__(
        self,
        name: str,
        github_workflow: str,
        doc: str,
        agent_image: str,
        scenario_groups: tuple[ScenarioGroup, ...] = (),
    ) -> None:
        super().__init__(
            name=name,
            doc=doc,
            github_workflow=github_workflow,
            scenario_groups=[*scenario_groups, groups.all, groups.tracer_release, groups.docker_fixtures],
        )

        self._test_agent_factory = TestAgentFactory(agent_image)

    def _clean(self):
        if self.is_main_worker:
            self._clean_containers()
            self._clean_networks()

    def _clean_containers(self):
        """Some containers may still exists from previous unfinished sessions"""

        for container in get_docker_client().containers.list(all=True):
            if "test-client" in container.name or "test-agent" in container.name or "test-library" in container.name:
                logger.info(f"Removing {container}")

                container.remove(force=True)

    def _clean_networks(self):
        """Some network may still exists from previous unfinished sessions"""
        logger.info("Removing unused network")
        get_docker_client().networks.prune()
        logger.info("Removing unused network done")

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

    @contextlib.contextmanager
    def get_test_agent_api(
        self,
        worker_id: str,
        request: pytest.FixtureRequest,
        test_id: str,
        container_otlp_http_port: int = 4318,
        container_otlp_grpc_port: int = 4317,
    ) -> Generator[TestAgentAPI, None, None]:
        with (
            self._get_docker_network(test_id) as docker_network,
            self._test_agent_factory.get_test_agent_api(
                request=request,
                worker_id=worker_id,
                docker_network=docker_network,
                container_name=f"ddapm-test-agent-{test_id}",
                container_otlp_http_port=container_otlp_http_port,
                container_otlp_grpc_port=container_otlp_grpc_port,
            ) as result,
        ):
            yield result
