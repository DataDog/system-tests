from utils import weblog, scenarios, interfaces, features
from utils.dd_types import DataDogAgentSpan


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
    def test_datadog_otel_span(self):
        spans = interfaces.agent.get_spans_list(self.req)
        assert len(spans) >= 2, "Agent did not submit the spans we want!"

        # Assert the parent span sent by the agent.
        parent = _get_span_by_resource(spans, "root-otel-name.dd-resource")
        assert parent.get("parentID") is None
        parent_meta = parent.meta
        if parent_meta["language"] != "jvm":  # Java OpenTelemetry API does not provide Span ID API
            assert parent.get("spanID") == "10000"
        assert parent_meta.get("attributes") == "values"
        assert parent_meta.get("error.message") == "testing_end_span_options"
        parent_metrics = interfaces.agent.get_span_metrics(parent)
        assert parent_metrics["_dd.top_level"] == 1.0
        # Assert the child sent by the agent.
        # childName is no longer the operation name, rather the resource name
        # after remapping the OTel attributes to Datadog semantics
        child = _get_span_by_resource(spans, "otel-name.dd-resource")
        child_meta = child.meta
        assert child.get("parentID") == parent.get("spanID")
        assert child.get("spanID") != "10000"
        assert child.get("duration") == "1000000000"
        assert child_meta.get("span.kind") == "internal"

        # Assert the spans received from the backend!
        spans = interfaces.backend.assert_request_spans_exist(self.req, query_filter="", retries=10)
        assert len(spans) == 2

    def setup_distributed_otel_trace(self):
        self.req = weblog.get(
            "/e2e_otel_span/mixed_contrib", {"shouldIndex": 1, "parentName": "root-otel-name.dd-resource"}
        )

    def test_distributed_otel_trace(self):
        spans = interfaces.agent.get_spans_list(self.req)
        assert len(spans) >= 3, "Agent did not submit the spans we want!"

        # Assert the parent span sent by the agent.
        parent = _get_span_by_resource(spans, "root-otel-name.dd-resource")
        assert parent.get_span_name() == "internal"
        assert parent.get("parentID") is None
        parent_metrics = interfaces.agent.get_span_metrics(parent)
        assert parent_metrics["_dd.top_level"] == 1.0

        # Assert the Roundtrip child span sent by the agent, this span is created by an external OTel contrib package
        roundtrip_span = _get_span_by_name(spans, "client.request")
        assert roundtrip_span.get_span_name() == "client.request"
        assert roundtrip_span.get_span_resource() == "HTTP GET"
        assert roundtrip_span.get("parentID") == parent.get("spanID")

        # Assert the Handler function child span sent by the agent.
        handler_span = _get_span_by_name(spans, "server.request")
        assert handler_span.get_span_resource() == "testOperation"
        assert handler_span.get("parentID") == roundtrip_span.get("spanID")

        # Assert the spans received from the backend!
        spans = interfaces.backend.assert_request_spans_exist(self.req, query_filter="", retries=10)
        assert len(spans) == 3


def _get_span_by_name(spans: list[DataDogAgentSpan], span_name: str) -> DataDogAgentSpan:
    for s in spans:
        if s.get_span_name() == span_name:
            return s
    raise ValueError("Span not found")


def _get_span_by_resource(spans: list[DataDogAgentSpan], resource_name: str) -> DataDogAgentSpan:
    for s in spans:
        if s.get_span_resource() == resource_name:
            return s
    raise ValueError("Span not found")
