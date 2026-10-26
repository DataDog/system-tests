# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Mocked backend (v2) interface: what the mocked backend container (utils/mocked_backend) receives, standing
in for the real Datadog backend.
"""

from collections.abc import Callable, Generator
from pathlib import Path

from utils._logger import logger
from utils._weblog import HttpResponse
from utils.dd_types import DataDogAgentSpan, DataDogAgentTrace
from utils.interfaces._core import ProxyBasedInterfaceValidator


class _BackendV2InterfaceValidator(ProxyBasedInterfaceValidator):
    def __init__(self):
        super().__init__("backend_v2")

    def ingest_all_files(self) -> None:
        """Ingest every recorded file not seen yet by the watchdog. To call once the mocked backend is stopped.

        The watchdog polls the log folder about once per second, so the last requests (e.g. what the agent flushes
        when it stops) may be on disk but not ingested yet. Instead of waiting an arbitrary time, as other
        proxy-based interfaces do, read them now: once the mocked backend is stopped, nothing else can arrive.
        """
        for file in sorted(Path(self.log_folder).glob("*.json")):
            # same path as given by the watchdog, so files are not ingested twice
            self.ingest_file(str(file))

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
