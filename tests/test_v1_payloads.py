from utils import weblog, interfaces, scenarios, features
from utils.dd_constants import SamplingPriority, SamplingMechanism, SpanKind


@scenarios.apm_tracing_efficient_payload
@features.efficient_trace_payload
class Test_V1Payloads:
    def setup_field_changes(self):
        self.r = weblog.get("/status?code=500")

    def test_field_changes(self):
        traces = list(interfaces.library.get_traces_v1(self.r))
        agent_chunks = list(interfaces.agent.get_chunks_v1(self.r))
        assert len(traces) == 1
        _, trace = traces[0]
        assert len(trace["spans"]) == 1
        assert len(trace["trace_id"]) == 34  # 32 bytes for ID and 2 for "0x"
        assert (
            trace["sampling_mechanism"] == SamplingMechanism.RULE_RATE
        )  # TODO: Why is this local rule sampler for go?
        assert trace["priority"] == SamplingPriority.USER_KEEP
        span = trace["spans"][0]
        assert span["error"], "Error field must be boolean"
        assert span["env"] == "system-tests"
        assert span["component"] == "net/http"
        assert span["span_kind"] == SpanKind.SERVER

        assert len(agent_chunks) == 1
        _, agent_chunk = agent_chunks[0]
        assert len(agent_chunk["spans"]) == 1
        assert agent_chunk["traceID"] == trace["trace_id"]
