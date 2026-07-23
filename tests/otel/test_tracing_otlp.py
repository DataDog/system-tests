# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2024 Datadog, Inc.

import base64
import binascii
import re

from utils import context, features, interfaces, scenarios, weblog
from utils._context._scenarios.endtoend import EndToEndScenario
from utils.dd_constants import SpanKind, StatusCode
from utils.docker_fixtures.spec.tracecontext import Tracestate


def _trace_id_to_hex(tid: str | None) -> str:
    """Normalize an OTLP traceId field to a 32-char lowercase hex string.

    JSON Protobuf encoding emits the field as a hex string. Binary Protobuf encoding emits
    16 raw bytes, which the proxy renders as a standard-base64 string. Returns "" if the
    input is empty or doesn't decode to a 16-byte ID.
    """
    if not tid:
        return ""
    if re.fullmatch(r"[0-9a-fA-F]{32}", tid):
        return tid.lower()
    try:
        decoded = base64.b64decode(tid, validate=True)
    except (ValueError, binascii.Error):
        return ""
    if len(decoded) != 16:
        return ""
    return decoded.hex()


# @scenarios.apm_tracing_e2e_otel
@features.otel_api
@scenarios.apm_tracing_otlp
class Test_Otel_Tracing_OTLP:
    def setup_single_server_trace(self):
        # Get the start time of the weblog container in nanoseconds
        assert isinstance(context.scenario, EndToEndScenario)
        exit_code, output = context.scenario.weblog_container.execute_command("date -u +%s%N")
        assert exit_code == 0, f"self.start_time_ns: date -u +%s%N in weblog container failed: {output!r}"
        stripped = output.strip()
        assert stripped, f"empty output from date -u +%s%N in weblog container: {output!r}"

        self.start_time_ns = int(stripped)
        self.req = weblog.get("/")

    def test_single_server_trace(self):
        """Validates the required elements of the OTLP payload for a single trace"""
        data = list(interfaces.open_telemetry.get_otel_spans(self.req))

        # Assert that there is only one OTLP request containing the desired server span
        assert len(data) == 1
        request, content, span = data[0]

        # Determine if JSON Protobuf Encoding was used for the OTLP request (rather than Binary Protobuf)
        # We need to assert that we match the OTLP specification, which has some odd encoding rules when using JSON: https://opentelemetry.io/docs/specs/otlp/#json-protobuf-encoding
        request_headers = {key.lower(): value for key, value in request.get("headers")}
        is_json = request_headers.get("content-type") == "application/json"

        # Assert that there is only one resource span (i.e. SDK) in the OTLP request
        resource_spans = content["resourceSpans"]
        assert resource_spans is not None, f"missing 'resourceSpans' on content: {content}"
        assert len(resource_spans) == 1, f"expected 1 resource span, got {len(resource_spans)}"
        resource_span = resource_spans[0]

        attributes = resource_span.get("resource", {}).get("attributes", {})

        # Assert that the resource attributes contain the service-level attributes and tracer-level attributes we expect
        # TODO: Assert the following attributes: runtime-id, git.commit.sha, git.repository_url
        assert attributes.get("service.name") == "weblog"
        assert attributes.get("service.version") == "1.0.0"
        assert (
            attributes.get("deployment.environment.name") == "system-tests"
            or attributes.get("deployment.environment") == "system-tests"
        )
        assert attributes.get("telemetry.sdk.name") == "datadog"
        assert "telemetry.sdk.language" in attributes
        # assert "telemetry.sdk.version" in attributes

        # Assert that the `traceId` and `spanId` JSON fields are valid case-insensitive hexadecimal strings, not base64-encoded strings as defined in the standard Protobuf JSON Mapping.
        # See https://opentelemetry.io/docs/specs/otlp/#json-protobuf-encoding
        # TODO: Assert against trace_id and span_id fields in the protobuf encoding as well
        if is_json:
            assert re.match(r"^[0-9a-fA-F]{32}$", span.get("traceId")), (
                f"traceId is not a valid case-insensitive hexadecimal string, got {span.get('traceId')}"
            )
            assert re.match(r"^[0-9a-fA-F]{16}$", span.get("spanId")), (
                f"spanId is not a valid case-insensitive hexadecimal string, got {span.get('spanId')}"
            )

        # Assert that the span fields match the expected values
        span_start_time_ns = int(span["startTimeUnixNano"])
        span_end_time_ns = int(span["endTimeUnixNano"])
        assert span_start_time_ns >= self.start_time_ns
        assert span_end_time_ns >= span_start_time_ns

        assert span["name"]
        assert span["kind"] == SpanKind.SERVER.value
        status = span.get("status", {})
        # An absent or empty status dict both mean STATUS_CODE_UNSET (protobuf default = 0).
        assert (
            not status or status.get("code", StatusCode.STATUS_CODE_UNSET.value) == StatusCode.STATUS_CODE_UNSET.value
        )

        # Assert core span attributes
        assert span["attributes"] is not None
        span_attributes = span["attributes"]
        assert span_attributes.get("service.name") == "weblog" or span_attributes.get("service.name") is None
        assert span_attributes["resource.name"] == span["name"]
        assert span_attributes["span.type"] == "web"
        assert span_attributes["operation.name"] is not None

        # Assert HTTP tags
        # Convert attributes list to a dictionary, but for now only handle key_value objects with stringValue
        method = span_attributes.get("http.method") or span_attributes.get("http.request.method")
        status_code = span_attributes.get("http.status_code") or span_attributes.get("http.response.status_code")
        assert method == "GET", f"HTTP method is not GET, got {method}"
        assert status_code is not None
        assert int(status_code) == 200, f"HTTP status code is not 200, got {int(status_code)}"

    def setup_unsampled_trace(self):
        self.req = weblog.get("/", headers={"traceparent": "00-11111111111111110000000000000001-0000000000000001-00"})

    def test_unsampled_trace(self):
        """Validates that the spans from a non-sampled trace are not exported."""
        data = list(interfaces.open_telemetry.get_otel_spans(self.req))

        # Assert that the span from this test case was not exported
        assert len(data) == 0, f"Expected no weblog spans in the OTLP trace payload, got {data}"

    def setup_128bit_trace_id_consistent_across_spans(self):
        self.req = weblog.get("/make_distant_call", params={"url": "http://weblog:7777/"})

    def test_128bit_trace_id_consistent_across_spans(self):
        """Validates that every span in a trace carries the same full 128-bit OTLP traceId.

        DD tracers emit 128-bit trace IDs by default but the v04/v05 msgpack wire format only
        carries the lower 64 bits per span; the upper 64 bits live in the `_dd.p.tid` meta tag,
        which RFC #85 sets on the chunk root only. The OTLP exporter must apply that value to
        every span in the chunk, otherwise child spans are exported with the upper 64 bits zeroed,
        resulting in two distinct trace IDs in the OTLP backend. The /make_distant_call endpoint
        produces a multi-span trace (server + client + nested server) so we can verify this
        propagation.
        """
        data = list(interfaces.open_telemetry.get_otel_spans(self.req))

        # `get_otel_spans` yields the server span, identified by the user-agent header
        assert len(data) >= 1, f"Expected at least one matching OTLP span, got {data}"
        _, content, server_span = data[0]

        root_span_tid = server_span.get("traceId")
        root_span_hex_id = _trace_id_to_hex(root_span_tid)
        assert root_span_hex_id, (
            f"server span has unrecognized traceId encoding (expected hex or base64-bytes): {root_span_tid!r}"
        )

        # The upper 64 bits must be non-zero — if they're zero the tracer is either emitting
        # 64-bit-only IDs (misconfiguration for this scenario) or, more importantly, the OTLP
        # exporter dropped the high bits on the root span itself.
        upper_hex = root_span_hex_id[:16]
        assert upper_hex != "0" * 16, (
            f"server traceId upper 64 bits are zero (expected a 128-bit ID): {root_span_tid!r}"
        )

        # Group every span in the OTLP payload by the lower 64 bits of its traceId.
        # If spans have a matching lower 64 bits, we expect them to have a matching full 128-bit traceId
        anchor_lower_hex = root_span_hex_id[16:]
        single_trace_spans = []
        for resource_span in content.get("resourceSpans", []):
            for scope_span in resource_span.get("scopeSpans", []):
                for s in scope_span.get("spans", []):
                    hex_tid = _trace_id_to_hex(s.get("traceId"))
                    if hex_tid and hex_tid[16:] == anchor_lower_hex:
                        single_trace_spans.append((s, hex_tid))

        # The /make_distant_call trace produces a server entry span plus at least one child span.
        # (the outbound HTTP client span).
        assert len(single_trace_spans) >= 2, (
            f"Expected at least two spans in the same trace for the OTLP payload, found "
            f"{len(single_trace_spans)}. The /make_distant_call endpoint must produce a multi-span trace "
            f"for this test to exercise _dd.p.tid propagation."
        )

        mismatched = [(s.get("spanId"), hex_tid) for s, hex_tid in single_trace_spans if hex_tid != root_span_hex_id]
        assert not mismatched, (
            f"Found {len(mismatched)} span(s) in the same logical trace with a different "
            f"128-bit traceId than the server span (server traceId={root_span_hex_id}). "
            f"Mismatched (span_id, trace_id_hex): {mismatched}. This indicates the OTLP "
            f"exporter is not propagating _dd.p.tid (high 64 bits) from the chunk root to "
            f"the remaining chunk spans."
        )


