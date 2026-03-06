# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2024 Datadog, Inc.

import time
import re
from enum import Enum
from utils import weblog, interfaces, scenarios, features
from typing import Any
from collections.abc import Iterator


def _snake_to_camel(snake_key: str) -> str:
    parts = snake_key.split("_")
    return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])


def get_otlp_key(d: dict[str, Any] | None, snake_case_key: str, *, is_json: bool, default: Any = None) -> Any:  # noqa: ANN401
    """Look up a field by its snake_case name when is_json is false, or its camelCase equivalent when is_json is true.
    Fields must be camelCase for JSON Protobuf encoding. See https://opentelemetry.io/docs/specs/otlp/#json-protobuf-encoding
    """
    if d is None:
        return default
    key = _snake_to_camel(snake_case_key) if is_json else snake_case_key
    return d.get(key, default)


# See https://github.com/open-telemetry/opentelemetry-proto/blob/v1.9.0/opentelemetry/proto/trace/v1/trace.proto#L153
class SpanKind(Enum):
    UNSPECIFIED = 0
    INTERNAL = 1
    SERVER = 2
    CLIENT = 3
    PRODUCER = 4
    CONSUMER = 5


# See https://github.com/open-telemetry/opentelemetry-proto/blob/v1.9.0/opentelemetry/proto/trace/v1/trace.proto#L316
class StatusCode(Enum):
    STATUS_CODE_UNSET = 0
    STATUS_CODE_OK = 1
    STATUS_CODE_ERROR = 2


def get_keyvalue_generator(attributes: list[dict]) -> Iterator[tuple[str, Any]]:
    for key_value in attributes:
        if key_value["value"].get("string_value"):
            yield key_value["key"], key_value["value"]["string_value"]
        elif key_value["value"].get("stringValue"):
            yield key_value["key"], key_value["value"]["stringValue"]
        elif key_value["value"].get("bool_value"):
            yield key_value["key"], key_value["value"]["bool_value"]
        elif key_value["value"].get("boolValue"):
            yield key_value["key"], key_value["value"]["boolValue"]
        elif key_value["value"].get("int_value"):
            yield key_value["key"], key_value["value"]["int_value"]
        elif key_value["value"].get("intValue"):
            yield key_value["key"], key_value["value"]["intValue"]
        elif key_value["value"].get("double_value"):
            yield key_value["key"], key_value["value"]["double_value"]
        elif key_value["value"].get("doubleValue"):
            yield key_value["key"], key_value["value"]["doubleValue"]
        elif key_value["value"].get("array_value"):
            yield key_value["key"], key_value["value"]["array_value"]
        elif key_value["value"].get("arrayValue"):
            yield key_value["key"], key_value["value"]["arrayValue"]
        elif key_value["value"].get("kvlist_value"):
            yield key_value["key"], key_value["value"]["kvlist_value"]
        elif key_value["value"].get("kvlistValue"):
            yield key_value["key"], key_value["value"]["kvlistValue"]
        elif key_value["value"].get("bytes_value"):
            yield key_value["key"], key_value["value"]["bytes_value"]
        elif key_value["value"].get("bytesValue"):
            yield key_value["key"], key_value["value"]["bytesValue"]
        else:
            raise ValueError(f"Unknown attribute value: {key_value['value']}")


