# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2025 Datadog, Inc.

"""System test for OTLP trace metrics export (Phase 2).

When DD_TRACE_OTEL_STATS_COMPUTATION_ENABLED=true the tracer computes client-side span
stats and exports them as OTLP metrics to /v1/metrics.  The single expected metric is
dd.trace.span.duration (Histogram), whose data points are split by a
(error, dd.top_level) attribute matrix:

  { dd.top_level: false }                   — ok, not top-level
  { dd.top_level: true  }                   — ok, top-level
  { error: true, dd.top_level: false }      — error, not top-level
  { error: true, dd.top_level: true  }      — error, top-level

The `error` attribute is only present when error=true; ok data points carry no error
attribute.  Data points with count=0 are omitted.
"""

from utils import features, interfaces, scenarios, weblog


@features.otlp_trace_metrics
@scenarios.apm_tracing_otlp_metrics
class Test_OTLP_Trace_Metrics:
    """dd.trace.span.duration histogram must be exported to /v1/metrics with the expected attribute matrix."""

    def setup_duration_histogram_present(self):
        weblog.get("/")

    def test_duration_histogram_present(self):
        payloads = list(interfaces.open_telemetry.get_otel_metrics())
        assert payloads, "No OTLP metrics payloads captured on /v1/metrics"

        metrics_found: dict[str, list] = {}
        for _, content in payloads:
            for rm in content.get("resourceMetrics") or []:
                for sm in rm.get("scopeMetrics") or []:
                    for metric in sm.get("metrics") or []:
                        name = metric.get("name")
                        if name:
                            metrics_found.setdefault(name, []).append(metric)

        assert "dd.trace.span.duration" in metrics_found, (
            f"Expected 'dd.trace.span.duration' metric. Found: {sorted(metrics_found)}"
        )

        unexpected = set(metrics_found) - {"dd.trace.span.duration"}
        assert not unexpected, (
            f"Unexpected extra metrics found (old 4-metric format?): {sorted(unexpected)}"
        )

    def setup_data_points_have_top_level_attribute(self):
        weblog.get("/")

    def test_data_points_have_top_level_attribute(self):
        payloads = list(interfaces.open_telemetry.get_otel_metrics())
        assert payloads, "No OTLP metrics payloads captured on /v1/metrics"

        data_points = []
        for _, content in payloads:
            for rm in content.get("resourceMetrics") or []:
                for sm in rm.get("scopeMetrics") or []:
                    for metric in sm.get("metrics") or []:
                        if metric.get("name") == "dd.trace.span.duration":
                            histogram = metric.get("histogram") or {}
                            data_points.extend(histogram.get("dataPoints") or [])

        assert data_points, "dd.trace.span.duration histogram has no data points"

        for dp in data_points:
            attr_keys = {a.get("key") for a in dp.get("attributes") or []}
            assert "dd.top_level" in attr_keys, (
                f"Data point missing required 'dd.top_level' attribute. Attributes: {attr_keys}"
            )

    def setup_error_attribute_only_on_error_data_points(self):
        weblog.get("/")

    def test_error_attribute_only_on_error_data_points(self):
        payloads = list(interfaces.open_telemetry.get_otel_metrics())
        assert payloads, "No OTLP metrics payloads captured on /v1/metrics"

        for _, content in payloads:
            for rm in content.get("resourceMetrics") or []:
                for sm in rm.get("scopeMetrics") or []:
                    for metric in sm.get("metrics") or []:
                        if metric.get("name") != "dd.trace.span.duration":
                            continue
                        histogram = metric.get("histogram") or {}
                        for dp in histogram.get("dataPoints") or []:
                            attrs = {a.get("key"): a.get("value") for a in dp.get("attributes") or []}
                            if "error" in attrs:
                                error_val = attrs["error"]
                                # error attr must be true (string "true" in JSON, boolValue true in proto)
                                assert error_val in ({"stringValue": "true"}, {"boolValue": True}), (
                                    f"'error' attribute present on non-error data point: {attrs}"
                                )
