from tests.apm_tracing_e2e.test_single_span import _get_spans_submitted, _assert_msg
from utils import context, weblog, scenarios, interfaces, missing_feature, irrelevant, flaky


@missing_feature(
    context.weblog_variant not in ("net-http", "spring-boot"),
    reason="The /e2e_otel_span endpoint is only implemented in Go net/http and Java Spring Boot at the moment.",
)
@scenarios.apm_tracing_e2e_otel
class Test_Otel_Span:
    """This is a test that that exercises the full flow of APM Tracing with the use of Datadog OTel API.
    """

    def setup_datadog_otel_span(self):
        self.req = weblog.get(
            "/e2e_otel_span", {"shouldIndex": 1, "parentName": "parent.span.otel", "childName": "child.span.otel"},
        )

    # Parent span will have the following traits :
    # - spanId of 10000
    # - tags {'attributes':'values'}
    # - error tag with 'testing_end_span_options' message
    # Child span will have the following traits :
    # - tags necessary to retain the mapping between the system-tests/weblog request id and the traces/spans
    # - duration of one second
    # - span kind of SpanKind - Internal
    def test_datadog_otel_span(self):
        spans = _get_spans_submitted(self.req)
        assert 2 <= len(spans), _assert_msg(2, len(spans), "Agent did not submit the spans we want!")

        # Assert the parent span sent by the agent.
        parent = _get_span(spans, "parent.span.otel")
        assert parent.get("parentID") is None
        if parent.get("meta")["language"] != "jvm":  # Java OpenTelemetry API does not provide Span ID API
            assert parent.get("spanID") == "10000"
        assert parent.get("meta").get("attributes") == "values"
        assert parent.get("meta").get("error.message") == "testing_end_span_options"
        assert parent["metrics"]["_dd.top_level"] == 1.0

        # Assert the child sent by the agent.
        child = _get_span(spans, "child.span.otel")
        assert child.get("parentID") == parent.get("spanID")
        assert child.get("spanID") != "10000"
        assert child.get("duration") == "1000000000"
        assert child.get("type") == "internal"

        # Assert the spans received from the backend!
        spans = interfaces.backend.assert_request_spans_exist(self.req, query_filter="")
        assert 2 == len(spans), _assert_msg(2, len(spans))

    def setup_distributed_otel_trace(self):
        self.req = weblog.get("/e2e_otel_span/mixed_contrib", {"shouldIndex": 1, "parentName": "parent.span.otel"},)

    @irrelevant(condition=context.library != "golang", reason="Golang specific test with OTel Go contrib package")
    def test_distributed_otel_trace(self):
        spans = _get_spans_submitted(self.req)
        assert 3 <= len(spans), _assert_msg(3, len(spans), "Agent did not submit the spans we want!")

        # Assert the parent span sent by the agent.
        parent = _get_span(spans, "parent.span.otel")
        assert parent["name"] == "parent.span.otel"
        assert parent.get("parentID") is None
        assert parent["metrics"]["_dd.top_level"] == 1.0

        # Assert the Roundtrip child span sent by the agent, this span is created by an external OTel contrib package
        roundtrip_span = _get_span(spans, "HTTP_GET")
        assert roundtrip_span["name"] == "HTTP_GET"
        assert roundtrip_span.get("parentID") == parent.get("spanID")

        # Assert the Handler function child span sent by the agent.
        handler_span = _get_span(spans, "testOperation")
        assert handler_span["name"] == "testOperation"
        assert handler_span.get("parentID") == roundtrip_span.get("spanID")

        # Assert the spans received from the backend!
        spans = interfaces.backend.assert_request_spans_exist(self.req, query_filter="")
        assert 3 == len(spans), _assert_msg(3, len(spans))


def _get_span(spans, span_name):
    for s in spans:
        if s["name"] == span_name:
            return s
    return {}
