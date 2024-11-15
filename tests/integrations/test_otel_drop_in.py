# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2024 Datadog, Inc.

from utils import weblog, interfaces, context, missing_feature, scenarios, features


@features.f_otel_interoperability
@missing_feature(condition=context.library != "java", reason="Endpoint is not implemented on weblog")
@scenarios.integrations
class Test_Otel_Drop_In:
    """ Verify telemetry data for OpenTelemetry drop-in support """

    def setup_otel_drop_in_telemetry_data(self):
        self.r = weblog.get("/otel_drop_in")

    def test_otel_drop_in_telemetry_data(self):
        def has_otel_integration(integrations):
            return any(item["name"].startswith("otel.") and item["enabled"] for item in integrations)

        integration_found = False
        for data in interfaces.library.get_telemetry_data():
            payload = data["request"]["content"].get("payload")
            if payload and has_otel_integration(payload.get("integrations", [])):
                integration_found = True
                break
        assert integration_found, "Otel drop-in telemetry data not found"

    def test_otel_drop_in_span_metrics(self):
        def has_otel_library_tag(tags):
            return any(tag.startswith("integration_name:otel.") for tag in tags)

        span_metric_found = False
        for metric in interfaces.library.get_telemetry_metric_series("tracers", "spans_created"):
            if has_otel_library_tag(metric.get("tags", [])):
                span_metric_found = True
                break
        assert span_metric_found, "Otel drop-in span metric not found"
