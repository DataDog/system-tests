from utils import weblog, interfaces, scenarios, features
from utils.dd_constants import SamplingPriority, SamplingMechanism, SpanKind
from utils.dd_types import AgentTraceFormat, LibraryTraceFormat


@features.efficient_trace_payload
class Test_V1PayloadByDefault:
    """Tracers use by default v1 trace format"""

    def test_main(self):
        for data, trace in interfaces.library.get_traces():
            assert data["path"] == "/v1.0/traces"
            assert trace.format == LibraryTraceFormat.v10


@scenarios.apm_tracing_efficient_payload
@features.efficient_trace_payload
class Test_V1Payloads:
    def setup_field_changes(self):
        self.r = weblog.get("/status?code=500")

    def test_field_changes(self):
        library_traces = list(interfaces.library.get_traces(self.r))
        agent_traces = list(interfaces.agent.get_traces(self.r))
        assert len(library_traces) == 1
        _, trace = library_traces[0]
        assert isinstance(trace.raw_trace, dict)
        assert len(trace.raw_trace["spans"]) > 0  # various tracers can return different number of spans
        assert len(trace.raw_trace["trace_id"]) == 34  # 32 bytes for ID and 2 for "0x"
        assert trace.raw_trace["sampling_mechanism"] in (
            SamplingMechanism.RULE_RATE,
            SamplingMechanism.DEFAULT,
        )  # TODO: Why is this local rule sampler for go? For JAVA it is `DEFAULT`.
        assert trace.raw_trace["priority"] == SamplingPriority.USER_KEEP
        span = trace.spans[0]
        assert span.raw_span["error"], "Error field must be boolean"
        assert span.raw_span["env"] == "system-tests"
        assert span.raw_span["component"], "Component must not be empty"
        assert span.raw_span["span_kind"] == SpanKind.SERVER

        assert len(agent_traces) == 1
        _, agent_trace = agent_traces[0]
        assert agent_trace.format == AgentTraceFormat.efficient_trace_payload_format
        assert any(s.get_span_resource() == "GET /status" for s in agent_trace.spans)
        assert agent_trace.trace_id == trace.raw_trace["trace_id"]


@scenarios.apm_tracing_efficient_payload
@features.efficient_trace_payload
class Test_V1SpanLinks:
    """Verify span links are correctly transmitted in V1 format"""

    def setup_span_links_present(self):
        self.r = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777"},
            headers={
                "x-datadog-trace-id": "2",
                "x-datadog-parent-id": "10",
                "x-datadog-tags": "_dd.p.tid=2222222222222222",
                "x-datadog-sampling-priority": "2",
                "traceparent": "00-11111111111111110000000000000002-000000003ade68b1-01",
                "tracestate": "dd=s:2;p:000000000000000a,foo=1",
            },
        )

    def test_span_links_present(self):
        """V1 spans carrying span links expose them at the top level or in attributes"""
        spans_with_links = [
            span
            for _, _, span in interfaces.library.get_spans(self.r, full_trace=True)
            if span.raw_span.get("span_links") or span.raw_span.get("attributes", {}).get("_dd.span_links")
        ]
        assert len(spans_with_links) >= 1, "Expected at least one span with span links"

        link_carrier = spans_with_links[0]
        links = link_carrier.raw_span.get("span_links") or []

        assert len(links) >= 1
        link = links[0]

        assert isinstance(link["trace_id"], str)
        assert link["trace_id"].startswith("0x")
        assert isinstance(link["span_id"], int)


@scenarios.apm_tracing_efficient_payload
@features.efficient_trace_payload
class Test_V1SpanEvents:
    """Verify span events are correctly transmitted in V1 format"""

    def setup_span_event_present(self):
        self.r = weblog.get("/add_event")

    def test_span_event_present(self):
        """Root span carries at least one span event in V1 format"""
        span = interfaces.library.get_root_span(self.r)
        assert span is not None

        events = span.raw_span.get("span_events", [])
        assert len(events) >= 1, "Expected at least one span event"

        event = events[0]

        assert "name" in event, "Span event must have a name"
        assert "time_unix_nano" in event, "Span event must have a time_unix_nano (nanoseconds)"
        assert isinstance(event["time_unix_nano"], int)
        assert event["time_unix_nano"] > 0
        assert isinstance(event["name"], str)
        assert len(event["name"]) > 0

        if "attributes" in event:
            assert isinstance(event["attributes"], dict)


@scenarios.apm_tracing_efficient_payload
@features.efficient_trace_payload
class Test_V1TopLevelSpans:
    """Verify tracers correctly mark top-level spans in V1 format"""

    def setup_root_span_is_top_level(self):
        self.r = weblog.get("/status?code=200")

    def test_root_span_is_top_level(self):
        """The root span of a trace must be marked as top-level"""
        for _, root_span in interfaces.library.get_root_spans(self.r):
            attrs = root_span.raw_span.get("attributes", {})
            assert attrs.get("_dd.top_level") == 1 or attrs.get("_dd.top_level") == 1.0, (
                f"Root span must have _dd.top_level=1 in attributes, got: {attrs.get('_dd.top_level')}"
            )
