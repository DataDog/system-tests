# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Mocked backend (v2) interface: what the mocked backend container (utils/mocked_backend) receives, standing
in for the real Datadog backend.
"""

from collections.abc import Callable, Generator, Iterable
import copy
from pathlib import Path
from typing import Any

from utils._logger import logger
from utils._weblog import HttpResponse
from utils.dd_types import AgentTraceFormat, DataDogAgentSpan, DataDogAgentTrace
from utils.interfaces._core import ProxyBasedInterfaceValidator
from utils.interfaces._misc_validators import HeadersPresenceValidator


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

    def get_data(self, path_filters: Iterable[str] | str | None = None, *, with_api_key: str | None = None):
        """Same as other interfaces. with_api_key: only requests sent with this API key. Each sender (agent, library,
        serverless-init...) uses its own key, it tells where a request comes from.
        """
        for data in super().get_data(path_filters=path_filters):
            if with_api_key is None or self.get_api_key(data) == with_api_key:
                yield data

    def wait_for(
        self, wait_for_function: Callable[[dict], bool], timeout: int, *, with_api_key: str | None = None
    ) -> bool:
        """Same as other interfaces. with_api_key: only consider requests sent with this API key"""
        if with_api_key is None:
            return super().wait_for(wait_for_function, timeout)

        return super().wait_for(
            lambda data: self.get_api_key(data) == with_api_key and wait_for_function(data), timeout
        )

    @staticmethod
    def get_api_key(data: dict) -> str | None:
        """The API key a request was sent with"""
        for name, value in data["request"]["headers"]:
            if name.lower() == "dd-api-key":
                return value

        return None

    def get_traces(
        self, request: HttpResponse | None = None, *, with_api_key: str | None = None
    ) -> Generator[tuple[dict, DataDogAgentTrace]]:
        """Attempts to fetch the traces the agent submitted to the mocked backend.

        When a valid request is given, then we filter the spans to the ones sampled
        during that request's execution, and only return those.

        Yields (data, trace) tuples.
        """

        rid = request.get_rid() if request else None
        if rid:
            logger.debug(f"Will try to find backend_v2 spans related to request {rid}")

        for data in self.get_data(path_filters="/api/v0.2/traces", with_api_key=with_api_key):
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

    def get_spans(
        self, request: HttpResponse | None = None, *, with_api_key: str | None = None
    ) -> Generator[tuple[dict, DataDogAgentSpan], None, None]:
        """Attempts to fetch the spans the agent submitted to the mocked backend.

        When a valid request is given, then we filter the spans to the ones sampled
        during that request's execution, and only return those.

        Yields (data, span) tuples.
        """

        rid = request.get_rid() if request else None
        if rid:
            logger.debug(f"Will try to find backend_v2 spans related to request {rid}")

        for data, trace in self.get_traces(request=request, with_api_key=with_api_key):
            for span in trace.spans:
                if rid is None or span.get_rid() == rid:
                    yield data, span

    def get_spans_list(
        self, request: HttpResponse | None = None, *, with_api_key: str | None = None
    ) -> list[DataDogAgentSpan]:
        return [span for _, span in self.get_spans(request, with_api_key=with_api_key)]

    def get_appsec_data(
        self, request: HttpResponse, *, with_api_key: str | None = None
    ) -> Generator[tuple[dict[str, Any], DataDogAgentSpan, dict[str, Any]], Any, None]:
        for data, span in self.get_spans(request, with_api_key=with_api_key):
            json_data = span.meta.get("_dd.appsec.json")
            if json_data is not None:
                yield data, span, json_data
            elif (legacy_metastruct_data := span.get("metaStruct", {}).get("appsec")) is not None:
                yield data, span, legacy_metastruct_data
            elif (v1_metastruct_data := span.meta.get("appsec")) is not None:
                yield data, span, v1_metastruct_data

    def get_profiling_data(self, *, with_api_key: str | None = None):
        yield from self.get_data(path_filters="/api/v2/profile", with_api_key=with_api_key)

    def get_telemetry_data(self, *, flatten_message_batches: bool = True, with_api_key: str | None = None):
        all_data = self.get_data(path_filters="/api/v2/apmtelemetry", with_api_key=with_api_key)
        if flatten_message_batches:
            yield from all_data
        else:
            for data in all_data:
                if data["request"]["content"].get("request_type") == "message-batch":
                    for batch_payload in data["request"]["content"]["payload"]:
                        # create a fresh copy of the request for each payload in the
                        # message batch, as though they were all sent independently
                        copied = copy.deepcopy(data)
                        copied["request"]["content"]["request_type"] = batch_payload.get("request_type")
                        copied["request"]["content"]["payload"] = batch_payload.get("payload")
                        yield copied
                else:
                    yield data

    def assert_trace_exists(self, request: HttpResponse, *, with_api_key: str | None = None):
        for _, _ in self.get_traces(request=request, with_api_key=with_api_key):
            return

        raise ValueError(f"No trace has been found for request {request.get_rid()}")

    def assert_headers_presence(
        self,
        path_filter: Iterable[str] | str | None,
        request_headers: Iterable[str] = (),
        response_headers: Iterable[str] = (),
        check_condition: Callable | None = None,
    ):
        """Assert that a header is present on all requests"""
        validator = HeadersPresenceValidator(request_headers, response_headers, check_condition)
        self.validate_all(validator, path_filters=path_filter, allow_no_data=True)

    @staticmethod
    def get_span_metrics(span: DataDogAgentSpan) -> dict[str, str]:
        """Returns the metrics dictionary of a span according to its format"""
        if span.trace.format == AgentTraceFormat.legacy:
            return span["metrics"]

        if span.trace.format == AgentTraceFormat.efficient_trace_payload_format:
            # in the new format, metrics and meta are joined in attributes
            return span["attributes"]

        raise ValueError(f"Unknown span format: {span.trace.format}")

    def get_metrics(self, *, with_api_key: str | None = None):
        """Attempts to fetch the metrics the agent submitted to the mocked backend."""

        for data in self.get_data(
            path_filters=("/api/v2/series", "/api/intake/metrics/v3/series"), with_api_key=with_api_key
        ):
            content = data["request"]["content"]
            assert isinstance(content, dict), f"content is not a dict in {data['log_filename']}"

            if len(content) == 0:
                continue

            if "series" not in content:
                raise ValueError(f"series property is missing in agent payload in {data['log_filename']}")

            series = data["request"]["content"]["series"]

            for point in series:
                yield data, point

    def get_sketches(self, *, with_api_key: str | None = None):
        """Attempts to fetch the sketches the agent submitted to the mocked backend."""

        all_data = self.get_data(path_filters="/api/beta/sketches", with_api_key=with_api_key)

        for data in all_data:
            if "sketches" in data["request"]["content"]:
                content = data["request"]["content"]["sketches"]

                for point in content:
                    yield data, point

    def get_dsm_data(self, *, with_api_key: str | None = None):
        return self.get_data(path_filters="/api/v0.1/pipeline_stats", with_api_key=with_api_key)

    def get_stats(self, resource: str | list[str] = "", *, with_api_key: str | None = None):
        """Attempts to fetch the stats the agent submitted to the mocked backend.

        When a valid request is given, then we filter the stats to the ones sampled
        during that request's execution, and only return those.
        """
        resources = [resource] if isinstance(resource, str) else resource

        for data in self.get_data(path_filters="/api/v0.2/stats", with_api_key=with_api_key):
            client_stats_payloads = data["request"]["content"]["Stats"]

            for client_stats_payload in client_stats_payloads:
                for client_stats_buckets in client_stats_payload["Stats"]:
                    for client_grouped_stat in client_stats_buckets["Stats"]:
                        if not resources or "" in resources or client_grouped_stat["Resource"] in resources:
                            yield client_grouped_stat