def _parse_ot_from_trace_state(trace_state: str) -> dict[str, str]:
    """Split an OTLP span's traceState ot= list-member into its rv/th sub-keys."""
    tracestate = Tracestate(trace_state) if trace_state else Tracestate()
    if "ot" not in tracestate:
        return {}

    parsed = {}
    for item in tracestate["ot"].split(";"):
        if ":" not in item:
            continue
        key, _, value = item.partition(":")
        parsed[key] = value
    return parsed


# Trace ID, rv and th match the RFC's own verified worked example (rate 0.1, trace ID 0xfff972474538efff),
# also used in tests/test_otel_tracestate_sampling.py. rv only depends on the trace ID, not the sample rate.
OTLP_TRACE_ID = 18444899399302180863
OTLP_RV = "ef284ace7a91e1"
OTLP_TH = "e6666666666668"


@features.otel_api
@scenarios.apm_tracing_otlp
class Test_Otlp_Carries_Ot:
    """B1: a probability sampling decision is carried on the exported OTLP span's tracestate as ot=rv:...;th:...

    See APMAPI-2172.
    """

    def setup_otlp_carries_ot(self):
        self.req = weblog.get(
            "/", headers={"x-datadog-trace-id": str(OTLP_TRACE_ID), "x-datadog-parent-id": str(OTLP_TRACE_ID)}
        )

    def test_otlp_carries_ot(self):
        data = list(interfaces.open_telemetry.get_otel_spans(self.req))
        assert len(data) >= 1, f"Expected at least one matching OTLP span, got {data}"
        _, _, span = data[0]

        ot = _parse_ot_from_trace_state(span.get("traceState", ""))
        assert ot.get("rv") == OTLP_RV, f"rv={ot.get('rv')!r}, expected {OTLP_RV!r}"
        assert "th" in ot, "no th on the exported span's tracestate for a probability sampling decision"


@features.otel_api
@scenarios.apm_tracing_otlp
class Test_Otlp_Forwards_Inherited_Ot:
    """B2: an inherited ot=rv:...;th:... is forwarded unchanged onto the exported OTLP span's tracestate.

    See APMAPI-2172.
    """

    def setup_otlp_forwards_inherited_ot(self):
        self.req = weblog.get(
            "/",
            headers={
                "traceparent": f"00-{OTLP_TRACE_ID:032x}-0000000000000001-01",
                "tracestate": f"dd=s:2;t.dm:-3,ot=rv:{OTLP_RV};th:{OTLP_TH}",
            },
        )

    def test_otlp_forwards_inherited_ot(self):
        data = list(interfaces.open_telemetry.get_otel_spans(self.req))
        assert len(data) >= 1, f"Expected at least one matching OTLP span, got {data}"
        _, _, span = data[0]

        ot = _parse_ot_from_trace_state(span.get("traceState", ""))
        assert ot.get("rv") == OTLP_RV, "inherited rv was not forwarded unchanged onto the exported OTLP span"
        assert ot.get("th") == OTLP_TH, "inherited th was not forwarded unchanged onto the exported OTLP span"
