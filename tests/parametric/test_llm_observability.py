from utils import scenarios
from utils.docker_fixtures import TestAgentAPI
from .conftest import APMLibrary
from utils.docker_fixtures.spec.llm_observability import LlmObsSpanRequest
import pytest


@pytest.fixture
def test_ml_app() -> str | None:
    return "test-app"


@pytest.fixture
def library_env(test_ml_app: str | None) -> dict[str, str]:
    env = {
        "DD_LLMOBS_ENABLED": "true",
        "DD_SERVICE": "test-service",
    }

    if test_ml_app is not None:
        env["DD_LLMOBS_ML_APP"] = test_ml_app

    return env


def _find_event_tag(event: dict, tag: str) -> str | None:
    """Find a tag in a span event or telemetry metric event."""
    tags = event["tags"]
    for t in tags:
        k, v = t.split(":")
        if k == tag:
            return v

    return None


@scenarios.parametric
class TestEnablement:
    pytest.mark.parametrize("test_ml_app", ["overridden-test-ml-app", "", None])

    def test_ml_app(self, test_agent: TestAgentAPI, test_library: APMLibrary, test_ml_app: str | None):
        llmobs_span_request = LlmObsSpanRequest(kind="task")
        test_library.llmobs_trace(llmobs_span_request)

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        task_span = span_events[0]
        ml_app = _find_event_tag(task_span, "ml_app")
        if test_ml_app:
            assert ml_app == test_ml_app
        else:
            assert ml_app == "test-service"  # default ml app is the service name
