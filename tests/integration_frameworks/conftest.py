from collections.abc import Generator

import pytest

from utils.integration_frameworks import (
    FrameworkTestClientApi,
    TestAgentAPI,
)
from utils import context, scenarios, logger

# Max timeout in seconds to keep a container running
default_subprocess_run_timeout = 300


@pytest.fixture
def test_id(request: pytest.FixtureRequest) -> str:
    import uuid

    result = str(uuid.uuid4())[0:6]
    logger.info(f"Test {request.node.nodeid} ID: {result}")
    return result


@pytest.fixture
def library_env() -> dict[str, str]:
    return {}


@pytest.fixture
def docker_network(test_id: str) -> Generator[str, None, None]:
    with scenarios.integration_frameworks.get_docker_network(test_id) as name:
        yield name


@pytest.fixture
def test_agent(
    test_id: str,
    worker_id: str,
    docker_network: str,
    request: pytest.FixtureRequest,
) -> Generator[TestAgentAPI, None, None]:
    with scenarios.integration_frameworks.test_agent_factory.get_test_agent_api(
        request=request,
        worker_id=worker_id,
        container_name=f"ddapm-test-agent-{test_id}",
        docker_network=docker_network,
    ) as result:
        yield result


@pytest.fixture
def test_client(
    request: pytest.FixtureRequest,
    library_env: dict[str, str],
    test_id: str,
    worker_id: str,
    test_agent: TestAgentAPI,
) -> Generator[FrameworkTestClientApi, None, None]:
    context.scenario.parametrized_tests_metadata[request.node.nodeid] = dict(library_env)

    framework_test_server = scenarios.integration_frameworks.test_client_factory
    with framework_test_server.get_client(
        request=request,
        library_env=library_env,
        worker_id=worker_id,
        test_id=test_id,
        test_agent=test_agent,
    ) as client:
        yield client
