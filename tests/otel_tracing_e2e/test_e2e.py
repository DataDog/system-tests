import os
from _validator import validate_all_traces
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

        # The 1st account has traces sent by DD Agent
        traces_agent = [
            interfaces.backend.assert_otlp_trace_exist(
                request=self.r,
                dd_trace_id=dd_trace_id,
                dd_api_key=os.environ["DD_API_KEY"],
                dd_app_key=os.environ.get("DD_APP_KEY", os.environ["DD_APPLICATION_KEY"]),
            )
            for dd_trace_id in dd_trace_ids
        ]

        # The 2nd account has traces via the backend OTLP intake endpoint
        traces_intake = [
            interfaces.backend.assert_otlp_trace_exist(
                request=self.r,
                dd_trace_id=dd_trace_id,
                dd_api_key=os.environ["DD_API_KEY_2"],
                dd_app_key=os.environ["DD_APP_KEY_2"],
            )
            for dd_trace_id in dd_trace_ids
        ]

        # The 3rd account has traces sent by OTel Collector
        traces_collector = [
            interfaces.backend.assert_otlp_trace_exist(
                request=self.r,
                dd_trace_id=dd_trace_id,
                dd_api_key=os.environ["DD_API_KEY_3"],
                dd_app_key=os.environ["DD_APP_KEY_3"],
            )
            for dd_trace_id in dd_trace_ids
        ]

        validate_all_traces(traces_agent, traces_intake, traces_collector, self.use_128_bits_trace_id)

    def _get_dd_trace_id(self, otel_trace_id=bytes) -> int:
        if self.use_128_bits_trace_id:
            return int.from_bytes(otel_trace_id, "big")
        return int.from_bytes(otel_trace_id[8:], "big")
