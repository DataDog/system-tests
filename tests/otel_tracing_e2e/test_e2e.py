import base64
import os
import time
from _validator import validate_all_traces, validate_span_metas_metrics
from utils import context, weblog, interfaces, scenarios, irrelevant


def _get_dd_trace_id(otel_trace_id=str, use_128_bits_trace_id=bool) -> int:
    otel_trace_id_bytes = base64.b64decode(otel_trace_id)
    if use_128_bits_trace_id:
        return int.from_bytes(otel_trace_id_bytes, "big")
    return int.from_bytes(otel_trace_id_bytes[8:], "big")


@scenarios.otel_tracing_e2e
@irrelevant(context.library != "open_telemetry")
class Test_OTel_E2E:
    def setup_main(self):
        self.use_128_bits_trace_id = False
        self.r = weblog.get(path="/basic/trace")

    def test_main(self):
        otel_trace_ids = set(interfaces.open_telemetry.get_otel_trace_id(request=self.r))
        assert len(otel_trace_ids) == 2
        dd_trace_ids = [_get_dd_trace_id(otel_trace_id, self.use_128_bits_trace_id) for otel_trace_id in otel_trace_ids]

        # The 1st account has traces sent by DD Agent
        traces_agent = [
            interfaces.backend.assert_otlp_trace_exist(
                request=self.r,
                dd_trace_id=dd_trace_id,
                dd_api_key=os.environ["DD_API_KEY"],
                dd_app_key=os.environ.get("DD_APP_KEY", os.environ.get("DD_APPLICATION_KEY")),
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


@scenarios.otel_tracing_container_tagging
@irrelevant(context.library != "open_telemetry")
class Test_OTelTracingContainerTagging:
    def setup_main(self):
        self.use_128_bits_trace_id = False
        self.r = weblog.get(path="/container_tagging")

    def test_main(self):
        otel_trace_ids = list(set(interfaces.open_telemetry.get_otel_trace_id(request=self.r)))
        assert len(otel_trace_ids) == 1
        dd_trace_id = _get_dd_trace_id(otel_trace_ids[0], self.use_128_bits_trace_id)

        # The 1st account has traces sent by DD Agent
        trace_agent = interfaces.backend.assert_otlp_trace_exist(
            request=self.r,
            dd_trace_id=dd_trace_id,
            dd_api_key=os.environ["DD_API_KEY"],
            dd_app_key=os.environ.get("DD_APP_KEY", os.environ.get("DD_APPLICATION_KEY")),
        )
        span_agent = None
        for item in trace_agent["spans"].items():
            span_agent = item[1]

        # The 2nd account has traces via the backend OTLP intake endpoint
        trace_intake = interfaces.backend.assert_otlp_trace_exist(
            request=self.r,
            dd_trace_id=dd_trace_id,
            dd_api_key=os.environ["DD_API_KEY_2"],
            dd_app_key=os.environ["DD_APP_KEY_2"],
        )
        span_intake = None
        for item in trace_intake["spans"].items():
            span_intake = item[1]

        # The 3rd account has traces sent by OTel Collector
        trace_collector = interfaces.backend.assert_otlp_trace_exist(
            request=self.r,
            dd_trace_id=dd_trace_id,
            dd_api_key=os.environ["DD_API_KEY_3"],
            dd_app_key=os.environ["DD_APP_KEY_3"],
        )
        span_collector = None
        for item in trace_collector["spans"].items():
            span_collector = item[1]

        validate_span_metas_metrics(
            span_agent["meta"],
            span_intake["meta"],
            span_agent["metrics"],
            span_intake["metrics"],
            "span_agent",
            "span_intake",
        )
        validate_span_metas_metrics(
            span_collector["meta"],
            span_intake["meta"],
            span_collector["metrics"],
            span_intake["metrics"],
            "span_collector",
            "span_intake",
        )
