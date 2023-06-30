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
        id = randint(0, 10000000)
        self.trace_id = str(id)
        self.span_id = str(id)
        self.sampled = 1
        traceparent = "00-{:032x}-{:016x}-{:02x}".format(id, id, self.sampled)

        self.req = weblog.get(
            "/make_distant_call", params={"url": "http://weblog:7777"}, headers={"traceparent": traceparent}
        )

    def test_tracecontext_span(self):
        # Assert the span sent by the agent.
        spans = _get_spans_submitted(self.req)
        assert 1 == len(spans), _assert_msg(1, len(spans), "Agent did not submit the spans we want!")

        span = spans[0]
        assert span.get("traceID") == self.trace_id
        assert span.get("parentID") == self.span_id

        trace = interfaces.backend.assert_library_traces_exist(self.req)

        # Assert the spans received from the backend
        spans = interfaces.backend.assert_single_spans_exist(self.req)
        assert 1 == len(spans), _assert_msg(1, len(spans))

        span = spans[0]
        assert span.get("traceID") == self.trace_id
        assert span.get("parentID") == self.span_id

        # Assert the information in the outbound http client request
        interfaces.library.assert_trace_exists(self.req)

        assert self.req.status_code == 200
        assert self.req.json() is not None
        data = self.req.json()
        assert "traceparent" in data["request_headers"]
