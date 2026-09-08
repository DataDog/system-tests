# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Validate data flow between agent and backend"""

import threading
from typing import Any

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
        # Paths filter intercepted OTLP export requests (weblog → proxy), not weblog or backend URLs.
        paths = ["/api/v0.2/traces", "/v1/traces"]
        rid = request.get_rid()

        if rid:
            logger.debug(f"Try to find traces related to request {rid}")

        for data in self.get_data(path_filters=paths):
            content = data.get("request").get("content")
            resource_spans = content.get("resourceSpans") or []
            for resource_span in resource_spans:
                scope_spans = resource_span.get("scopeSpans") or []
                for scope_span in scope_spans:
                    for span in scope_span.get("spans", []):
                        attributes = span.get("attributes", {})
                        request_headers_user_agent_value = attributes.get("http.request.headers.user-agent", "")
                        user_agent_value = attributes.get("http.useragent", "")
                        user_agent_original_value = attributes.get("user_agent.original", "")
                        if (
                            rid in request_headers_user_agent_value
                            or rid in user_agent_value
                            or rid in user_agent_original_value
                        ):
                            yield span.get("trace_id") or span.get("traceId")

    def get_otel_spans(self, request: HttpResponse):
        paths = ["/api/v0.2/traces", "/v1/traces"]
        rid = request.get_rid()

        if rid:
            logger.debug(f"Try to find traces related to request {rid}")

        span_records: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
        correlated_indexes: set[int] = set()
        correlated_span_ids: set[str] = set()

        for data in self.get_data(path_filters=paths):
            content = data.get("request").get("content")
            logger.debug(f"[get_otel_spans] content: {content}")
            resource_spans = content.get("resourceSpans") or []
            for resource_span in resource_spans:
                scope_spans = resource_span.get("scopeSpans")
                for scope_span in scope_spans:
                    for span in scope_span.get("spans"):
                        index = len(span_records)
                        span_records.append((data.get("request"), content, span))
                        attributes = span.get("attributes", {})
                        if any(
                            rid in attributes.get(key, "")
                            for key in ("http.request.headers.user-agent", "http.useragent", "user_agent.original")
                        ):
                            correlated_indexes.add(index)
                            if span_id := span.get("spanId"):
                                correlated_span_ids.add(span_id)

        # Child spans can be exported before their parent. Resolve the complete descendant set
        # only after collecting every payload, so export order does not affect correlation.
        found_descendant = True
        while found_descendant:
            found_descendant = False
            for index, (_, _, span) in enumerate(span_records):
                if index in correlated_indexes or span.get("parentSpanId") not in correlated_span_ids:
                    continue
                correlated_indexes.add(index)
                if span_id := span.get("spanId"):
                    correlated_span_ids.add(span_id)
                found_descendant = True

        for index in sorted(correlated_indexes):
            yield span_records[index]
