import base64
import os
import time

from utils import context, weblog, interfaces, scenarios, irrelevant
from utils.tools import get_rid_from_request
from ._test_validator_trace import validate_all_traces
from ._test_validator_log import validate_log, validate_log_trace_correlation
from ._test_validator_metric import validate_metrics


def _get_dd_trace_id(otel_trace_id: str, use_128_bits_trace_id: bool) -> int:
    otel_trace_id_bytes = base64.b64decode(otel_trace_id)
    if use_128_bits_trace_id:
        return int.from_bytes(otel_trace_id_bytes, "big")
    return int.from_bytes(otel_trace_id_bytes[8:], "big")


@scenarios.otel_tracing_e2e
@irrelevant(context.library != "open_telemetry")
class Test_OTelTracingE2E:
    def setup_main(self):
        self.use_128_bits_trace_id = False
        self.r = weblog.get(path="/basic/trace")
        time.sleep(5)  # wait a bit for trace agent to submit traces

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


@scenarios.otel_metric_e2e
@irrelevant(context.library != "open_telemetry")
class Test_OTelMetricE2E:
    def setup_main(self):
        self.start = int(time.time())
        self.r = weblog.get(path="/basic/metric")
        self.expected_metrics = [
            "example.counter",
            "example.histogram",
            "example.histogram.sum",
            "example.histogram.count",
            # TODO: enable send_aggregation_metrics and verify max and min once newer version of Agent is released
            # "example.histogram.min",
            # "example.histogram.max",
        ]

    def test_main(self):
        end = int(time.time())
        rid = get_rid_from_request(self.r).lower()
        # The 1st account has metrics sent by DD Agent
        metrics_agent = [
            interfaces.backend.query_timeseries(
                start=self.start,
                end=end,
                rid=rid,
                metric=metric,
                dd_api_key=os.environ["DD_API_KEY"],
                dd_app_key=os.environ.get("DD_APP_KEY", os.environ.get("DD_APPLICATION_KEY")),
            )
            for metric in self.expected_metrics
        ]

        # The 3rd account has metrics sent by OTel Collector
        metrics_collector = [
            interfaces.backend.query_timeseries(
                start=self.start,
                end=end,
                rid=rid,
                metric=metric,
                dd_api_key=os.environ["DD_API_KEY_3"],
                dd_app_key=os.environ["DD_APP_KEY_3"],
            )
            for metric in self.expected_metrics
        ]

        validate_metrics(metrics_agent, metrics_collector)


@scenarios.otel_log_e2e
@irrelevant(context.library != "open_telemetry")
class Test_OTelLogE2E:
    def setup_main(self):
        self.r = weblog.get(path="/basic/log")
        self.use_128_bits_trace_id = False

    def test_main(self):
        rid = get_rid_from_request(self.r)
        otel_trace_ids = set(interfaces.open_telemetry.get_otel_trace_id(request=self.r))
        assert len(otel_trace_ids) == 1
        dd_trace_id = _get_dd_trace_id(list(otel_trace_ids)[0], self.use_128_bits_trace_id)
        # The 3rd account has logs and traces sent by OTel Collector
        log_collector = interfaces.backend.get_logs(
            query=f"trace_id:{dd_trace_id}",
            rid=rid,
            dd_api_key=os.environ["DD_API_KEY_3"],
            dd_app_key=os.environ["DD_APP_KEY_3"],
        )
        otel_log_trace_attrs = validate_log(log_collector, rid)
        trace = interfaces.backend.assert_otlp_trace_exist(
            request=self.r,
            dd_trace_id=dd_trace_id,
            dd_api_key=os.environ["DD_API_KEY_3"],
            dd_app_key=os.environ["DD_APP_KEY_3"],
        )
        validate_log_trace_correlation(otel_log_trace_attrs, trace)
