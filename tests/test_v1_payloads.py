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
        assert span.raw_span["component"] in (
            "net/http",
            "tomcat-server",
        )  # TODO probably should be under check for language (go, java, ...)
        assert span.raw_span["span_kind"] == SpanKind.SERVER

        assert len(agent_traces) == 1
        _, agent_trace = agent_traces[0]
        assert agent_trace.format == AgentTraceFormat.efficient_trace_payload_format
        assert any(s.get_span_resource() == "GET /status" for s in agent_trace.spans)
        assert agent_trace.trace_id == trace.raw_trace["trace_id"]
