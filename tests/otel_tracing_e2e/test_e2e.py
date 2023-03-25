from _validator import validate_trace
from utils import context, weblog, interfaces, scenarios, missing_feature


@scenarios.otel_tracing_e2e
@missing_feature(
    context.library != "java_otel", reason="OTel tests only support OTel instrumented applications at the moment.",
)
class Test_OTel_E2E:
    def setup_main(self):
        self.use_128_bits_trace_id = False
        self.r = weblog.get(path="/")

    def test_main(self):
        otel_trace_ids = list(interfaces.library.get_otel_trace_id(request=self.r))
        assert len(otel_trace_ids) == 2
        dd_trace_ids = map(self._get_dd_trace_id, otel_trace_ids)
        traces = map(lambda dd_trace_id: interfaces.backend.assert_otlp_trace_exist(request=self.r, dd_trace_id=dd_trace_id), dd_trace_ids)
        validate_trace(traces, self.use_128_bits_trace_id)

    def _get_dd_trace_id(self, otel_trace_id=bytes) -> int:
        if self.use_128_bits_trace_id:
            return int.from_bytes(otel_trace_id, "big")
        return int.from_bytes(otel_trace_id[8:], "big")
