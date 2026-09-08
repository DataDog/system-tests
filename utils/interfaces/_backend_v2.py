# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Mocked backend (v2) interface: owns the lifecycle of a local HTTP server that stands in for
the real Datadog backend and records everything it receives. See
utils/mocked_backend/backend_v2.py.
"""

from collections.abc import Callable, Generator

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

        Returns data, trace and trace_format
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

        Returns data, span and trace_format
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
