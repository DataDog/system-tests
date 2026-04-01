# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2024 Datadog, Inc.

import re

from utils import context, features, interfaces, scenarios, weblog
from utils._context._scenarios.endtoend import EndToEndScenario
from utils.dd_constants import SpanKind, StatusCode


# @scenarios.apm_tracing_e2e_otel
@features.otel_api
@scenarios.apm_tracing_otlp
class Test_Otel_Tracing_OTLP:
    def setup_single_server_trace(self):
        # Get the start time of the weblog container in nanoseconds
        assert isinstance(context.scenario, EndToEndScenario)
        exit_code, output = context.scenario.weblog_container.execute_command("date -u +%s%N")
        assert exit_code == 0, f"self.start_time_ns: date -u +%s%N in weblog container failed: {output!r}"
        stripped = output.strip()
        assert stripped, f"empty output from date -u +%s%N in weblog container: {output!r}"

        self.start_time_ns = int(stripped)
        self.req = weblog.get("/")

    def test_single_server_trace(self):
        """Validates the required elements of the OTLP payload for a single trace"""
        data = list(interfaces.open_telemetry.get_otel_spans(self.req))

        # Assert that there is only one OTLP request containing the desired server span
        assert len(data) == 1
        request, content, span = data[0]

        # Determine if JSON Protobuf Encoding was used for the OTLP request (rather than Binary Protobuf)
        # We need to assert that we match the OTLP specification, which has some odd encoding rules when using JSON: https://opentelemetry.io/docs/specs/otlp/#json-protobuf-encoding
        request_headers = {key.lower(): value for key, value in request.get("headers")}
        is_json = request_headers.get("content-type") == "application/json"

        # Assert that there is only one resource span (i.e. SDK) in the OTLP request
        resource_spans = content["resourceSpans"]
        assert resource_spans is not None, f"missing 'resourceSpans' on content: {content}"
        assert len(resource_spans) == 1, f"expected 1 resource span, got {len(resource_spans)}"
        resource_span = resource_spans[0]

        attributes = resource_span.get("resource", {}).get("attributes", {})

        # Assert that the resource attributes contain the service-level attributes and tracer-level attributes we expect
        # TODO: Assert the following attributes: runtime-id, git.commit.sha, git.repository_url
        assert attributes.get("service.name") == "weblog"
        assert attributes.get("service.version") == "1.0.0"
        assert (
            attributes.get("deployment.environment.name") == "system-tests"
            or attributes.get("deployment.environment") == "system-tests"
        )
        assert attributes.get("telemetry.sdk.name") == "datadog"
        assert "telemetry.sdk.language" in attributes
        # assert "telemetry.sdk.version" in attributes

        # Assert that the `traceId` and `spanId` JSON fields are valid case-insensitive hexadecimal strings, not base64-encoded strings as defined in the standard Protobuf JSON Mapping.
        # See https://opentelemetry.io/docs/specs/otlp/#json-protobuf-encoding
        # TODO: Assert against trace_id and span_id fields in the protobuf encoding as well
        if is_json:
            assert re.match(r"^[0-9a-fA-F]{32}$", span.get("traceId")), (
                f"traceId is not a valid case-insensitive hexadecimal string, got {span.get('traceId')}"
            )
            assert re.match(r"^[0-9a-fA-F]{16}$", span.get("spanId")), (
                f"spanId is not a valid case-insensitive hexadecimal string, got {span.get('spanId')}"
            )

        # Assert that the span fields match the expected values
        span_start_time_ns = int(span["startTimeUnixNano"])
        span_end_time_ns = int(span["endTimeUnixNano"])
        assert span_start_time_ns >= self.start_time_ns
        assert span_end_time_ns >= span_start_time_ns

        assert span["name"]
        assert span["kind"] == SpanKind.SERVER.value
        status = span.get("status", {})
        # An absent or empty status dict both mean STATUS_CODE_UNSET (protobuf default = 0).
        assert (
            not status or status.get("code", StatusCode.STATUS_CODE_UNSET.value) == StatusCode.STATUS_CODE_UNSET.value
        )

        # Assert core span attributes
        assert span["attributes"] is not None
        span_attributes = span["attributes"]
        assert span_attributes.get("service.name") == "weblog" or span_attributes.get("service.name") is None
        assert span_attributes["resource.name"] == span["name"]
        assert span_attributes["span.type"] == "web"
        assert span_attributes["operation.name"] is not None

        # Assert HTTP tags
        # Convert attributes list to a dictionary, but for now only handle key_value objects with stringValue
        method = span_attributes.get("http.method") or span_attributes.get("http.request.method")
        status_code = span_attributes.get("http.status_code") or span_attributes.get("http.response.status_code")
        assert method == "GET", f"HTTP method is not GET, got {method}"
        assert status_code is not None
        assert int(status_code) == 200, f"HTTP status code is not 200, got {int(status_code)}"

    def setup_unsampled_trace(self):
        self.req = weblog.get("/", headers={"traceparent": "00-11111111111111110000000000000001-0000000000000001-00"})

    def test_unsampled_trace(self):
        """Validates that the spans from a non-sampled trace are not exported."""
        data = list(interfaces.open_telemetry.get_otel_spans(self.req))

        # Assert that the span from this test case was not exported
        assert len(data) == 0, f"Expected no weblog spans in the OTLP trace payload, got {data}"