# @scenarios.apm_tracing_e2e_otel
@features.otel_api
@scenarios.apm_tracing_otlp
class Test_Otel_Tracing_OTLP:
    def setup_single_server_trace(self):
        self.start_time_ns = time.time_ns()
        self.req = weblog.get("/")
        self.end_time_ns = time.time_ns()

    def test_single_server_trace(self):
        data = list(interfaces.open_telemetry.get_otel_spans(self.req))

        # Assert that there is only one OTLP request containing the desired server span
        assert len(data) == 1
        request, content, span = data[0]

        # Determine if JSON Protobuf Encoding was used for the OTLP request (rather than Binary Protobuf)
        # We need to assert that we match the OTLP specification, which has some odd encoding rules when using JSON: https://opentelemetry.io/docs/specs/otlp/#json-protobuf-encoding
        request_headers = {key.lower(): value for key, value in request.get("headers")}
        is_json = request_headers.get("content-type") == "application/json"

        # Assert that there is only one resource span (i.e. SDK) in the OTLP request
        resource_spans = get_otlp_key(content, "resource_spans", is_json=is_json)
        expected_key = _snake_to_camel("resource_spans") if is_json else "resource_spans"
        assert resource_spans is not None, f"missing '{expected_key}' on content: {content}"
        assert len(resource_spans) == 1, f"expected 1 resource span, got {len(resource_spans)}"
        resource_span = resource_spans[0]

        attributes = {
            key_value["key"]: get_otlp_key(key_value["value"], "string_value", is_json=is_json)
            for key_value in resource_span.get("resource").get("attributes")
        }

        # Assert that the resource attributes contain the service-level attributes that were configured for weblog
        assert attributes.get("service.name") == "weblog"
        assert attributes.get("service.version") == "1.0.0"
        assert (
            attributes.get("deployment.environment.name") == "system-tests"
            or attributes.get("deployment.environment") == "system-tests"
        )

        # Assert that the resource attributes contain the tracer-level attributes we expect
        # assert attributes.get("telemetry.sdk.name") == "datadog"
        assert "telemetry.sdk.language" in attributes
        assert "telemetry.sdk.version" in attributes
        assert "runtime-id" in attributes
        # assert "git.commit.sha" in attributes
        # assert "git.repository_url" in attributes

        # Assert that the `traceId` and `spanId` JSON fields are valid case-insensitive hexadecimal strings, not base64-encoded strings as defined in the standard Protobuf JSON Mapping.
        # See https://opentelemetry.io/docs/specs/otlp/#json-protobuf-encoding
        if is_json:
            assert re.match(r"^[0-9a-fA-F]{32}$", span.get("traceId")), (
                f"traceId is not a valid case-insensitive hexadecimal string, got {span.get('traceId')}"
            )
            assert re.match(r"^[0-9a-fA-F]{16}$", span.get("spanId")), (
                f"spanId is not a valid case-insensitive hexadecimal string, got {span.get('spanId')}"
            )

        # Assert that the span fields match the expected values
        span_start_time_ns = int(get_otlp_key(span, "start_time_unix_nano", is_json=is_json))
        span_end_time_ns = int(get_otlp_key(span, "end_time_unix_nano", is_json=is_json))
        assert span_start_time_ns >= self.start_time_ns
        assert span_end_time_ns >= span_start_time_ns
        assert span_end_time_ns <= self.end_time_ns

        assert get_otlp_key(span, "name", is_json=is_json)
        assert get_otlp_key(span, "kind", is_json=is_json) == SpanKind.SERVER.value
        assert get_otlp_key(span, "attributes", is_json=is_json) is not None
        assert (
            get_otlp_key(span, "status", is_json=is_json) is None
            or get_otlp_key(span, "status", is_json=is_json).get("code") == StatusCode.STATUS_CODE_UNSET.value
        )

        # Assert HTTP tags
        # Convert attributes list to a dictionary, but for now only handle key_value objects with stringValue
        span_attributes = dict(get_keyvalue_generator(get_otlp_key(span, "attributes", is_json=is_json)))
        method = span_attributes.get("http.method") or span_attributes.get("http.request.method")
        status_code = span_attributes.get("http.status_code") or span_attributes.get("http.response.status_code")
        assert method == "GET", f"HTTP method is not GET, got {method}"
        assert status_code is not None
        assert int(status_code) == 200, f"HTTP status code is not 200, got {int(status_code)}"
        # assert span_attributes.get("http.url") == "http://localhost:7777/"
