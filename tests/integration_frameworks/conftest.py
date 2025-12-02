from collections.abc import Generator
from typing import TYPE_CHECKING
import uuid

import pytest

from utils.docker_fixtures import (
    FrameworkTestClientApi,
    TestAgentAPI,
)
from utils import context, scenarios, logger

if TYPE_CHECKING:
    from utils._context._scenarios.integration_frameworks import IntegrationFrameworksScenario


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Mark all integration_frameworks tests as xfail when generating cassettes."""
    if config.option.generate_cassettes:
        for item in items:
            item.add_marker(
                pytest.mark.xfail(
                    reason="Generating cassettes - test assertions are not evaluated",
                    strict=False,
                )
            )


@pytest.fixture
def test_id(request: pytest.FixtureRequest) -> str:
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
    framework_app_name: str,
) -> Generator[TestAgentAPI, None, None]:
    framework_scenario: IntegrationFrameworksScenario | None = getattr(
        scenarios, f"integration_frameworks_{framework_app_name}"
    )

    if framework_scenario is None:
        pytest.exit(f"Framework scenario for {framework_app_name} not found", 1)

    with framework_scenario.get_test_agent_api(  # type: ignore[union-attr]
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
    framework_app_name: str,
) -> Generator[FrameworkTestClientApi, None, None]:
    framework_scenario: IntegrationFrameworksScenario | None = getattr(
        scenarios, f"integration_frameworks_{framework_app_name}"
    )

    if framework_scenario is None:
        pytest.exit(f"Framework scenario for {framework_app_name} not found", 1)

    context.scenario.parametrized_tests_metadata[request.node.nodeid] = dict(library_env)

    with framework_scenario.get_client(  # type: ignore[union-attr]
        request=request,
        library_env=library_env,
        worker_id=worker_id,
        test_id=test_id,
        test_agent=test_agent,
    ) as client:
        yield client
