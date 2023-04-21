from _validator import validate_trace
from utils import context, weblog, interfaces, scenarios, irrelevant


@scenarios.otel_tracing_e2e
@irrelevant(context.library != "open_telemetry")
class Test_OTel_E2E:
    def setup_main(self):
        self.use_128_bits_trace_id = False
        self.r = weblog.get(path="/")

    def test_main(self):
        otel_trace_ids = set(interfaces.open_telemetry.get_otel_trace_id(request=self.r))
        assert len(otel_trace_ids) == 2
        dd_trace_ids = [self._get_dd_trace_id(otel_trace_id) for otel_trace_id in otel_trace_ids]
        traces = [
            interfaces.backend.assert_otlp_trace_exist(request=self.r, dd_trace_id=dd_trace_id)
            for dd_trace_id in dd_trace_ids
        ]
        validate_trace(traces, self.use_128_bits_trace_id)

    def _get_dd_trace_id(self, otel_trace_id=bytes) -> int:
        if self.use_128_bits_trace_id:
            return int.from_bytes(otel_trace_id, "big")
        return int.from_bytes(otel_trace_id[8:], "big")
