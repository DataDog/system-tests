from utils import scenarios
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.spec.llm_observability import ApmSpanRequest, LlmObsSpanRequest
from ..conftest import APMLibrary  # noqa: TID252
import pytest
from requests import HTTPError


def _get_id_from_exported_span_ctx(exported_span_ctx: dict, id_key: str) -> str:
    return exported_span_ctx.get(f"{id_key}_id", exported_span_ctx.get(f"{id_key}Id"))


@scenarios.parametric
class Test_Export_Span:
    def test_export_span(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        trace_structure = LlmObsSpanRequest(kind="task", export_span="implicit")
        exported_span_ctx = test_library.llmobs_trace(trace_structure)

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1
        span_event = span_events[0]

        assert exported_span_ctx is not None
        assert _get_id_from_exported_span_ctx(exported_span_ctx, "trace") == span_event["trace_id"]
        assert _get_id_from_exported_span_ctx(exported_span_ctx, "span") == span_event["span_id"]

    def test_export_span_explicit_span(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        trace_structure = LlmObsSpanRequest(kind="task", export_span="explicit")
        exported_span_ctx = test_library.llmobs_trace(trace_structure)

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1
        span_event = span_events[0]

        assert exported_span_ctx is not None
        assert _get_id_from_exported_span_ctx(exported_span_ctx, "trace") == span_event["trace_id"]
        assert _get_id_from_exported_span_ctx(exported_span_ctx, "span") == span_event["span_id"]

    def test_export_span_missing_span_throws(self, test_library: APMLibrary):
        trace_structure = ApmSpanRequest(name="test-span", export_span="implicit")
        with pytest.raises(HTTPError):
            test_library.llmobs_trace(trace_structure)

    def test_export_span_is_not_llm_obs_span_throws(self, test_library: APMLibrary):
        trace_structure = ApmSpanRequest(name="test-span", export_span="explicit")
        with pytest.raises(HTTPError):
            test_library.llmobs_trace(trace_structure)


@scenarios.parametric
class Test_Submit_Evaluation:
    pass
