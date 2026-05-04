# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2025 Datadog, Inc.

"""System test for OTLP trace metrics export (Phase 2).

When DD_TRACE_OTEL_METRICS_ENABLED=true the tracer computes client-side span stats and
exports them as OTLP metrics to /v1/metrics.  This test validates that all four expected
metrics are present in the captured payload.
"""

from utils import features, interfaces, scenarios, weblog

EXPECTED_METRICS = frozenset(
    {
        "dd.trace.span.hits",
        "dd.trace.span.errors",
        "dd.trace.span.top_level_hits",
        "dd.trace.span.duration",
    }
)


@features.otlp_trace_metrics
@scenarios.apm_tracing_otlp_metrics
class Test_OTLP_Trace_Metrics:
    """All four dd.trace.span.* metrics must be exported to /v1/metrics."""

    def setup_all_expected_metrics(self):
        weblog.get("/")

    def test_all_expected_metrics(self):
        payloads = list(interfaces.open_telemetry.get_otel_metrics())
        assert payloads, "No OTLP metrics payloads captured on /v1/metrics"

        found: set[str] = set()
        for _, content in payloads:
            for rm in content.get("resourceMetrics") or []:
                for sm in rm.get("scopeMetrics") or []:
                    for metric in sm.get("metrics") or []:
                        name = metric.get("name")
                        if name:
                            found.add(name)

        missing = EXPECTED_METRICS - found
        assert not missing, f"Missing metrics: {sorted(missing)}. Found: {sorted(found)}"
