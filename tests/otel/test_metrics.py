import os
import time

from utils import context, weblog, interfaces, scenarios, irrelevant, features, logger

def validate_example_counter_new(metric: dict, name: str, value: str) -> None:
    assert metric["name"] == name
    assert "sum" in metric # This asserts the metric type is a counter
    assert len(metric["sum"]["dataPoints"]) == 1
    assert metric["sum"]["dataPoints"][0]["asInt"] == value
    assert metric["sum"]["aggregationTemporality"] == "AGGREGATION_TEMPORALITY_DELTA"
    assert metric["sum"]["isMonotonic"] == True

def validate_example_histogram_new(metric: dict) -> None:
    assert metric["name"] == "example.histogram"
    assert "histogram" in metric # This asserts the metric type is a histogram
    assert len(metric["histogram"]["dataPoints"]) == 1
    assert metric["histogram"]["dataPoints"][0]["count"] == "1"
    assert metric["histogram"]["dataPoints"][0]["sum"] == 33.0
    assert metric["histogram"]["dataPoints"][0]["min"] == 33.0
    assert metric["histogram"]["dataPoints"][0]["max"] == 33.0
    assert metric["histogram"]["aggregationTemporality"] == "AGGREGATION_TEMPORALITY_DELTA"

def validate_example_upDownCounter_new(metric: dict, name: str, value: str) -> None:
    assert metric["name"] == name
    assert "sum" in metric # This asserts the metric type is a counter
    assert len(metric["sum"]["dataPoints"]) == 1
    assert metric["sum"]["dataPoints"][0]["asInt"] == value
    assert metric["sum"]["aggregationTemporality"] == "AGGREGATION_TEMPORALITY_CUMULATIVE"

def validate_example_gauge_new(metric: dict) -> None:
    assert metric["name"] == "example.gauge"
    assert "gauge" in metric # This asserts the metric type is a gauge
    assert len(metric["gauge"]["dataPoints"]) == 1
    assert metric["gauge"]["dataPoints"][0]["asDouble"] == 77.0

def validate_example_async_gauge_new(metric: dict) -> None:
    assert metric["name"] == "example.async.gauge"
    assert "gauge" in metric # This asserts the metric type is a gauge
    assert len(metric["gauge"]["dataPoints"]) == 1
    assert metric["gauge"]["dataPoints"][0]["asDouble"] == 88.0


@scenarios.otel_metric_e2e
@irrelevant(context.library != "java_otel")
@features.not_reported  # FPD does not support otel libs
class Test_OTelMetrics:
    def setup_agent_otlp_upload(self):
        self.start = int(time.time())
        self.r = weblog.get(path="/basic/metric")
        self.expected_metrics = [
            "example.counter",
            "example.async.counter",
            "example.gauge",
            "example.async.gauge",
            "example.upDownCounter",
            "example.async.upDownCounter",
            "example.histogram",
        ]

    def test_agent_otlp_upload(self):
        end = int(time.time())
        rid = self.r.get_rid().lower()
        seen = set()

        try:
            metrics_agent = []
            for _, metric in interfaces.open_telemetry.get_metrics(host="agent"):
                if metric["name"].startswith("example"):
                    # Asynchronous instruments report on each metric read, so we need to deduplicate
                    # Also, the UpDownCounter instrument (in addition to the AsyncUpDownCounter instrument) is cumulative, so we need to deduplicate
                    if metric["name"].startswith("example.async") or metric["name"] == "example.upDownCounter":
                        if metric["name"] not in seen:
                            metrics_agent.append(metric)
                            seen.add(metric["name"])
                    else:
                        metrics_agent.append(metric)

        except ValueError as e:
            logger.warning("Backend does not provide series")
            logger.warning(e)
            return

        print(metrics_agent)

        assert len(metrics_agent) == len(self.expected_metrics), "Agent metrics should match expected"

        for metric in metrics_agent:
            if metric["name"] == "example.counter":
                validate_example_counter_new(metric, "example.counter", "11")
            elif metric["name"] == "example.async.counter":
                validate_example_counter_new(metric, "example.async.counter", "22")
            elif metric["name"] == "example.histogram":
                validate_example_histogram_new(metric)
            elif metric["name"] == "example.upDownCounter":
                validate_example_upDownCounter_new(metric, "example.upDownCounter", "55")
            elif metric["name"] == "example.async.upDownCounter":
                validate_example_upDownCounter_new(metric, "example.async.upDownCounter", "66")
            elif metric["name"] == "example.gauge":
                validate_example_gauge_new(metric)
            elif metric["name"] == "example.async.gauge":
                validate_example_async_gauge_new(metric)
            else:
                assert False, f"Metric {metric["name"]} not expected"