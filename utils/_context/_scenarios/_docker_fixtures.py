import contextlib
from collections.abc import Generator
import os
from pathlib import Path

import pytest

from docker.errors import DockerException

from utils.docker_fixtures._test_agent import (
    TestAgentFactory,
    TestAgentAPI,
    DEFAULT_OTLP_HTTP_PORT,
    DEFAULT_OTLP_GRPC_PORT,
)
from utils.docker_fixtures._test_agent_pool import WorkerAgentPool, agent_env_key
from utils._context.docker import get_docker_client
from utils._context.constants import WeblogCategory
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
        weblog_categories: list[WeblogCategory],
        scenario_groups: tuple[ScenarioGroup, ...] = (),
    ) -> None:
        super().__init__(
            name=name,
            doc=doc,
            github_workflow=github_workflow,
            scenario_groups=[*scenario_groups, groups.all, groups.tracer_release, groups.docker_fixtures],
            weblog_categories=weblog_categories,
        )

        self._test_agent_factory = TestAgentFactory(agent_image)
        self._agent_pool: WorkerAgentPool | None = None

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
            except DockerException as e:
                # Possible exceptions:
                # - docker.errors.DockerException: Base exception for Docker errors
                # - requests.exceptions.RequestException: Underlying HTTP/connection errors
                # - ConnectionError: Docker daemon connection issues
                # It's possible (why?) of having some container not stopped.
                # If it happens, failing here makes stdout tough to understand.
                # Let's ignore this, later calls will clean the mess
                logger.info(f"Failed to remove network, ignoring the error: {e}")

    def get_agent_pool(self, worker_id: str) -> WorkerAgentPool:
        # POC: only the default agent_env ({}) is pooled, so there is at most one
        # pooled agent per xdist worker.  That is why start_agent's worker-keyed
        # host ports are safe — no two pooled agents on the same worker can collide.
        # Supporting multiple envs per worker would require per-(worker, env) port
        # allocation and is out of scope for this POC.
        if self._agent_pool is None:

            @contextlib.contextmanager
            def _creator(
                request: pytest.FixtureRequest, agent_env: dict[str, str]
            ) -> Generator[TestAgentAPI, None, None]:
                key = agent_env_key(agent_env)
                network_name = f"{_NETWORK_PREFIX}_worker_{worker_id}_{abs(hash(key))}"
                network = get_docker_client().networks.create(name=network_name, driver="bridge")
                container_name = f"ddapm-test-agent-worker-{worker_id}-{abs(hash(key))}"
                # Pooled agents use a separate host-port band (5000/5100/5200 + worker offset)
                # so a worker's persistent pooled agent never collides, on that worker, with the
                # fresh-path agent (4600/4701/4802) or the FFE mock backend (4900, added on main
                # in MockFFEAgentlessBackendServer). Bands stay non-overlapping for up to ~97
                # concurrent xdist workers, well above any real run.
                try:
                    with self._test_agent_factory.start_agent(
                        request=request,
                        worker_id=worker_id,
                        container_name=container_name,
                        docker_network=network.name,
                        agent_env=agent_env,
                        # Fixed container OTLP ports for the pooled agent. The poolable check
                        # in tests/parametric/conftest.py only pools tests using these ports,
                        # since a parametrized custom OTLP port needs an agent listening on it.
                        container_otlp_http_port=DEFAULT_OTLP_HTTP_PORT,
                        container_otlp_grpc_port=DEFAULT_OTLP_GRPC_PORT,
                        agent_port_base=5000,
                        otlp_http_port_base=5100,
                        otlp_grpc_port_base=5200,
                    ) as api:
                        yield api
                finally:
                    try:
                        network.remove()
                    except Exception as e:
                        logger.info(f"Failed to remove worker network, ignoring: {e}")

            self._agent_pool = WorkerAgentPool(_creator)
        return self._agent_pool

    @contextlib.contextmanager
    def get_test_agent_api(
        self,
        worker_id: str,
        request: pytest.FixtureRequest,
        test_id: str,
        agent_env: dict[str, str],
        container_otlp_http_port: int = DEFAULT_OTLP_HTTP_PORT,
        container_otlp_grpc_port: int = DEFAULT_OTLP_GRPC_PORT,
    ) -> Generator[TestAgentAPI, None, None]:
        with (
            self._get_docker_network(test_id) as docker_network,
            self._test_agent_factory.get_test_agent_api(
                request=request,
                worker_id=worker_id,
                docker_network=docker_network,
                container_name=f"ddapm-test-agent-{test_id}",
                agent_env=agent_env,
                container_otlp_http_port=container_otlp_http_port,
                container_otlp_grpc_port=container_otlp_grpc_port,
            ) as result,
        ):
            yield result

    @staticmethod
    def get_node_volumes() -> dict[str, str]:
        volumes = {}

        try:
            with open("./binaries/nodejs-load-from-local", encoding="utf-8") as f:
                path = f.read().strip(" \r\n")
                source = os.path.join(str(Path.cwd()), path)
                volumes[str(Path(source).resolve())] = "/volumes/dd-trace-js"
        except FileNotFoundError:
            logger.info("No local dd-trace-js found, do not mount any volume")

        return volumes

    @staticmethod
    def get_python_env_and_volumes() -> tuple[dict[str, str], dict[str, str]]:
        env = {}
        volumes = {}

        try:
            with open("./binaries/python-load-from-local", encoding="utf-8") as f:
                path = f.read().strip(" \r\n")
                source = os.path.join(str(Path.cwd()), path)
                resolved_path = Path(source).resolve()
                volumes[str(resolved_path)] = "/volumes/dd-trace-py"
                env["PYTHONPATH"] = f"{resolved_path!s}/ddtrace/bootstrap:/volumes/dd-trace-py"
        except FileNotFoundError:
            logger.info("No local dd-trace-py found, do not mount any volume or set any python path")

        return env, volumes
