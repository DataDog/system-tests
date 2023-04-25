# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""
This files will validate data flow between agent and backend
"""

import threading

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

from utils.tools import logger
from utils.interfaces._core import InterfaceValidator, get_rid_from_request


class OpenTelemetryInterfaceValidator(InterfaceValidator):
    """ Validated communication between open telemetry and datadog backend"""

    def __init__(self):
        super().__init__("agent")
        self.ready = threading.Event()

    def ingest_file(self, src_path):
        self.ready.set()
        return super().ingest_file(src_path)

    def get_otel_trace_id(self, request):
        paths = ["/api/v0.2/traces"]
        rid = get_rid_from_request(request)

        if rid:
            logger.debug(f"Try to find traces related to request {rid}")

        for data in self.get_data(path_filters=paths):
            export_request = ExportTraceServiceRequest()
            content = eval(data["request"]["content"])  # Raw content is a str like "b'\n\x\...'"
            assert export_request.ParseFromString(content) > 0, content
            for resource_span in export_request.resource_spans:
                for scope_span in resource_span.scope_spans:
                    for span in scope_span.spans:
                        for attribute in span.attributes:
                            if (
                                attribute.key == "http.request.headers.user-agent"
                                and rid in attribute.value.string_value
                            ):
                                yield span.trace_id
