# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Validate data flow between agent and backend"""

import threading

from utils._logger import logger
from utils.interfaces._core import ProxyBasedInterfaceValidator
from utils._weblog import HttpResponse


class OpenTelemetryInterfaceValidator(ProxyBasedInterfaceValidator):
    """Validated communication between open telemetry and datadog backend"""

    def __init__(self):
        super().__init__("open_telemetry")
        self.ready = threading.Event()

    def ingest_file(self, src_path: str):
        self.ready.set()
        return super().ingest_file(src_path)

    def get_otel_trace_id(self, request: HttpResponse):
        paths = ["/api/v0.2/traces", "/v1/traces"]
        rid = request.get_rid()

        if rid:
            logger.debug(f"Try to find traces related to request {rid}")

        for data in self.get_data(path_filters=paths):
            for resource_span in data.get("request").get("content").get("resourceSpans"):
                for scope_span in resource_span.get("scopeSpans"):
                    for span in scope_span.get("spans"):
                        for attribute in span.get("attributes", []):
                            attr_key = attribute.get("key")
                            attr_val = attribute.get("value").get("string_value") or attribute.get("value").get(
                                "stringValue"
                            )
                            if (attr_key == "http.request.headers.user-agent" and rid in attr_val) or (
                                attr_key == "http.useragent" and rid in attr_val
                            ):
                                yield span.get("traceId")

    def get_otel_spans(self, request: HttpResponse):
        paths = ["/api/v0.2/traces", "/v1/traces"]
        rid = request.get_rid()

        if rid:
            logger.debug(f"Try to find traces related to request {rid}")

        for data in self.get_data(path_filters=paths):
            resource_spans = data.get("request").get("content").get("resource_spans") or data.get("request").get(
                "content"
            ).get("resourceSpans")
            for resource_span in resource_spans:
                scope_spans = resource_span.get("scope_spans") or resource_span.get("scopeSpans")
                for scope_span in scope_spans:
                    for span in scope_span.get("spans"):
                        for attribute in span.get("attributes", []):
                            attr_key = attribute.get("key")
                            attr_val = attribute.get("value").get("string_value") or attribute.get("value").get(
                                "stringValue"
                            )
                            if (attr_key == "http.request.headers.user-agent" and rid in attr_val) or (
                                attr_key == "http.useragent" and rid in attr_val
                            ):
                                yield resource_span, span
                                break  # Skip to next span

    def get_trace_stats(self, resource: str):
        paths = ["/api/v0.2/stats", "/v1/metrics"]

        for data in self.get_data(path_filters=paths):
            resource_metrics = data.get("request").get("content").get("resource_metrics") or data.get("request").get(
                "content"
            ).get("resourceMetrics")
            if not resource_metrics:
                continue

            for resource_metric in resource_metrics:
                scope_metrics = resource_metric.get("scope_metrics") or resource_metric.get("scopeMetrics")
                for scope_metric in scope_metrics:
                    if scope_metric.get("scope").get("name") == "datadog.trace.metrics":
                        for metric in scope_metric.get("metrics"):
                            if metric.get("name") == "request.latencies":
                                data_points = metric.get("histogram").get("data_points") or metric.get("histogram").get(
                                    "dataPoints"
                                )
                                for data_point in data_points:
                                    for attribute in data_point.get("attributes", []):
                                        attr_key = attribute.get("key")
                                        attr_val = attribute.get("value").get("string_value") or attribute.get(
                                            "value"
                                        ).get("stringValue")
                                        if attr_key == "Resource" and attr_val == resource:
                                            yield metric, data_point
