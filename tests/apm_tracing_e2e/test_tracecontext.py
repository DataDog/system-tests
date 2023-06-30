from tests.apm_tracing_e2e.test_single_span import _get_spans_submitted, _assert_msg
from utils import context, weblog, scenarios, interfaces, missing_feature, irrelevant
from random import randint


@scenarios.apm_tracing_e2e_tracecontext
class Test_Tracecontext_Span:
    """This is a smoke test that exercises the full flow of APM Tracing.
    It includes trace submission, the trace flowing through the backend processing,
    and then finally successfully fetching the final trace from the API.
    """

    def setup_tracecontext_span(self):
        self.req = weblog.get("/make_distant_call", params={"url": "http://weblog:7777"})

    def test_tracecontext_span(self):
        # Assert the span sent by the agent.
        spans = _get_spans_submitted(self.req)
        assert 1 == len(spans), _assert_msg(1, len(spans), "Agent did not submit the spans we want!")

        span = spans[0]
        trace_id = span.get("traceID")
        span_id = span.get("parentID")

        # Assert the spans received from the backend
        trace = interfaces.backend.assert_library_traces_exist(self.req)
        spans = trace.get("spans")
        assert 1 == len(spans), _assert_msg(1, len(spans))

        span = spans[0]
        assert span.get("traceID") == trace_id
        assert span.get("parentID") == span_id

        # Assert the information in the outbound http client request
        interfaces.library.assert_trace_exists(self.req)

        assert self.req.status_code == 200
        assert self.req.json() is not None
        data = self.req.json()
        assert "traceparent" in data["request_headers"]
        assert "x-datadog-parent-id" not in data["request_headers"]
        assert "x-datadog-sampling-priority" not in data["request_headers"]
        assert "x-datadog-tags" not in data["request_headers"]
        assert "x-datadog-trace-id" not in data["request_headers"]
