from tests.apm_tracing_e2e.test_single_span import _get_spans_submitted, _assert_msg
from utils import context, weblog, scenarios, interfaces, missing_feature, irrelevant
from random import randint
import json


@scenarios.apm_tracing_e2e_tracecontext
class Test_Tracecontext_Span:
    """This is a smoke test that exercises the full flow of APM Tracing.
    It includes trace submission, the trace flowing through the backend processing,
    and then finally successfully fetching the final trace from the API.
    """

    def setup_tracecontext_span(self):
        self.req = weblog.get("/make_distant_call", params={"url": "http://weblog:7777"})

    def test_tracecontext_span(self):
        # Assert the weblog server span was sent by the agent.
        spans = _get_spans_submitted(self.req)
        assert 1 == len(spans), _assert_msg(1, len(spans), "Agent did not submit the spans we want!")

        # Assert all spans in the distributed trace were received from the backend
        traces = interfaces.backend.assert_library_traces_exist(self.req)
        trace = traces[0]
        spans = trace.get("spans")
        assert len(spans) >= 3, _assert_msg(3, len(spans))

        # Assert the information in the outbound http client request
        interfaces.library.assert_trace_exists(self.req)

        # Assert span information from headers against span information from the backend
        assert self.req.status_code == 200

        data = json.loads(self.req.text)
        assert "traceparent" in data["request_headers"]
        assert "x-datadog-parent-id" not in data["request_headers"]
        assert "x-datadog-sampling-priority" not in data["request_headers"]
        assert "x-datadog-tags" not in data["request_headers"]
        assert "x-datadog-trace-id" not in data["request_headers"]

        _, traceparent_trace_id, traceparent_span_id, _ = data["request_headers"]["traceparent"].split('-')

        span_id = str(int(traceparent_span_id, 16)) 
        trace_id = str(int(traceparent_trace_id, 16))
        assert span_id in spans

        span = spans[span_id]
        assert span["span_id"] == span_id
        assert span["trace_id"] == trace_id
