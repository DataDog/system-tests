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
                            attr_val = attribute.get("value").get("stringValue")
                            if attr_key == "http.request.headers.user-agent" and rid in attr_val:
                                yield span.get("traceId")
