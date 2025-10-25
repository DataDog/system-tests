from collections.abc import Generator

import pytest

from utils.integration_frameworks import (
    FrameworkTestClientApi,
    TestAgentAPI,
)
from utils import context, scenarios, logger


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
def test_agent(
    test_id: str,
    worker_id: str,
    request: pytest.FixtureRequest,
) -> Generator[TestAgentAPI, None, None]:
    with scenarios.integration_frameworks.get_test_agent_api(
        request=request,
        worker_id=worker_id,
        test_id=test_id,
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

    with scenarios.integration_frameworks.get_client(
        request=request,
        library_env=library_env,
        worker_id=worker_id,
        test_id=test_id,
        test_agent=test_agent,
    ) as client:
        yield client
