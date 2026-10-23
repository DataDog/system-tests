from collections.abc import Callable, Generator
from contextlib import AbstractContextManager, contextmanager

from tests.parametric.conftest import APMLibrary
from utils import pytest, scenarios
from utils.docker_fixtures import TestAgentAPI, new_test_id


APMLibraryFactory = Callable[[dict[str, str | None]], AbstractContextManager[APMLibrary]]


# This fixture serves two small use cases: the SDK-default comparison in
# OTEL_PROPAGATORS and OTEL_LOG_LEVEL, and the exporting control run in
# OTEL_SDK_DISABLED. Do not use it outside these tests; contact the
# apm-shared-testing team if another use case needs it.
@pytest.fixture
def test_library_factory(
    worker_id: str,
    request: pytest.FixtureRequest,
    test_agent: TestAgentAPI,
    library_extra_command_arguments: list[str],
) -> APMLibraryFactory:
    """Observe fresh SDK processes sequentially without sharing agent data."""

    @contextmanager
    def create(library_env: dict[str, str | None]) -> Generator[APMLibrary, None, None]:
        test_agent.clear()
        scenarios.parametric.parametrized_tests_metadata[request.node.nodeid] = library_env
        with (
            scenarios.parametric.get_apm_library(
                request=request,
                worker_id=worker_id,
                test_id=new_test_id(),
                test_agent=test_agent,
                library_env=library_env,
                library_extra_command_arguments=library_extra_command_arguments,
            ) as library,
            library,
        ):
            yield library

    return create
