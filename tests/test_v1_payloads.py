from utils import weblog, interfaces, scenarios


@scenarios.apm_tracing_e2e_single_span
class Test_V1Payloads:
    def setup_field_changes(self):
        self.r = weblog.get("/status?code=500")

    def test_field_changes(self):
        traces = list(interfaces.library.get_traces_v1(self.r))
        assert len(traces) == 1
        _, trace = traces[0]
        assert len(trace["spans"]) == 1
        assert len(trace["trace_id"]) == 34  # 32 bytes for ID and 2 for "0x"
        assert trace["sampling_mechanism"] == 4
        assert trace["priority"] == 1
        span = trace["spans"][0]
        assert span["error"], "Error field must be boolean"
        assert span["env"] == "system-tests"
        assert span["component"] == "net/http"
        assert span["kind"] == 2
