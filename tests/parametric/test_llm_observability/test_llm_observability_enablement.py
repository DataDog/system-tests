import pytest

from tests.parametric.test_llm_observability.utils import find_event_tag
from utils import scenarios, features
from utils.docker_fixtures import TestAgentAPI
from ..conftest import APMLibrary  # noqa: TID252
from utils.docker_fixtures.spec.llm_observability import (
    LlmObsSpanRequest,
)


@features.llm_observability_sdk_enablement
@scenarios.parametric
class Test_Enablement:
    @pytest.mark.parametrize("llmobs_ml_app", ["overridden-test-ml-app", "", None])
    def test_ml_app(self, test_agent: TestAgentAPI, test_library: APMLibrary, llmobs_ml_app: str | None):
        llmobs_span_request = LlmObsSpanRequest(kind="task")
        test_library.llmobs_trace(llmobs_span_request)

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        task_span = span_events[0]
        ml_app = find_event_tag(task_span, "ml_app")
        if llmobs_ml_app:
            assert ml_app == llmobs_ml_app
        else:
            assert ml_app == "test-service"  # default ml app is the service name
