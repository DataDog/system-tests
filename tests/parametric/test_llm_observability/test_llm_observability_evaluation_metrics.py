from tests.parametric.test_llm_observability.utils import find_event_tag
from utils import scenarios
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.spec.llm_observability import ApmSpanRequest, LlmObsEvaluationRequest, LlmObsSpanRequest
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
    def test_submit_evaluation_metric_simple_categorical(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        evaluation_request = LlmObsEvaluationRequest(
            trace_id="123",
            span_id="456",
            label="foo",
            metric_type="categorical",
            value="bar",
            tags={"baz": "qux"},
            ml_app="test_ml_app",
            timestamp_ms=1234567890,
        )

        test_library.llmobs_submit_evaluation(evaluation_request)
        evaluation_metrics = test_agent.wait_for_llmobs_evaluations_requests(num=1)
        assert len(evaluation_metrics) == 1

        evaluation_metric = evaluation_metrics[0]

        if evaluation_metric.get("join_on", None) is not None:
            assert evaluation_metric["join_on"]["span"]["trace_id"] == "123"
            assert evaluation_metric["join_on"]["span"]["span_id"] == "456"
        else:
            assert evaluation_metric["trace_id"] == "123"
            assert evaluation_metric["span_id"] == "456"

        assert evaluation_metric["label"] == "foo"
        assert evaluation_metric["metric_type"] == "categorical"
        assert evaluation_metric["categorical_value"] == "bar"
        assert evaluation_metric["ml_app"] == "test_ml_app"
        assert evaluation_metric["timestamp_ms"] == 1234567890
        assert evaluation_metric["ml_app"] == "test_ml_app"

        assert find_event_tag(evaluation_metric, "baz") == "qux"
        assert find_event_tag(evaluation_metric, "ddtrace.version") is not None

    def test_submit_evaluation_metric_simple_score(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        evaluation_request = LlmObsEvaluationRequest(
            trace_id="123",
            span_id="456",
            label="foo",
            metric_type="score",
            ml_app="test_ml_app",
            value=0.5,
        )

        test_library.llmobs_submit_evaluation(evaluation_request)
        evaluation_metrics = test_agent.wait_for_llmobs_evaluations_requests(num=1)
        assert len(evaluation_metrics) == 1
        evaluation_metric = evaluation_metrics[0]

        if evaluation_metric.get("join_on", None) is not None:
            assert evaluation_metric["join_on"]["span"]["trace_id"] == "123"
            assert evaluation_metric["join_on"]["span"]["span_id"] == "456"
        else:
            assert evaluation_metric["trace_id"] == "123"
            assert evaluation_metric["span_id"] == "456"

        assert evaluation_metric["label"] == "foo"
        assert evaluation_metric["metric_type"] == "score"
        assert evaluation_metric["score_value"] == 0.5
        assert evaluation_metric["ml_app"] == "test_ml_app"

        assert find_event_tag(evaluation_metric, "ddtrace.version") is not None

    def test_submit_evaluation_infers_ml_app(
        self, test_agent: TestAgentAPI, test_library: APMLibrary, llmobs_ml_app: str | None
    ):
        evaluation_request = LlmObsEvaluationRequest(
            trace_id="123",
            span_id="456",
            label="foo",
            metric_type="score",
            value=0.5,
        )

        test_library.llmobs_submit_evaluation(evaluation_request)
        evaluation_metrics = test_agent.wait_for_llmobs_evaluations_requests(num=1)
        assert len(evaluation_metrics) == 1
        evaluation_metric = evaluation_metrics[0]

        assert evaluation_metric["ml_app"] == llmobs_ml_app  # inferred from the global configuration

    def test_submit_evaluation_throws_for_missing_trace_id(self, test_library: APMLibrary):
        evaluation_request = LlmObsEvaluationRequest(
            span_id="456",
            label="foo",
            metric_type="score",
            value=0.5,
        )
        with pytest.raises(HTTPError):
            test_library.llmobs_submit_evaluation(evaluation_request)

    def test_submit_evaluation_throws_for_missing_span_id(self, test_library: APMLibrary):
        evaluation_request = LlmObsEvaluationRequest(
            trace_id="123",
            label="foo",
            metric_type="score",
            value=0.5,
        )
        with pytest.raises(HTTPError):
            test_library.llmobs_submit_evaluation(evaluation_request)

    def test_submit_evaluation_defaults_timestamp(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        evaluation_request = LlmObsEvaluationRequest(
            trace_id="123",
            span_id="456",
            label="foo",
            metric_type="score",
            value=0.5,
        )

        test_library.llmobs_submit_evaluation(evaluation_request)
        evaluation_metrics = test_agent.wait_for_llmobs_evaluations_requests(num=1)
        assert len(evaluation_metrics) == 1
        evaluation_metric = evaluation_metrics[0]

        assert evaluation_metric["timestamp_ms"] is not None
        assert evaluation_metric["timestamp_ms"] > 0

    def test_submit_evaluation_throws_for_negative_timestamp(self, test_library: APMLibrary):
        evaluation_request = LlmObsEvaluationRequest(
            trace_id="123",
            span_id="456",
            label="foo",
            metric_type="score",
            value=0.5,
            timestamp_ms=-1,
        )
        with pytest.raises(HTTPError):
            test_library.llmobs_submit_evaluation(evaluation_request)

    def test_submit_evaluation_throws_for_non_number_timestamp(self, test_library: APMLibrary):
        evaluation_request = LlmObsEvaluationRequest(
            trace_id="123",
            span_id="456",
            label="foo",
            metric_type="score",
            value=0.5,
            timestamp_ms="not a number",
        )
        with pytest.raises(HTTPError):
            test_library.llmobs_submit_evaluation(evaluation_request)

    def test_submit_evaluation_throws_for_missing_label(self, test_library: APMLibrary):
        evaluation_request = LlmObsEvaluationRequest(
            trace_id="123",
            span_id="456",
            metric_type="score",
            value=0.5,
        )
        with pytest.raises(HTTPError):
            test_library.llmobs_submit_evaluation(evaluation_request)

    def test_submit_evaluation_throws_for_label_value_with_dot(self, test_library: APMLibrary):
        evaluation_request = LlmObsEvaluationRequest(
            trace_id="123",
            span_id="456",
            metric_type="score",
            label="foo.0",
            value=0.5,
        )

        with pytest.raises(HTTPError):
            test_library.llmobs_submit_evaluation(evaluation_request)

    def test_submit_evaluation_throws_for_bad_metric_type(self, test_library: APMLibrary):
        evaluation_request = LlmObsEvaluationRequest(
            trace_id="123",
            span_id="456",
            label="foo",
            metric_type="bad",
            value=0.5,
        )

        with pytest.raises(HTTPError):
            test_library.llmobs_submit_evaluation(evaluation_request)

    def test_submit_evaluation_throws_for_categorical_with_non_string_value(self, test_library: APMLibrary):
        evaluation_request = LlmObsEvaluationRequest(
            trace_id="123",
            span_id="456",
            label="foo",
            metric_type="categorical",
            value=0.5,
        )

        with pytest.raises(HTTPError):
            test_library.llmobs_submit_evaluation(evaluation_request)

    def test_submit_evaluation_throws_for_score_with_non_number_value(self, test_library: APMLibrary):
        evaluation_request = LlmObsEvaluationRequest(
            trace_id="123",
            span_id="456",
            label="foo",
            metric_type="score",
            value="not a number",
        )

        with pytest.raises(HTTPError):
            test_library.llmobs_submit_evaluation(evaluation_request)

    def test_submit_evaluation_metric_with_joining_key(self, test_library: APMLibrary, test_agent: TestAgentAPI):
        evaluation_request = LlmObsEvaluationRequest(
            span_with_tag_value={
                "tag_key": "foo",
                "tag_value": "bar",
            },
            label="foo",
            metric_type="score",
            value=0.5,
        )

        test_library.llmobs_submit_evaluation(evaluation_request)
        evaluation_metrics = test_agent.wait_for_llmobs_evaluations_requests(num=1)
        assert len(evaluation_metrics) == 1
        evaluation_metric = evaluation_metrics[0]

        assert evaluation_metric["join_on"]["tag"]["key"] == "foo"
        assert evaluation_metric["join_on"]["tag"]["value"] == "bar"

    def test_submit_evaluation_metric_with_joining_key_and_span_throws(self, test_library: APMLibrary):
        evaluation_request = LlmObsEvaluationRequest(
            trace_id="123",
            span_id="456",
            span_with_tag_value={
                "tag_key": "foo",
                "tag_value": "bar",
            },
        )

        with pytest.raises(HTTPError):
            test_library.llmobs_submit_evaluation(evaluation_request)

    def test_submit_evaluation_metric_with_joining_key_without_tag_key_throws(self, test_library: APMLibrary):
        evaluation_request = LlmObsEvaluationRequest(
            span_with_tag_value={
                "tag_value": "bar",
            },
        )
        with pytest.raises(HTTPError):
            test_library.llmobs_submit_evaluation(evaluation_request)

    def test_submit_evaluation_metric_with_joining_key_non_string_tag_key_throws(self, test_library: APMLibrary):
        evaluation_request = LlmObsEvaluationRequest(
            span_with_tag_value={
                "tag_key": 1,
                "tag_value": "bar",
            },
        )
        with pytest.raises(HTTPError):
            test_library.llmobs_submit_evaluation(evaluation_request)

    def test_submit_evaluation_metric_with_joining_key_non_string_tag_value_throws(self, test_library: APMLibrary):
        evaluation_request = LlmObsEvaluationRequest(
            span_with_tag_value={
                "tag_key": "foo",
                "tag_value": 1,
            },
        )
        with pytest.raises(HTTPError):
            test_library.llmobs_submit_evaluation(evaluation_request)
