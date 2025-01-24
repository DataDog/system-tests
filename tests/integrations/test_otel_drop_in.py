# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2024 Datadog, Inc.

import json
from utils import weblog, interfaces, scenarios, features, incomplete_test_app


@features.f_otel_interoperability
@scenarios.integrations
class Test_Otel_Drop_In:
    """Verify telemetry data for OpenTelemetry drop-in support"""

    def exercise_otel_drop_in(self):
        self.r = weblog.get("/otel_drop_in")

    setup_otel_drop_in_telemetry_data = exercise_otel_drop_in

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

    setup_otel_drop_in_span_metrics = exercise_otel_drop_in

    def test_otel_drop_in_span_metrics(self):
        def has_otel_library_tag(tags):
            return any(tag.startswith("integration_name:otel.") for tag in tags)

        span_metric_found = False
        for metric in interfaces.library.get_telemetry_metric_series("tracers", "spans_created"):
            if has_otel_library_tag(metric.get("tags", [])):
                span_metric_found = True
                break
        assert span_metric_found, "Otel drop-in span metric not found"


@features.f_otel_interoperability
@scenarios.apm_tracing_e2e_otel
class Test_Otel_Drop_In_Default_Propagator:
    def setup_propagation_extract(self):
        extract_headers = {
            "traceparent": "00-11111111111111110000000000000002-000000000000000a-01",
            "tracestate": "dd=s:2;p:000000000000000a,foo=1",
            "baggage": "foo=1",
        }
        self.r = weblog.get("/otel_drop_in_default_propagator_extract", headers=extract_headers)

    @incomplete_test_app(library="ruby", reason="Ruby extract seems to fail even though it should be supported")
    def test_propagation_extract(self):
        content = json.loads(self.r.text)

        assert content["trace_id"] == 2
        assert content["span_id"] == 10
        assert content["tracestate"] and not content["tracestate"].isspace()
        # assert content["baggage"] and not content["baggage"].isspace()

    def setup_propagation_inject(self):
        inject_headers = {
            "baggage": "foo=2",
        }
        self.r = weblog.get("/otel_drop_in_default_propagator_inject")

    @incomplete_test_app(library="nodejs", reason="Node.js inject endpoint doesn't seem to be working.")
    def test_propagation_inject(self):
        content = json.loads(self.r.text)

        assert content["traceparent"] and not content["traceparent"].isspace()
        # assert content["baggage"] and not content["baggage"].isspace()
