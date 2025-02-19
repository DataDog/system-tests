import base64
import os
import time

from utils import context, weblog, interfaces, scenarios, irrelevant, features
from utils.tools import logger, get_rid_from_request
from utils.otel_validators.validator_trace import validate_all_traces
from utils.otel_validators.validator_log import validate_log, validate_log_trace_correlation
from utils.otel_validators.validator_metric import validate_metrics


def _get_dd_trace_id(otel_trace_id: str, *, use_128_bits_trace_id: bool) -> int:
    otel_trace_id_bytes = base64.b64decode(otel_trace_id)
    if use_128_bits_trace_id:
        return int.from_bytes(otel_trace_id_bytes, "big")
    return int.from_bytes(otel_trace_id_bytes[8:], "big")


@scenarios.otel_tracing_e2e
@irrelevant(context.library != "java_otel")
@features.not_reported  # FPD does not support otel libs
class Test_OTelTracingE2E:
    def setup_main(self):
        self.use_128_bits_trace_id = False
        self.r = weblog.get(path="/basic/trace")

    def test_main(self):
        otel_trace_ids = set(interfaces.open_telemetry.get_otel_trace_id(request=self.r))
        assert len(otel_trace_ids) == 2
        dd_trace_ids = [_get_dd_trace_id(otel_trace_id, self.use_128_bits_trace_id) for otel_trace_id in otel_trace_ids]

        try:
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

        except ValueError:
            logger.warning("Backend does not provide traces")
            return

        validate_all_traces(
            traces_agent, traces_intake, traces_collector, use_128_bits_trace_id=self.use_128_bits_trace_id
        )


@scenarios.otel_metric_e2e
@irrelevant(context.library != "java_otel")
@features.not_reported  # FPD does not support otel libs
class Test_OTelMetricE2E:
    def setup_main(self):
        self.start = int(time.time())
        self.r = weblog.get(path="/basic/metric")
        self.expected_metrics = [
            "example.counter",
            "example.histogram",
            "example.histogram.sum",
            "example.histogram.count",
            "example.histogram.min",
            "example.histogram.max",
        ]

    def test_main(self):
        end = int(time.time())
        rid = get_rid_from_request(self.r).lower()
        try:
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

            # The 2nd account has metrics via the backend OTLP intake endpoint
            metrics_intake = [
                interfaces.backend.query_timeseries(
                    start=self.start,
                    end=end,
                    rid=rid,
                    metric=metric,
                    dd_api_key=os.environ["DD_API_KEY_2"],
                    dd_app_key=os.environ.get("DD_APP_KEY_2"),
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

        except ValueError:
            logger.warning("Backend does not provide series")
            return

        validate_metrics(metrics_agent, metrics_collector, "Agent", "Collector")
        validate_metrics(metrics_agent, metrics_intake, "Agent", "Intake")


@scenarios.otel_log_e2e
@irrelevant(context.library != "java_otel")
@features.not_reported  # FPD does not support otel libs
class Test_OTelLogE2E:
    def setup_main(self):
        self.r = weblog.get(path="/basic/log")
        self.use_128_bits_trace_id = False

    def test_main(self):
        rid = get_rid_from_request(self.r)
        otel_trace_ids = set(interfaces.open_telemetry.get_otel_trace_id(request=self.r))
        assert len(otel_trace_ids) == 1
        dd_trace_id = _get_dd_trace_id(list(otel_trace_ids)[0], self.use_128_bits_trace_id)

        # The 1st account has logs and traces sent by Agent
        try:
            log_agent = interfaces.backend.get_logs(
                query=f"trace_id:{dd_trace_id}",
                rid=rid,
                dd_api_key=os.environ["DD_API_KEY"],
                dd_app_key=os.environ.get("DD_APP_KEY", os.environ.get("DD_APPLICATION_KEY")),
            )
            otel_log_trace_attrs = validate_log(log_agent, rid, "datadog_agent")
            trace_agent = interfaces.backend.assert_otlp_trace_exist(
                request=self.r,
                dd_trace_id=dd_trace_id,
                dd_api_key=os.environ["DD_API_KEY"],
                dd_app_key=os.environ.get("DD_APP_KEY", os.environ.get("DD_APPLICATION_KEY")),
            )
        except ValueError:
            logger.warning("Backend does not provide logs")
            return
        validate_log_trace_correlation(otel_log_trace_attrs, trace_agent)

        # The 2nd account has logs and traces sent via the backend OTLP intake endpoint
        try:
            log_intake = interfaces.backend.get_logs(
                query=f"trace_id:{dd_trace_id}",
                rid=rid,
                dd_api_key=os.environ["DD_API_KEY_2"],
                dd_app_key=os.environ["DD_APP_KEY_2"],
            )
            otel_log_trace_attrs = validate_log(log_intake, rid, "backend_endpoint")
            trace_intake = interfaces.backend.assert_otlp_trace_exist(
                request=self.r,
                dd_trace_id=dd_trace_id,
                dd_api_key=os.environ["DD_API_KEY_2"],
                dd_app_key=os.environ["DD_APP_KEY_2"],
            )
        except ValueError:
            logger.warning("Backend does not provide logs")
            return
        validate_log_trace_correlation(otel_log_trace_attrs, trace_intake)

        # The 3rd account has logs and traces sent by OTel Collector
        try:
            log_collector = interfaces.backend.get_logs(
                query=f"trace_id:{dd_trace_id}",
                rid=rid,
                dd_api_key=os.environ["DD_API_KEY_3"],
                dd_app_key=os.environ["DD_APP_KEY_3"],
            )
            otel_log_trace_attrs = validate_log(log_collector, rid, "datadog_exporter")
            trace_collector = interfaces.backend.assert_otlp_trace_exist(
                request=self.r,
                dd_trace_id=dd_trace_id,
                dd_api_key=os.environ["DD_API_KEY_3"],
                dd_app_key=os.environ["DD_APP_KEY_3"],
            )
        except ValueError:
            logger.warning("Backend does not provide traces")
            return
        validate_log_trace_correlation(otel_log_trace_attrs, trace_collector)
