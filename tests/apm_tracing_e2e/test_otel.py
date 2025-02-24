from utils import context, weblog, scenarios, interfaces, irrelevant, bug, features, flaky


@features.otel_api
@scenarios.apm_tracing_e2e_otel
class Test_Otel_Span:
    """This is a test that that exercises the full flow of APM Tracing with the use of Datadog OTel API."""

    def setup_datadog_otel_span(self):
        self.req = weblog.get(
            "/e2e_otel_span",
            {"shouldIndex": 1, "parentName": "root-otel-name.dd-resource", "childName": "otel-name.dd-resource"},
        )

    # Parent span will have the following traits :
    # - spanId of 10000
    # - tags {'attributes':'values'}
    # - error tag with 'testing_end_span_options' message
    # Child span will have the following traits :
    # - tags necessary to retain the mapping between the system-tests/weblog request id and the traces/spans
    # - duration of one second
    # - span kind of SpanKind - Internal
    @bug(context.library == "java", reason="APMAPI-912")
    @flaky(library="golang", reason="APMAPI-178")
    def test_datadog_otel_span(self):
        spans = interfaces.agent.get_spans_list(self.req)
        assert len(spans) >= 2, "Agent did not submit the spans we want!"

        # Assert the parent span sent by the agent.
        parent = _get_span_by_resource(spans, "root-otel-name.dd-resource")
        assert parent.get("parentID") is None
        if parent.get("meta")["language"] != "jvm":  # Java OpenTelemetry API does not provide Span ID API
            assert parent.get("spanID") == "10000"
        assert parent.get("meta").get("attributes") == "values"
        assert parent.get("meta").get("error.message") == "testing_end_span_options"
        assert parent["metrics"]["_dd.top_level"] == 1.0
        # Assert the child sent by the agent.
        # childName is no longer the operation name, rather the resource name
        # after remapping the OTel attributes to Datadog semantics
        child = _get_span_by_resource(spans, "otel-name.dd-resource")
        assert child.get("parentID") == parent.get("spanID")
        assert child.get("spanID") != "10000"
        assert child.get("duration") == "1000000000"
        assert child.get("meta").get("span.kind") == "internal"

        # Assert the spans received from the backend!
        spans = interfaces.backend.assert_request_spans_exist(self.req, query_filter="", retries=10)
        assert len(spans) == 2

    def setup_distributed_otel_trace(self):
        self.req = weblog.get(
            "/e2e_otel_span/mixed_contrib", {"shouldIndex": 1, "parentName": "root-otel-name.dd-resource"}
        )

    @irrelevant(condition=context.library != "golang", reason="Golang specific test with OTel Go contrib package")
    @flaky(library="golang", reason="APMAPI-178")
    def test_distributed_otel_trace(self):
        spans = interfaces.agent.get_spans_list(self.req)
        assert len(spans) >= 3, "Agent did not submit the spans we want!"

        # Assert the parent span sent by the agent.
        parent = _get_span_by_resource(spans, "root-otel-name.dd-resource")
        assert parent["name"] == "internal"
        assert parent.get("parentID") is None
        assert parent["metrics"]["_dd.top_level"] == 1.0

        # Assert the Roundtrip child span sent by the agent, this span is created by an external OTel contrib package
        roundtrip_span = _get_span_by_name(spans, "client.request")
        assert roundtrip_span["name"] == "client.request"
        assert roundtrip_span["resource"] == "HTTP GET"
        assert roundtrip_span.get("parentID") == parent.get("spanID")

        # Assert the Handler function child span sent by the agent.
        handler_span = _get_span_by_name(spans, "server.request")
        assert handler_span["resource"] == "testOperation"
        assert handler_span.get("parentID") == roundtrip_span.get("spanID")

        # Assert the spans received from the backend!
        spans = interfaces.backend.assert_request_spans_exist(self.req, query_filter="", retries=10)
        assert len(spans) == 3


def _get_span_by_name(spans, span_name):
    for s in spans:
        if s["name"] == span_name:
            return s
    return {}


def _get_span_by_resource(spans, resource_name):
    for s in spans:
        if s["resource"] == resource_name:
            return s
    return {}
