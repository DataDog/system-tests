# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Validate data flow between agent and backend"""

import contextlib

from collections.abc import Callable, Generator, Iterable
import base64
import copy
import json
import msgpack
import threading

from utils.dd_constants import TraceAgentPayloadFormat, Capabilities
from utils.tools import get_rid_from_span
from utils._logger import logger
from utils.interfaces._core import ProxyBasedInterfaceValidator
from utils.interfaces._misc_validators import HeadersPresenceValidator
from utils.interfaces._library.appsec import _WafAttack, _ReportedHeader
from utils._weblog import HttpResponse


class AgentInterfaceValidator(ProxyBasedInterfaceValidator):
    """Validate agent/backend interface"""

    def __init__(self):
        super().__init__("agent")
        self.ready = threading.Event()

    @staticmethod
    def _normalize_span_keys(span: dict) -> dict:
        """Normalize camelCase keys to snake_case for consistency with library interface.

        Agent→backend traces use camelCase (spanID, traceID, metaStruct) while
        library→agent traces use snake_case (span_id, trace_id, meta_struct).
        We normalize to snake_case so tests don't need to know the difference.

        Also parse JSON strings in meta_struct/metaStruct fields.
        """
        normalized = span.copy()

        # Rename camelCase keys to snake_case
        if "spanID" in normalized:
            normalized["span_id"] = normalized.pop("spanID")
        if "traceID" in normalized:
            normalized["trace_id"] = normalized.pop("traceID")
        if "metaStruct" in normalized:
            meta_struct = normalized.pop("metaStruct")
            # Decode base64+msgpack encoded data in metaStruct fields
            if isinstance(meta_struct, dict):
                for key, value in meta_struct.items():
                    if isinstance(value, str):
                        try:
                            # Agent traces encode structured data as base64(msgpack(data))
                            decoded = base64.b64decode(value)
                            meta_struct[key] = msgpack.unpackb(decoded, raw=False)
                        except Exception:
                            with contextlib.suppress(json.JSONDecodeError, ValueError):
                                meta_struct[key] = json.loads(value)
            normalized["meta_struct"] = meta_struct

        # Also handle meta._dd.appsec.json if it's a string
        if "meta" in normalized and isinstance(normalized["meta"], dict):
            if "_dd.appsec.json" in normalized["meta"] and isinstance(normalized["meta"]["_dd.appsec.json"], str):
                with contextlib.suppress(json.JSONDecodeError, ValueError):
                    normalized["meta"]["_dd.appsec.json"] = json.loads(normalized["meta"]["_dd.appsec.json"])

        return normalized

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

    def get_appsec_events(self, request: HttpResponse | None = None, *, full_trace: bool = False):
        """Get appsec events from agent-to-backend traces.

        Yields (data, chunk, span, appsec_data) tuples where chunk acts as "trace" for compatibility.

        If request is provided:
        - If full_trace is False, only yields spans matching the request ID
        - If full_trace is True, yields all spans from traces containing the request ID
        """
        rid = request.get_rid() if request else None
        if rid:
            logger.debug(f"Try to find appsec events related to request {rid}")

        for data in self.get_data(path_filters="/api/v0.2/traces"):
            # Handle tracerPayloads format
            if "tracerPayloads" in data["request"]["content"]:
                content = data["request"]["content"]["tracerPayloads"]

                for payload in content:
                    for chunk in payload["chunks"]:
                        # Check if this chunk/trace contains the request ID (for full_trace mode)
                        chunk_has_rid = False
                        if rid and full_trace:
                            chunk_has_rid = any(get_rid_from_span(s) == rid for s in chunk["spans"])

                        for span in chunk["spans"]:
                            # Normalize span first (handles JSON parsing)
                            normalized_span = self._normalize_span_keys(span)

                            appsec_data = normalized_span.get("meta", {}).get("_dd.appsec.json") or normalized_span.get(
                                "meta_struct", {}
                            ).get("appsec")
                            if appsec_data is None:
                                continue

                            # Apply filtering based on request and full_trace
                            if rid is None or (full_trace and chunk_has_rid):
                                yield data, chunk, normalized_span, appsec_data
                            elif not full_trace and get_rid_from_span(span) == rid:
                                logger.debug(f"Found appsec event in {data['log_filename']}")
                                yield data, chunk, normalized_span, appsec_data

            # Handle idxTracerPayloads format (efficient trace payload format)
            if "idxTracerPayloads" in data["request"]["content"]:
                content = data["request"]["content"]["idxTracerPayloads"]

                for payload in content:
                    for chunk in payload.get("chunks", []):
                        # Check if this chunk/trace contains the request ID (for full_trace mode)
                        chunk_has_rid = False
                        if rid and full_trace:
                            chunk_has_rid = any(get_rid_from_span(s) == rid for s in chunk.get("spans", []))

                        for span in chunk.get("spans", []):
                            # Normalize span first (handles JSON parsing)
                            normalized_span = self._normalize_span_keys(span)

                            appsec_data = normalized_span.get("meta", {}).get("_dd.appsec.json") or normalized_span.get(
                                "meta_struct", {}
                            ).get("appsec")
                            if appsec_data is None:
                                continue

                            # Apply filtering based on request and full_trace
                            if rid is None or (full_trace and chunk_has_rid):
                                yield data, chunk, normalized_span, appsec_data
                            elif not full_trace and get_rid_from_span(span) == rid:
                                logger.debug(f"Found appsec event in {data['log_filename']}")
                                yield data, chunk, normalized_span, appsec_data

    def validate_one_appsec(
        self,
        request: HttpResponse | None = None,
        validator: Callable[[dict, dict], bool] | None = None,
        *,
        full_trace: bool = False,
    ):
        """Will call validator() on all appsec events. validator() returns a boolean:
        * True : the payload satisfies the condition, validate_one returns in success
        * False : the payload is ignored
        * If validator() raises an exception, the validate_one will fail

        If no payload satisfies validator(), then validate_one will fail

        Note: This validates agent-to-backend data flow. Legacy appsec events are not supported.
        """
        if validator:
            for _, _, span, appsec_data in self.get_appsec_events(request=request, full_trace=full_trace):
                if validator(span, appsec_data) is True:
                    return

        raise ValueError("No appsec event validate this condition")

    def validate_all_appsec(
        self,
        validator: Callable[[dict, dict], None],
        request: HttpResponse | None = None,
        *,
        allow_no_data: bool = False,
        full_trace: bool = False,
    ):
        """Will call validator() on all appsec events.
        If ever a validator raises an exception, the validation will fail.
        """
        data_is_missing = True
        for _, _, span, appsec_data in self.get_appsec_events(request=request, full_trace=full_trace):
            data_is_missing = False
            validator(span, appsec_data)

        if not allow_no_data and data_is_missing:
            raise ValueError("No appsec event has been found")

    def assert_no_appsec_event(self, request: HttpResponse):
        """Assert that no appsec event was reported for this request."""
        for data, _, _, appsec_data in self.get_appsec_events(request=request):
            logger.error(json.dumps(appsec_data, indent=2))
            raise ValueError(f"An appsec event has been reported in {data['log_filename']}")

    def assert_waf_attack(
        self,
        request: HttpResponse | None,
        rule: str | type | None = None,
        pattern: str | None = None,
        value: str | None = None,
        address: str | None = None,
        patterns: list[str] | None = None,
        key_path: str | list[str] | None = None,
        *,
        full_trace: bool = False,
        span_validator: Callable | None = None,
    ):
        """Asserts the WAF detected an attack on the provided request.

        If full_trace is True, all events found on the trace(s) created by the request will be looked into,
        otherwise only those with an identified User-Agent matching that of the request will be considered.
        It is advised to set full_trace to True when the events aren't expected to originate from the HTTP
        layer (e.g: GraphQL tests).
        """
        validator = _WafAttack(
            rule=rule,
            pattern=pattern,
            value=value,
            address=address,
            patterns=patterns,
            key_path=key_path,
            span_validator=span_validator,
        )

        self.validate_one_appsec(request, validator=validator.validate, full_trace=full_trace)

    def add_appsec_reported_header(self, request: HttpResponse, header_name: str):
        """Validate that a specific header was reported in appsec events."""
        validator = _ReportedHeader(header_name)
        self.validate_one_appsec(request, validator=validator.validate)

    def assert_rasp_attack(self, request: HttpResponse, rule: str, parameters: dict | None = None):
        """Assert that a RASP attack was detected with the specified rule and parameters."""

        def validator(_: dict, appsec_data: dict):
            assert "triggers" in appsec_data, "'triggers' not found in '_dd.appsec.json'"

            triggers = appsec_data["triggers"]
            assert len(triggers) == 1, "multiple appsec events found, only one expected"

            trigger = triggers[0]
            obtained_rule_id = trigger["rule"]["id"]
            assert obtained_rule_id == rule, f"incorrect rule id, expected {rule}, got {obtained_rule_id}"

            if parameters is not None:
                rule_matches = trigger["rule_matches"]
                assert len(rule_matches) == 1, "multiple rule matches found, only one expected"

                rule_match_params = rule_matches[0]["parameters"]
                assert len(rule_match_params) == 1, "multiple parameters found, only one expected"

                obtained_parameters = rule_match_params[0]
                for name, fields in parameters.items():
                    address = fields["address"]
                    value = None
                    if "value" in fields:
                        value = fields["value"]

                    key_path = None
                    if "key_path" in fields:
                        key_path = fields["key_path"]

                    assert name in obtained_parameters, f"parameter '{name}' not in rule match"

                    obtained_param = obtained_parameters[name]

                    assert obtained_param["address"] == address, (
                        f"incorrect address for '{name}', expected '{address}, found '{obtained_param['address']}'"
                    )

                    if value is not None:
                        assert obtained_param["value"] == value, (
                            f"incorrect value for '{name}', expected '{value}', found '{obtained_param['value']}'"
                        )

                    if key_path is not None:
                        assert obtained_param["key_path"] == key_path, (
                            f"incorrect key_path for '{name}', expected '{key_path}'"
                        )

            return True

        self.validate_one_appsec(request, validator)

    def get_profiling_data(self):
        yield from self.get_data(path_filters="/api/v2/profile")

    def validate_appsec(self, request: HttpResponse, validator: Callable):
        for data, payload, chunk, span, appsec_data in self.get_appsec_data(request=request):
            if validator(data, payload, chunk, span, appsec_data):
                return

        raise ValueError("No data validate this test")

    def get_telemetry_data(self, *, flatten_message_batches: bool = True):
        all_data = self.get_data(path_filters="/api/v2/apmtelemetry")
        if not flatten_message_batches:
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

    def get_traces(self, request: HttpResponse | None = None) -> Generator[tuple[dict, dict, TraceAgentPayloadFormat]]:
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
                content: list[dict] = data["request"]["content"]["idxTracerPayloads"]

                for payload in content:
                    for trace in payload.get("chunks", []):
                        for span in trace["spans"]:
                            if rid is None or get_rid_from_span(span) == rid:
                                logger.info(f"Found a trace in {data['log_filename']}")
                                yield data, trace, TraceAgentPayloadFormat.efficient_trace_payload_format
                                break

    def get_spans(
        self, request: HttpResponse | None = None
    ) -> Generator[tuple[dict, dict, TraceAgentPayloadFormat, list[dict]], None, None]:
        """Attempts to fetch the spans the agent will submit to the backend.

        When a valid request is given, then we filter the spans to the ones sampled
        during that request's execution, and only return those.

        Returns data, span, trace_format, and trace
        """

        rid = request.get_rid() if request else None
        if rid:
            logger.debug(f"Will try to find agent spans related to request {rid}")

        for data, trace, trace_format in self.get_traces(request=request):
            for span in trace["spans"]:
                if rid is None or get_rid_from_span(span) == rid:
                    normalized_span = self._normalize_span_keys(span)
                    yield data, normalized_span, trace_format, trace["spans"]

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
    def set_span_attrs(span: dict, span_format: TraceAgentPayloadFormat, meta: dict[str, str]) -> None:
        """Overwrites the span attributes of a span according to its format.
        For legacy spans this means only the meta dictionary,
        for efficient spans this means the entire attributes dictionary.
        """
        if span_format == TraceAgentPayloadFormat.legacy:
            span["meta"] = meta

        elif span_format == TraceAgentPayloadFormat.efficient_trace_payload_format:
            span["attributes"] = meta
        else:
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

    def get_chunks_v1(self, request: HttpResponse | None = None):
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
                for chunk in payload.get("chunks", []):
                    for span in chunk["spans"]:
                        if rid is None or get_rid_from_span(span) == rid:
                            logger.debug(f"Found a span in {data['log_filename']}")
                            yield data, chunk
                            break

    def get_spans_list(self, request: HttpResponse | None = None) -> list[tuple[dict, TraceAgentPayloadFormat]]:
        return [(span, span_format) for _, span, span_format, _ in self.get_spans(request)]

    def _get_spans_with_full_trace(
        self, request: HttpResponse | None = None, *, full_trace: bool = False
    ) -> Generator[tuple[dict, dict], None, None]:
        """Internal helper to get spans with full_trace support.

        Yields (data, span) tuples.
        """
        if not full_trace:
            # Simple case: just get spans matching the request
            for data, span, _, _ in self.get_spans(request=request):
                yield data, span
        else:
            # Full trace: get all spans from traces containing the request
            for data, trace, _ in self.get_traces(request=request):
                for span in trace["spans"]:
                    yield data, span

    def get_root_spans(self, request: HttpResponse | None = None):
        """Get all root spans (spans with parent_id == 0 or None).

        Yields (data, span) tuples for root spans.
        """
        for data, span, _, _ in self.get_spans(request=request):
            if span.get("parent_id") in (0, None):
                yield data, span

    def get_root_span(self, request: HttpResponse) -> dict:
        """Get the root span associated with a given request.

        This function will fail if a request is not given, if there is no root span,
        or if there is more than one root span. For special cases, use get_root_spans.
        """
        assert request is not None, "A request object is mandatory"
        spans = [s for _, s in self.get_root_spans(request=request)]
        assert spans, "No root spans found"
        assert len(spans) == 1, "More than one root span found"
        return spans[0]

    def validate_one_span(
        self,
        request: HttpResponse | None = None,
        *,
        validator: Callable[[dict], bool],
        full_trace: bool = False,
    ):
        """Will call validator() on all spans (eventually filtered on spans triggered by request).

        validator() returns a boolean:
        * True : the payload satisfies the condition, validate_one returns in success
        * False : the payload is ignored
        * If validator() raises an exception, the validate_one will fail

        If no payload satisfies validator(), then validate_one will fail
        """
        for _, span in self._get_spans_with_full_trace(request=request, full_trace=full_trace):
            try:
                if validator(span) is True:
                    return
            except Exception as e:
                logger.error(f"This span is failing validation ({e}): {span}")
                raise

        raise ValueError("No span validates this test")

    def validate_all_spans(
        self,
        validator: Callable[[dict], None],
        request: HttpResponse | None = None,
        *,
        full_trace: bool = False,
        allow_no_data: bool = False,
    ):
        """Will call validator() on all spans (eventually filtered on spans triggered by request).
        If ever a validator raises an exception, the validation will fail.
        """
        data_is_missing = True
        for _, span in self._get_spans_with_full_trace(request=request, full_trace=full_trace):
            data_is_missing = False
            try:
                validator(span)
            except Exception as e:
                logger.error(f"This span is failing validation ({e}): {span}")
                raise

        if not allow_no_data and data_is_missing:
            raise ValueError("No span has been observed")

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

    @staticmethod
    def get_trace_id(chunk: dict, chunk_format: TraceAgentPayloadFormat) -> str:
        """Returns the trace ID of a chunk according to its format
        Returns only the lower 64 bits of the trace ID
        """
        if chunk_format == TraceAgentPayloadFormat.efficient_trace_payload_format:
            return str(int(chunk["traceID"], 16) & 0xFFFFFFFFFFFFFFFF)
        if chunk_format == TraceAgentPayloadFormat.legacy:
            return chunk["spans"][0]["traceID"]
        raise ValueError(f"Unknown chunk format: {chunk_format}")

    @staticmethod
    def get_span_type(span: dict, span_format: TraceAgentPayloadFormat) -> str:
        if span_format == TraceAgentPayloadFormat.efficient_trace_payload_format:
            return span.get("typeRef", "")
        if span_format == TraceAgentPayloadFormat.legacy:
            return span.get("type", "")
        raise ValueError(f"Unknown span format: {span_format}")

    @staticmethod
    def get_span_name(span: dict, span_format: TraceAgentPayloadFormat) -> str:
        if span_format == TraceAgentPayloadFormat.efficient_trace_payload_format:
            return span["nameRef"]
        if span_format == TraceAgentPayloadFormat.legacy:
            return span["name"]
        raise ValueError(f"Unknown span format: {span_format}")

    @staticmethod
    def get_span_resource(span: dict, span_format: TraceAgentPayloadFormat) -> str:
        if span_format == TraceAgentPayloadFormat.efficient_trace_payload_format:
            return span["resourceRef"]
        if span_format == TraceAgentPayloadFormat.legacy:
            return span["resource"]
        raise ValueError(f"Unknown span format: {span_format}")

    @staticmethod
    def get_span_service(span: dict, span_format: TraceAgentPayloadFormat) -> str:
        if span_format == TraceAgentPayloadFormat.efficient_trace_payload_format:
            return span["serviceRef"]
        if span_format == TraceAgentPayloadFormat.legacy:
            return span["service"]
        raise ValueError(f"Unknown span format: {span_format}")

    @staticmethod
    def get_span_kind(span: dict, span_format: TraceAgentPayloadFormat) -> str:
        if span_format == TraceAgentPayloadFormat.efficient_trace_payload_format:
            return span["kind"]
        if span_format == TraceAgentPayloadFormat.legacy:
            return span["meta"]["span.kind"]
        raise ValueError(f"Unknown span format: {span_format}")

    def assert_rc_capability(self, capability: Capabilities):
        """Check that the library reports a specific Remote Config capability.

        Note: This validates library->agent communication (/v0.7/config endpoint).
        Since /v0.7/config is library->agent communication, we read from the library interface.
        """

        found = False
        for data in self.get_data(path_filters="/v0.7/config"):
            capabilities = data["request"]["content"]["client"]["capabilities"]
            if isinstance(capabilities, list):
                decoded_capabilities = bytes(capabilities)
            # base64-encoded string:
            else:
                decoded_capabilities = base64.b64decode(capabilities)
            int_capabilities = int.from_bytes(decoded_capabilities, byteorder="big")
            if (int_capabilities >> capability & 1) == 1:
                found = True
        assert found, f"Capability {capability.name} not found"

    def assert_rc_targets_version_states(self, targets_version: int, config_states: list) -> None:
        """Check that for a given targets_version, the config states is the one expected.

        Note: This validates library->agent communication (/v0.7/config endpoint).
        EXPERIMENTAL (is it the good testing API ?)
        """
        # Local import to avoid circular dependency since this file is imported by __init__.py
        found = False
        # Read from library interface since /v0.7/config is library->agent communication
        for data in self.get_data(path_filters="/v0.7/config"):
            state = data["request"]["content"]["client"]["state"]

            if state["targets_version"] != targets_version:
                continue

            logger.debug(f"In {data['log_filename']}: found targets_version {targets_version}")

            assert not state.get("has_error", False), f"State error found: {state.get('error')}"

            observed_config_states = state.get("config_states", [])
            logger.debug(f"Observed: {observed_config_states}")
            logger.debug(f"expected: {config_states}")

            # apply_error is optional, and can be none or empty string.
            # remove it in that situation to simplify the comparison
            observed_config_states = copy.deepcopy(observed_config_states)  # copy to not mess up future checks
            for observed_config_state in observed_config_states:
                if "apply_error" in observed_config_state and observed_config_state["apply_error"] in (None, ""):
                    del observed_config_state["apply_error"]

            assert config_states == observed_config_states
            found = True

        assert found, f"Nothing has been found for targets_version {targets_version}"

    def get_telemetry_metric_series(self, namespace: str, metric: str):
        """Extract and return telemetry metric series matching the given namespace and metric."""
        relevant_series = []
        for data in self.get_telemetry_data():
            content = data["request"]["content"]
            if content.get("request_type") != "generate-metrics":
                continue
            fallback_namespace = content["payload"].get("namespace")

            for series in content["payload"]["series"]:
                computed_namespace = series.get("namespace", fallback_namespace)

                # Inject here the computed namespace considering the fallback. This simplifies later assertions.
                series["_computed_namespace"] = computed_namespace
                if computed_namespace == namespace and series["metric"] == metric:
                    relevant_series.append(series)
        return relevant_series

    def assert_iast_implemented(self):
        """Check that IAST is implemented by validating presence of _dd.iast.enabled tag."""
        for _, span in self.get_root_spans():
            if "_dd.iast.enabled" in span.get("metrics", {}):
                return

            if "_dd.iast.enabled" in span.get("meta", {}):
                return

        raise ValueError("_dd.iast.enabled has not been found in any metrics")
