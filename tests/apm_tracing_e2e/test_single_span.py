from utils import weblog, interfaces, rfc, scenario
from utils.tools import logger
from tests.apm_tracing_e2e.constants import (
    SAMPLING_PRIORITY_KEY,
    SINGLE_SPAN_SAMPLING_MECHANISM,
    SINGLE_SPAN_SAMPLING_MECHANISM_VALUE,
    SINGLE_SPAN_SAMPLING_RATE,
    SINGLE_SPAN_SAMPLING_MAX_PER_SEC,
)


@rfc("https://datadoghq.atlassian.net/browse/ATI-2419?focusedCommentId=956826")
@scenario("APM_TRACING_E2E_SINGLE_SPAN")
class Test_SingleSpan:
    """This is a test that exercises the Single Span Ingestion Control feature.
    Read more about Single Span at https://datadoghq.atlassian.net/wiki/spaces/APM/pages/2564915820/Trace+Ingestion+Mechanisms#Single-Span-Ingestion-Control

    Past incident: https://app.datadoghq.com/incidents/18687
    """

    def setup_parent_span_is_single_span(self):
        self.req = weblog.get("/e2e_single_span?parentName=parent.span.single_span_submitted&childName=child.span")

    def test_parent_span_is_single_span(self):
        # Only the parent span should be submitted to the backend!
        spans = _get_spans_submitted(self.req)
        assert 1 == len(spans), _assert_msg(1, len(spans))

        # Assert the spans sent by the agent.
        span = spans[0]
        assert span["name"] == "parent.span.single_span_submitted"
        assert span.get("parentID") is None
        assert span["metrics"]["_dd.top_level"] == 1.0
        _assert_single_span_metrics(span)

        # TODO - Assert the spans received from the backend!
        # TODO - The `/api/v1/logs-analytics/list?type=trace` API is behind user authentication...
        #        https://github.com/DataDog/dogweb/blob/prod/dogweb/controllers/api/logs/logs_queries.py#L290
        # interfaces.backend.assert_single_spans_exist(self.req)

    def setup_child_span_is_single_span(self):
        self.req = weblog.get("/e2e_single_span?parentName=parent.span&childName=child.span.single_span_submitted")

    def test_child_span_is_single_span(self):
        # Only the child should be submitted to the backend!
        spans = _get_spans_submitted(self.req)
        assert 1 == len(spans), _assert_msg(1, len(spans))

        # Assert the spans sent by the agent.
        span = spans[0]
        assert span["name"] == "child.span.single_span_submitted"
        assert span["parentID"] is not None
        _assert_single_span_metrics(span)

        # TODO - Assert the spans received from the backend!
        # TODO - The `/api/v1/logs-analytics/list?type=trace` API is behind user authentication...
        #        https://github.com/DataDog/dogweb/blob/prod/dogweb/controllers/api/logs/logs_queries.py#L290
        # interfaces.backend.assert_single_spans_exist(self.req)


def _assert_single_span_metrics(span):
    assert span["metrics"][SAMPLING_PRIORITY_KEY] == -1  # due to the global sampling rate = 0
    assert span["metrics"][SINGLE_SPAN_SAMPLING_RATE] == 1.0
    assert span["metrics"][SINGLE_SPAN_SAMPLING_MECHANISM] == SINGLE_SPAN_SAMPLING_MECHANISM_VALUE
    assert span["metrics"][SINGLE_SPAN_SAMPLING_MAX_PER_SEC] == 50.0


def _get_spans_submitted(request):
    return [span for _, _, _, span in interfaces.agent.get_spans(request)]


def _assert_msg(expected, actual):
    return f"\n\tExpected:\t{expected}\n\tActual:\t\t{actual}\n\n"
