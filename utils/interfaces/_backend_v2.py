# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Mocked backend (v2) interface: owns the lifecycle of a local HTTP server that stands in for
the real Datadog backend and records everything it receives. See
utils/mocked_backend/backend_v2.py.
"""

from collections.abc import Callable, Generator
import base64
import json

from utils._logger import logger
from utils._weblog import HttpResponse
from utils.dd_types import DataDogAgentSpan, DataDogAgentTrace
from utils.interfaces._core import ProxyBasedInterfaceValidator
from utils.mocked_backend.backend_v2 import MockBackendV2Server


class _BackendV2InterfaceValidator(ProxyBasedInterfaceValidator):
    def __init__(self):
        super().__init__("backend_v2")
        self._mock_server: MockBackendV2Server | None = None

    def start_mocked_backend(self) -> None:
        if self._mock_server is None:
            self._mock_server = MockBackendV2Server(self.log_folder, on_message=self._on_message)

    def stop_mocked_backend(self) -> None:
        if self._mock_server is not None:
            self._mock_server.close()
            self._mock_server = None

    def _on_message(self, data: dict) -> None:
        # The mock server runs in this same process, so data can be appended directly as it
        # is received instead of going through the file-watchdog round-trip used for
        # containerized interfaces.
        with self._lock:
            self._append_data(data)
            self._data_list.sort(key=lambda data: data["log_filename"])

    def get_traces(self, request: HttpResponse | None = None) -> Generator[tuple[dict, DataDogAgentTrace]]:
        """Attempts to fetch the traces the agent submitted to the mocked backend.

        When a valid request is given, then we filter the spans to the ones sampled
        during that request's execution, and only return those.

        Yields (data, trace) tuples.
        """

        rid = request.get_rid() if request else None
        if rid:
            logger.debug(f"Will try to find backend_v2 spans related to request {rid}")

        for data in self.get_data(path_filters="/api/v0.2/traces"):
            logger.debug(f"Looking at backend_v2 data {data['log_filename']}")

            if "content" not in data["request"]:
                raise ValueError(
                    f"backend_v2 request in {data['log_filename']} could not be deserialized: "
                    f"{data['request'].get('traceback', data['request'].get('raw_content'))}"
                )

            builder: Callable[[dict, dict], DataDogAgentTrace]

            if "tracerPayloads" in data["request"]["content"]:
                builder = DataDogAgentTrace.from_agent_legacy
                content: list[dict] = data["request"]["content"]["tracerPayloads"]
            elif "idxTracerPayloads" in data["request"]["content"]:
                builder = DataDogAgentTrace.from_agent_v1
                content: list[dict] = data["request"]["content"]["idxTracerPayloads"]
            else:
                raise TypeError("I don't know how to build trace from this file")

            for payload in content:
                for chunk in payload.get("chunks", []):
                    trace = builder(data, raw_trace=chunk)
                    if rid is None:
                        yield data, trace
                    else:
                        for span in trace.spans:
                            if span.get_rid() == rid:
                                logger.debug(f"Found a span in {trace.log_filename}")
                                yield data, trace
                                break

    def get_spans(self, request: HttpResponse | None = None) -> Generator[tuple[dict, DataDogAgentSpan], None, None]:
        """Attempts to fetch the spans the agent submitted to the mocked backend.

        When a valid request is given, then we filter the spans to the ones sampled
        during that request's execution, and only return those.

        Yields (data, span) tuples.
        """

        rid = request.get_rid() if request else None
        if rid:
            logger.debug(f"Will try to find backend_v2 spans related to request {rid}")

        for data, trace in self.get_traces(request=request):
            for span in trace.spans:
                if rid is None or span.get_rid() == rid:
                    yield data, span

    def get_spans_list(self, request: HttpResponse | None = None) -> list[DataDogAgentSpan]:
        return [span for _, span in self.get_spans(request)]

    def assert_otlp_trace_exist(self, dd_trace_id: int, dd_api_key: str | None = None) -> dict:
        logger.info(f"Look for otel trace {dd_trace_id}")
        for data in self.get_data("/api/v0.2/traces"):
            headers = {k.lower(): v for k, v in data["request"]["headers"]}

            if dd_api_key is not None and headers["dd-api-key"] != dd_api_key:
                logger.debug(f"API key does not match in {data['log_filename']}")
                continue

            logger.info(f"Look in {data['log_filename']}")
            if "tracerPayloads" in data["request"]["content"]:
                for payload in data["request"]["content"]["tracerPayloads"]:
                    for trace in payload.get("chunks", []):
                        observed_trace_id = trace["spans"][0]["traceID"]
                        if observed_trace_id == dd_trace_id or observed_trace_id == str(dd_trace_id):
                            return trace
            elif "resourceSpans" in data["request"]["content"]:
                for resource_span in data["request"]["content"]["resourceSpans"]:
                    for scope_span in resource_span["scopeSpans"]:
                        span = scope_span["spans"][0]
                        trace_id_base64 = span["traceId"]
                        # OTel trace IDs are 128-bit, Datadog trace IDs are the low 64 bits of that.
                        trace_id = int.from_bytes(base64.b64decode(trace_id_base64)[-8:], "big")
                        if trace_id == dd_trace_id:
                            # Unlike the tracerPayloads branch, this is raw OTLP: the real backend
                            # would convert it to the Datadog span shape, ours doesn't, so carry
                            # the resource/scope context along too, needed to do that conversion.
                            return {
                                "spans": [span],
                                "resource": resource_span.get("resource", {}),
                                "scope": scope_span.get("scope", {}),
                            }

        raise ValueError(f"Trace {dd_trace_id} not found")

    def query_timeseries(self, rid: str, metric: str, dd_api_key: str | None = None) -> dict:
        logger.info(f"Look for time serie {metric} for {rid}")

        for data in self.get_data("/api/v2/series"):
            headers = {k.lower(): v for k, v in data["request"]["headers"]}

            if dd_api_key is not None and headers["dd-api-key"] != dd_api_key:
                logger.debug(f"API key does not match in {data['log_filename']}")
                continue

            logger.info(f"Look in {data['log_filename']}")

            if headers.get("dd-protocol") == "otlp":
                for resource_metric in data["request"]["content"]["resourceMetrics"]:
                    for scope_metric in resource_metric["scopeMetrics"]:
                        for observed_metric in scope_metric["metrics"]:
                            if observed_metric["name"] == metric:
                                return observed_metric

            else:  # dd agent format
                for serie in data["request"]["content"].get("series", []):
                    if f"rid:{rid}" not in serie.get("tags", []):
                        continue

                    if serie["metric"] == metric:
                        logger.info(f"Found in {data['log_filename']}")
                        return serie

        raise ValueError(f"Serie {metric} not found")

    def get_logs(self, query: str, rid: str, dd_api_key: str | None = None) -> dict:
        logger.info(f"Look for logs {query} for {rid}")
        for data in self.get_data("/api/v2/logs"):
            headers = {k.lower(): v for k, v in data["request"]["headers"]}

            if dd_api_key is not None and headers["dd-api-key"] != dd_api_key:
                logger.debug(f"API key does not match in {data['log_filename']}")
                continue

            logger.debug(f"Look in {data['log_filename']}")

            if headers.get("dd-protocol") == "otlp":
                for item in data["request"]["content"]["resourceLogs"]:
                    for log in item["scopeLogs"]:
                        for reccord in log["logRecords"]:
                            for attribute in reccord["attributes"]:
                                if attribute["key"] == "http.request.headers.user-agent":
                                    if attribute["value"]["stringValue"] == f"system_tests rid/{rid}":
                                        return reccord

            else:  # Dd-Protocol = agent-json
                for item in data["request"]["content"]:
                    item["message"] = json.loads(item["message"])
                    if item["message"]["http.request.headers.user-agent"] == f"system_tests rid/{rid}":
                        return item

        raise ValueError("log not found")
