# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Validate data flow between agent and backend"""

from collections.abc import Callable, Generator, Iterable
import copy
import threading

from utils.dd_constants import TraceAgentPayloadFormat
from utils.tools import get_rid_from_span
from utils._logger import logger
from utils.interfaces._core import ProxyBasedInterfaceValidator
from utils.interfaces._misc_validators import HeadersPresenceValidator
from utils._weblog import HttpResponse


class AgentInterfaceValidator(ProxyBasedInterfaceValidator):
    """Validate agent/backend interface"""

    def __init__(self):
        super().__init__("agent")
        self.ready = threading.Event()

    def ingest_file(self, src_path: str):
        self.ready.set()
        return super().ingest_file(src_path)

    def get_appsec_data(self, request: HttpResponse):
        rid = request.get_rid()

        for data in self.get_data(path_filters="/api/v0.2/traces"):
            if "tracerPayloads" not in data["request"]["content"]:
                continue

            content = data["request"]["content"]["tracerPayloads"]

            for payload in content:
                for chunk in payload["chunks"]:
                    for span in chunk["spans"]:
                        appsec_data = span.get("meta", {}).get("_dd.appsec.json", None) or span.get(
                            "meta_struct", {}
                        ).get("appsec", None)
                        if appsec_data is None:
                            continue

                        if rid is None:
                            yield data, payload, chunk, span, appsec_data
                        elif get_rid_from_span(span) == rid:
                            logger.debug(f"Found span with rid={rid} in {data['log_filename']}")
                            yield data, payload, chunk, span, appsec_data

    def get_profiling_data(self):
        yield from self.get_data(path_filters="/api/v2/profile")

    def validate_appsec(self, request: HttpResponse, validator: Callable):
        for data, payload, chunk, span, appsec_data in self.get_appsec_data(request=request):
            if validator(data, payload, chunk, span, appsec_data):
                return

        raise ValueError("No data validate this test")

    def get_telemetry_data(self, *, flatten_message_batches: bool = True):
        all_data = self.get_data(path_filters="/api/v2/apmtelemetry")
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

    def assert_trace_exists(self, request: HttpResponse):
        for _, _, _ in self.get_traces(request=request):
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

    def get_traces(
        self, request: HttpResponse | None = None
    ) -> Generator[tuple[dict, dict, TraceAgentPayloadFormat], None, None]:
        """Attempts to fetch the traces the agent will submit to the backend.

        When a valid request is given, then we filter the spans to the ones sampled
        during that request's execution, and only return those.

        Returns data, trace and trace_format
        """

        rid = request.get_rid() if request else None
        if rid:
            logger.debug(f"Will try to find agent spans related to request {rid}")

        for data in self.get_data(path_filters="/api/v0.2/traces"):
            logger.debug(f"Looking at agent data {data['log_filename']}")
            if "tracerPayloads" in data["request"]["content"]:
                content = data["request"]["content"]["tracerPayloads"]

                for payload in content:
                    for trace in payload["chunks"]:
                        for span in trace["spans"]:
                            if rid is None or get_rid_from_span(span) == rid:
                                logger.info(f"Found a trace in {data['log_filename']}")
                                yield data, trace, TraceAgentPayloadFormat.legacy
                                break

            if "idxTracerPayloads" in data["request"]["content"]:
                content = data["request"]["content"]["idxTracerPayloads"]

                for payload in content:
                    for trace in payload["chunks"]:
                        for span in trace["spans"]:
                            if rid is None or get_rid_from_span(span) == rid:
                                logger.info(f"Found a trace in {data['log_filename']}")
                                yield data, trace, TraceAgentPayloadFormat.efficient_trace_payload_format
                                break

    def get_spans(
        self, request: HttpResponse | None = None
    ) -> Generator[tuple[dict, dict, TraceAgentPayloadFormat], None, None]:
        """Attempts to fetch the spans the agent will submit to the backend.

        When a valid request is given, then we filter the spans to the ones sampled
        during that request's execution, and only return those.

        Returns data, span and trace_format
        """

        rid = request.get_rid() if request else None
        if rid:
            logger.debug(f"Will try to find agent spans related to request {rid}")

        for data, trace, trace_format in self.get_traces(request=request):
            for span in trace["spans"]:
                if rid is None or get_rid_from_span(span) == rid:
                    yield data, span, trace_format

    @staticmethod
    def get_span_meta(span: dict, span_format: TraceAgentPayloadFormat) -> dict[str, str]:
        """Returns the meta dictionary of a span according to its format"""
        if span_format == TraceAgentPayloadFormat.legacy:
            return span["meta"]

        if span_format == TraceAgentPayloadFormat.efficient_trace_payload_format:
            # in the new format, metrics and meta are joined in attributes
            return span["attributes"]

        raise ValueError(f"Unknown span format: {span_format}")

    @staticmethod
    def get_span_metrics(span: dict, span_format: TraceAgentPayloadFormat) -> dict[str, str]:
        """Returns the metrics dictionary of a span according to its format"""
        if span_format == TraceAgentPayloadFormat.legacy:
            return span["metrics"]

        if span_format == TraceAgentPayloadFormat.efficient_trace_payload_format:
            # in the new format, metrics and meta are joined in attributes
            return span["attributes"]

        raise ValueError(f"Unknown span format: {span_format}")

    def get_chunks_v1(self, request: HttpResponse | None = None):  # TODO : remove this, and use get_traces instead
        """Attempts to fetch the v1 trace chunks the agent will submit to the backend.

        When a valid request is given, then we filter the chunks to the ones sampled
        during that request's execution, and only return those.
        """

        rid = request.get_rid() if request else None
        if rid:
            logger.debug(f"Will try to find agent spans related to request {rid}")

        for data in self.get_data(path_filters="/api/v0.2/traces"):
            logger.debug(f"Looking at agent data {data['log_filename']}")
            if "idxTracerPayloads" not in data["request"]["content"]:
                continue
            content = data["request"]["content"]["idxTracerPayloads"]

            for payload in content:
                logger.debug(f"Looking at agent payload {payload}")
                for chunk in payload["chunks"]:
                    for span in chunk["spans"]:
                        if rid is None or get_rid_from_span(span) == rid:
                            logger.debug(f"Found a span in {data['log_filename']}")
                            yield data, chunk
                            break

    def get_spans_list(self, request: HttpResponse) -> list[tuple[dict, TraceAgentPayloadFormat]]:
        return [(span, span_format) for _, span, span_format in self.get_spans(request)]

    def get_metrics(self):
        """Attempts to fetch the metrics the agent will submit to the backend."""

        for data in self.get_data(path_filters="/api/v2/series"):
            content = data["request"]["content"]
            assert isinstance(content, dict), f"content is not a dict in {data['log_filename']}"

            if len(content) == 0:
                continue

            if "series" not in content:
                raise ValueError(f"series property is missing in agent payload in {data['log_filename']}")

            series = data["request"]["content"]["series"]

            for point in series:
                yield data, point

    def get_sketches(self):
        """Attempts to fetch the sketches the agent will submit to the backend."""

        all_data = self.get_data(path_filters="/api/beta/sketches")

        for data in all_data:
            if "sketches" in data["request"]["content"]:
                content = data["request"]["content"]["sketches"]

                for point in content:
                    yield data, point

    def get_dsm_data(self):
        return self.get_data(path_filters="/api/v0.1/pipeline_stats")

    def get_stats(self, resource: str = ""):
        """Attempts to fetch the stats the agent will submit to the backend.

        When a valid request is given, then we filter the stats to the ones sampled
        during that request's execution, and only return those.
        """

        for data in self.get_data(path_filters="/api/v0.2/stats"):
            client_stats_payloads = data["request"]["content"]["Stats"]

            for client_stats_payload in client_stats_payloads:
                for client_stats_buckets in client_stats_payload["Stats"]:
                    for client_grouped_stat in client_stats_buckets["Stats"]:
                        if resource == "" or client_grouped_stat["Resource"] == resource:
                            yield client_grouped_stat
