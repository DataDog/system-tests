# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2024 Datadog, Inc.

import json
from utils import weblog, interfaces, scenarios, features, incomplete_test_app
from utils._logger import logger
from typing import Any, Iterator


# Assert that the histogram has only one recorded data point matching the overall duration
def assert_single_histogram_data_point(duration: int, bucket_counts: list[int], explicit_bounds: list[float]):
    for i in range(len(explicit_bounds)):
        is_first_index = i == 0
        is_last_index = i == len(explicit_bounds) - 1

        if is_first_index and is_last_index:
            assert bucket_counts[i] == 1
            assert duration <= explicit_bounds[i]
            break

        if int(bucket_counts[i]) == 1:
            lower_bound = float('-inf') if is_first_index else explicit_bounds[i-1]
            upper_bound = float('inf') if is_last_index else explicit_bounds[i]

            if is_last_index:
                assert duration > lower_bound and duration < upper_bound
            else:
                assert duration > lower_bound and duration <= upper_bound

def get_keyvalue_generator(attributes: list[dict]) -> Iterator[tuple[str, Any]]:
    for keyValue in attributes:
        if keyValue["value"].get("string_value"):
            yield keyValue["key"], keyValue["value"]["string_value"]
        elif keyValue["value"].get("stringValue"):
            yield keyValue["key"], keyValue["value"]["stringValue"]
        elif keyValue["value"].get("bool_value"):
            yield keyValue["key"], keyValue["value"]["bool_value"]
        elif keyValue["value"].get("boolValue"):
            yield keyValue["key"], keyValue["value"]["boolValue"]
        elif keyValue["value"].get("int_value"):
            yield keyValue["key"], keyValue["value"]["int_value"]
        elif keyValue["value"].get("intValue"):
            yield keyValue["key"], keyValue["value"]["intValue"]
        elif keyValue["value"].get("double_value"):
            yield keyValue["key"], keyValue["value"]["double_value"]
        elif keyValue["value"].get("doubleValue"):
            yield keyValue["key"], keyValue["value"]["doubleValue"]
        elif keyValue["value"].get("array_value"):
            yield keyValue["key"], keyValue["value"]["array_value"]
        elif keyValue["value"].get("arrayValue"):
            yield keyValue["key"], keyValue["value"]["arrayValue"]
        elif keyValue["value"].get("kvlist_value"):
            yield keyValue["key"], keyValue["value"]["kvlist_value"]
        elif keyValue["value"].get("kvlistValue"):
            yield keyValue["key"], keyValue["value"]["kvlistValue"]
        elif keyValue["value"].get("bytes_value"):
            yield keyValue["key"], keyValue["value"]["bytes_value"]
        elif keyValue["value"].get("bytesValue"):
            yield keyValue["key"], keyValue["value"]["bytesValue"]
        else:
            raise ValueError(f"Unknown attribute value: {keyValue["value"]}")


# @scenarios.apm_tracing_e2e_otel
@features.otel_api
@scenarios.apm_tracing_otlp
class Test_Otel_Tracing_OTLP:
    def setup_tracing(self):
        self.req = weblog.get("/")

    # Note: Both camelcase and snake_case are allowed by the ProtoJSON Format (https://protobuf.dev/programming-guides/json/)
    def test_tracing(self):
        data = list(interfaces.open_telemetry.get_otel_spans(self.req))
        # _logger.debug(data)
        assert len(data) == 1
        resource_span, span = data[0]

        # Assert resource attributes (we only expect string values)
        attributes = {keyValue["key"]: keyValue["value"].get("string_value") or keyValue["value"].get("stringValue") for keyValue in resource_span.get("resource").get("attributes")}
        assert attributes.get("service.name") == "weblog"
        assert attributes.get("service.version") == "1.0.0"
        assert attributes.get("deployment.environment.name") == "system-tests" or attributes.get("deployment.environment") == "system-tests"
        # assert attributes.get("telemetry.sdk.name") == "datadog"
        assert "telemetry.sdk.language" in attributes
        assert "telemetry.sdk.version" in attributes
        assert "git.commit.sha" in attributes
        assert "git.repository_url" in attributes
        assert "runtime-id" in attributes

        # Assert spans
        assert span.get("name") == "GET /"
        assert span.get("kind") == "SPAN_KIND_SERVER"
        assert span.get("start_time_unix_nano") or span.get("startTimeUnixNano")
        assert span.get("end_time_unix_nano") or span.get("endTimeUnixNano")
        assert span.get("attributes") is not None

        # Assert HTTP tags
        # Convert attributes list to a dictionary, but for now only handle KeyValue objects with stringValue
        # attributes = {keyValue["key"]: keyValue["value"]["string_value"] or keyValue["value"]["stringValue"] for keyValue in span.get("attributes")}
        span_attributes = dict(get_keyvalue_generator(span.get("attributes")))
        assert span_attributes.get("http.method") == "GET"
        assert span_attributes.get("http.status_code") == "200" # We may want to convert this to int later
        assert span_attributes.get("http.url") == "http://localhost:7777/"
