from collections.abc import Generator
from typing import Any
import pytest

from utils.docker_fixtures import (
    FrameworkTestClientApi,
    TestAgentAPI,
    new_test_id,
)
from utils import context, scenarios, logger


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> Generator[None, Any, None]:
    """When generating cassettes, don't let setup/assertion failures fail the run."""
    outcome = yield
    if item.config.option.generate_cassettes and call.when in ("setup", "call") and call.excinfo is not None:
        report = outcome.get_result()
        report.outcome = "skipped"
        current_filename, lineno, _ = item.location
        report.longrepr = (current_filename, lineno + 1, "Generating cassettes - test assertions are not evaluated")


@pytest.fixture
def test_id(request: pytest.FixtureRequest) -> str:
    result = new_test_id()
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
    agent_env = {}
    if not request.config.option.generate_cassettes:
        agent_env["VCR_CI_MODE"] = "1"

    with scenarios.integration_frameworks.get_test_agent_api(
        request=request,
        worker_id=worker_id,
        test_id=test_id,
        agent_env=agent_env,
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
