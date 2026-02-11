# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

import ast
import json
import re
from utils import weblog, interfaces, scenarios, features, bug, context, logger
from utils.dd_constants import TraceAgentPayloadFormat, TraceLibraryPayloadFormat
from utils.docker_fixtures.spec.trace import SAMPLING_PRIORITY_KEY, ORIGIN


@scenarios.trace_propagation_style_w3c
@features.w3c_headers_injection_and_extraction
class Test_DistributedHttp:
    """Verify behavior of http clients and distributed traces"""

    def setup_main(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777"})

    def test_main(self):
        interfaces.library.assert_trace_exists(self.r)

        assert self.r.status_code == 200
        data = json.loads(self.r.text)
        assert "traceparent" in data["request_headers"]
        assert "x-datadog-parent-id" not in data["request_headers"]
        assert "x-datadog-sampling-priority" not in data["request_headers"]
        assert "x-datadog-tags" not in data["request_headers"]
        assert "x-datadog-trace-id" not in data["request_headers"]


@scenarios.default
@features.w3c_headers_injection_and_extraction
@bug(
    context.library < "java@1.44.0" and context.weblog_variant == "spring-boot-3-native",
    reason="APMAPI-928",
    force_skip=True,
)
class Test_Span_Links_From_Conflicting_Contexts:
    """Verify headers containing conflicting trace context information are added as span links"""

    """Datadog, tracecontext, b3multi headers, Datadog is primary context tracecontext and b3multi
    trace_id do match it we should have two span links, b3multi should not have tracestate"""

    def setup_span_links_from_conflicting_contexts(self):
        extract_headers = {
            "x-datadog-parent-id": "10",
            "x-datadog-trace-id": "2",
            "x-datadog-tags": "_dd.p.tid=2222222222222222",
            "x-datadog-sampling-priority": "2",
            "traceparent": "00-11111111111111110000000000000002-000000003ade68b1-01",
            "tracestate": "dd=s:2;p:000000000000000a,foo=1",
            "x-b3-traceid": "11111111111111110000000000000003",
            "x-b3-spanid": "a2fb4a1d1a96d312",
            "x-b3-sampled": "0",
        }

        self.req = weblog.get("/make_distant_call", params={"url": "http://weblog:7777"}, headers=extract_headers)

    def test_span_links_from_conflicting_contexts(self):
        trace = [
            (span, span_format, trace_chunk)
            for _, trace_chunk, span, span_format in interfaces.library.get_spans(self.req, full_trace=True)
            if _retrieve_span_links(span, span_format) is not None
            and interfaces.library.get_span_trace_id(
                span, trace_chunk if isinstance(trace_chunk, dict) else None, span_format
            )
            == 2
            and interfaces.library.get_span_parent_id(span, span_format)
            == 10  # Only fetch the trace that is related to the header extractions
        ]

        assert len(trace) == 1, f"Expected 1 span with matching criteria, got {len(trace)}. Trace: {trace}"
        span, span_format, _trace_chunk = trace[0]
        links = _retrieve_span_links(span, span_format)
        assert links is not None, f"No span links found in span. Span keys: {list(span.keys())}"
        assert len(links) == 1, f"Expected 1 link, got {len(links)}. Links: {links}"
        link1 = links[0]
        assert "trace_id" in link1, f"trace_id not found in link. Link keys: {list(link1.keys())}, Link: {link1}"
        # Convert hex trace_id to int if needed
        trace_id_value = link1["trace_id"]
        if isinstance(trace_id_value, str) and trace_id_value.startswith("0x"):
            trace_id_value = int(trace_id_value[-16:], 16)
        assert trace_id_value == 2, f"Expected trace_id 2, got {trace_id_value}"
        assert link1["span_id"] == 987654321
        assert link1["attributes"] == {"reason": "terminated_context", "context_headers": "tracecontext"}
        # trace_id_high might not be present in v1 format
        if "trace_id_high" in link1:
            assert link1["trace_id_high"] == 1229782938247303441

    """Datadog and tracecontext headers, trace-id does match, Datadog is primary
    context we want to make sure there's no span link since they match"""

    def setup_no_span_links_from_nonconflicting_contexts(self):
        extract_headers = {
            "traceparent": "00-11111111111111110000000000000001-000000003ade68b1-01",
            "tracestate": "dd=s:2;t.tid:1111111111111111,foo=1",
            "x-datadog-trace-id": "1",
            "x-datadog-parent-id": "987654322",
            "x-datadog-sampling-priority": "2",
            "x-datadog-tags": "_dd.p.tid=1111111111111111",
        }

        self.req = weblog.get("/make_distant_call", params={"url": "http://weblog:7777"}, headers=extract_headers)

    def test_no_span_links_from_nonconflicting_contexts(self):
        trace = [
            (span, span_format, trace_chunk)
            for _, trace_chunk, span, span_format in interfaces.library.get_spans(self.req, full_trace=True)
            if _retrieve_span_links(span, span_format) is not None
            and interfaces.library.get_span_trace_id(
                span, trace_chunk if isinstance(trace_chunk, dict) else None, span_format
            )
            == 1
            and interfaces.library.get_span_parent_id(span, span_format)
            == 987654321  # Only fetch the trace that is related to the header extractions
        ]

        assert len(trace) == 0

    """Datadog, b3multi headers edge case where we want to make sure NOT to create a
    span_link if the secondary context has trace_id 0 since that's not valid."""

    def setup_no_span_links_from_invalid_trace_id(self):
        extract_headers = {
            "x-datadog-trace-id": "5",
            "x-datadog-parent-id": "987654324",
            "x-datadog-sampling-priority": "2",
            "x-datadog-tags": "_dd.p.tid=1111111111111111",
            "x-b3-traceid": "00000000000000000000000000000000",
            "x-b3-spanid": "a2fb4a1d1a96d314",
            "x-b3-sampled": "1",
        }

        self.req = weblog.get("/make_distant_call", params={"url": "http://weblog:7777"}, headers=extract_headers)

    def test_no_span_links_from_invalid_trace_id(self):
        trace = [
            (span, span_format, trace_chunk)
            for _, trace_chunk, span, span_format in interfaces.library.get_spans(self.req, full_trace=True)
            if _retrieve_span_links(span, span_format) is not None
            and interfaces.library.get_span_trace_id(
                span, trace_chunk if isinstance(trace_chunk, dict) else None, span_format
            )
            == 5
            and interfaces.library.get_span_parent_id(span, span_format)
            == 987654324  # Only fetch the trace that is related to the header extractions
        ]

        assert len(trace) == 0


@scenarios.default
@features.w3c_headers_injection_and_extraction
@bug(
    context.library < "java@1.44.0" and context.weblog_variant == "spring-boot-3-native",
    reason="APMAPI-928",
    force_skip=True,
)
class Test_Span_Links_Flags_From_Conflicting_Contexts:
    """Verify span links created from conflicting header contexts have the correct flags set"""

    def setup_span_links_flags_from_conflicting_contexts(self):
        extract_headers = {
            "traceparent": "00-11111111111111110000000000000002-000000003ade68b1-01",
            "tracestate": "dd=s:2;p:000000000000000a,foo=1",
            "x-datadog-parent-id": "10",
            "x-datadog-trace-id": "2",
            "x-datadog-tags": "_dd.p.tid=2222222222222222",
            "x-datadog-sampling-priority": "2",
        }

        self.req = weblog.get("/make_distant_call", params={"url": "http://weblog:7777"}, headers=extract_headers)

    def test_span_links_flags_from_conflicting_contexts(self):
        spans = [
            (span, span_format, trace_chunk)
            for _, trace_chunk, span, span_format in interfaces.library.get_spans(self.req, full_trace=True)
            if _retrieve_span_links(span, span_format) is not None
            and interfaces.library.get_span_trace_id(
                span, trace_chunk if isinstance(trace_chunk, dict) else None, span_format
            )
            == 2
            and interfaces.library.get_span_parent_id(span, span_format)
            == 987654321  # Only fetch the trace that is related to the header extractions
        ]

        if len(spans) != 1:
            logger.error(json.dumps(spans, indent=2))
            raise ValueError(f"Expected 1 span, got {len(spans)}")

        span, span_format, _ = spans[0]
        span_links = _retrieve_span_links(span, span_format)
        assert len(span_links) == 2
        link1 = span_links[0]
        assert link1["flags"] == 1 | TRACECONTEXT_FLAGS_SET


@scenarios.default
@features.w3c_headers_injection_and_extraction
@bug(
    context.library < "java@1.44.0" and context.weblog_variant == "spring-boot-3-native",
    reason="APMAPI-928",
    force_skip=True,
)
class Test_Span_Links_Omit_Tracestate_From_Conflicting_Contexts:
    """Verify span links created from conflicting header contexts properly omit the tracestate when conflicting propagator is not W3C"""

    def setup_span_links_omit_tracestate_from_conflicting_contexts(self):
        extract_headers = {
            "traceparent": "00-11111111111111110000000000000002-000000003ade68b1-01",
            "tracestate": "dd=s:2;p:000000000000000a,foo=1",
            "x-b3-traceid": "22222222222222220000000000000002",
            "x-b3-spanid": "000000000000000a",
            "x-b3-sampled": "1",
        }

        self.req = weblog.get("/make_distant_call", params={"url": "http://weblog:7777"}, headers=extract_headers)

    def test_span_links_omit_tracestate_from_conflicting_contexts(self):
        spans = [
            (span, span_format, trace_chunk)
            for _, trace_chunk, span, span_format in interfaces.library.get_spans(self.req, full_trace=True)
            if _retrieve_span_links(span, span_format) is not None
            and interfaces.library.get_span_trace_id(
                span, trace_chunk if isinstance(trace_chunk, dict) else None, span_format
            )
            == 2
            and interfaces.library.get_span_parent_id(span, span_format)
            == 987654321  # Only fetch the trace that is related to the header extractions
        ]

        if len(spans) != 1:
            logger.error(json.dumps(spans, indent=2))
            raise ValueError(f"Expected 1 span, got {len(spans)}")

        span, span_format, _ = spans[0]
        links = _retrieve_span_links(span, span_format)
        assert len(links) == 1
        link1 = links[0]
        assert link1.get("tracestate") is None


def _retrieve_span_links(span: dict, span_format: TraceLibraryPayloadFormat | None = None):
    # Check for span_links at top level (v1 format or v04 with span_links field)
    # Also check for "links" which is used in v1 format
    span_links = span.get("span_links") or span.get("links")
    if span_links is not None:
        # If format is v1, the links might need conversion
        if span_format == TraceLibraryPayloadFormat.v1:
            # v1 format span_links - convert to v04-like format for consistency
            converted_links = []
            for link in span_links:
                logger.debug(f"Processing v1 span link. Link keys: {list(link.keys())}, Link: {link}")
                converted_link = {}
                # Handle trace_id - check various possible key names and formats
                trace_id = (
                    link.get("trace_id") or link.get("traceID") or link.get("traceId") or link.get(1)
                )  # V1SpanLinkKeys.trace_id = 1
                if trace_id is None and 1 in link:
                    trace_id = link[1]
                if trace_id is not None:
                    if isinstance(trace_id, str):
                        # Handle string representation of bytes (e.g., "b'\\x11\\x11...'")
                        if trace_id.startswith(("b'", 'b"')):
                            # Remove b' or b" prefix and suffix
                            bytes_str = trace_id[2:-1]
                            # Parse escape sequences to get actual bytes
                            try:
                                # Use ast.literal_eval to safely parse the bytes literal
                                bytes_obj = ast.literal_eval(trace_id)
                                if isinstance(bytes_obj, bytes):
                                    # Convert bytes to int (big-endian)
                                    if len(bytes_obj) >= 8:
                                        # Lower 64 bits (last 8 bytes)
                                        converted_link["trace_id"] = int.from_bytes(bytes_obj[-8:], byteorder="big")
                                        # Upper 64 bits if present (first 8 bytes)
                                        if len(bytes_obj) > 8:
                                            converted_link["trace_id_high"] = int.from_bytes(
                                                bytes_obj[:8], byteorder="big"
                                            )
                                    else:
                                        # Pad with zeros if less than 8 bytes
                                        padded = bytes_obj + b"\x00" * (8 - len(bytes_obj))
                                        converted_link["trace_id"] = int.from_bytes(padded, byteorder="big")
                                else:
                                    # Fallback to hex parsing
                                    raise TypeError("Not bytes")
                            except (ValueError, SyntaxError):
                                # Fallback: try to parse as hex string
                                # Remove b' or b" and parse escape sequences manually
                                # Extract hex values from escape sequences
                                hex_values = re.findall(r"\\x([0-9a-fA-F]{2})", bytes_str)
                                if hex_values:
                                    # Convert hex values to bytes
                                    bytes_obj = bytes(int(h, 16) for h in hex_values)
                                    if len(bytes_obj) >= 8:
                                        converted_link["trace_id"] = int.from_bytes(bytes_obj[-8:], byteorder="big")
                                        if len(bytes_obj) > 8:
                                            converted_link["trace_id_high"] = int.from_bytes(
                                                bytes_obj[:8], byteorder="big"
                                            )
                                    else:
                                        padded = bytes_obj + b"\x00" * (8 - len(bytes_obj))
                                        converted_link["trace_id"] = int.from_bytes(padded, byteorder="big")
                                else:
                                    # Last resort: try direct hex parsing
                                    trace_id_str = trace_id.strip("b'\"")
                                    if len(trace_id_str) >= 16:
                                        converted_link["trace_id"] = int(trace_id_str[-16:], 16)
                                    else:
                                        converted_link["trace_id"] = int(trace_id_str, 16)
                        # Handle hex string (with or without 0x prefix)
                        elif trace_id.startswith("0x"):
                            trace_id_str = trace_id[2:]
                            # Extract lower 64 bits
                            if len(trace_id_str) >= 16:
                                converted_link["trace_id"] = int(trace_id_str[-16:], 16)
                                # Extract upper 64 bits if present
                                if len(trace_id_str) > 16:
                                    converted_link["trace_id_high"] = int(trace_id_str[:-16], 16)
                            else:
                                converted_link["trace_id"] = int(trace_id_str, 16)
                        else:
                            # Try to parse as hex string
                            try:
                                # Check if it's a valid hex string
                                if all(c in "0123456789abcdefABCDEF" for c in trace_id):
                                    trace_id_str = trace_id
                                    if len(trace_id_str) >= 16:
                                        converted_link["trace_id"] = int(trace_id_str[-16:], 16)
                                        if len(trace_id_str) > 16:
                                            converted_link["trace_id_high"] = int(trace_id_str[:-16], 16)
                                    else:
                                        converted_link["trace_id"] = int(trace_id_str, 16)
                                else:
                                    # Not a valid hex string, try as decimal
                                    converted_link["trace_id"] = int(trace_id)
                            except ValueError:
                                # If all else fails, try to parse as int directly
                                converted_link["trace_id"] = int(trace_id)
                    elif isinstance(trace_id, bytes):
                        # Handle actual bytes object
                        if len(trace_id) >= 8:
                            converted_link["trace_id"] = int.from_bytes(trace_id[-8:], byteorder="big")
                            if len(trace_id) > 8:
                                converted_link["trace_id_high"] = int.from_bytes(trace_id[:8], byteorder="big")
                        else:
                            padded = trace_id + b"\x00" * (8 - len(trace_id))
                            converted_link["trace_id"] = int.from_bytes(padded, byteorder="big")
                    else:
                        # Already an int
                        converted_link["trace_id"] = trace_id

                # Handle span_id
                span_id = (
                    link.get("span_id") or link.get("spanID") or link.get("spanId") or link.get(2)
                )  # V1SpanLinkKeys.span_id = 2
                if span_id is None and 2 in link:
                    span_id = link[2]
                if span_id is not None:
                    if isinstance(span_id, str):
                        converted_link["span_id"] = (
                            int(span_id, 16)
                            if span_id.startswith("0x") or all(c in "0123456789abcdefABCDEF" for c in span_id)
                            else int(span_id)
                        )
                    else:
                        converted_link["span_id"] = span_id

                # Copy other fields
                # Check for attributes (key 3 in v1 format)
                if "attributes" in link:
                    converted_link["attributes"] = link["attributes"]
                elif 3 in link:
                    converted_link["attributes"] = link[3]
                # Check for tracestate (key 4 in v1 format)
                if "tracestate" in link:
                    converted_link["tracestate"] = link["tracestate"]
                elif "trace_state" in link:
                    converted_link["tracestate"] = link["trace_state"]
                elif 4 in link:
                    converted_link["tracestate"] = link[4]
                # Check for flags (key 5 in v1 format)
                if "flags" in link:
                    converted_link["flags"] = link["flags"] | 1 << 31
                elif 5 in link:
                    converted_link["flags"] = link[5] | 1 << 31
                else:
                    converted_link["flags"] = 0
                converted_links.append(converted_link)
            return converted_links
        # v04 format - return as is
        return span_links

    # Check meta for _dd.span_links (v04 format stored in meta)
    meta = interfaces.library.get_span_meta(span, span_format) if span_format is not None else span.get("meta", {})
    span_links_value = meta.get("_dd.span_links")
    if span_links_value is not None:
        # Convert span_links tags into msgpack v0.4 format
        json_links = json.loads(span_links_value)
        links = []
        for json_link in json_links:
            link = {}
            link["trace_id"] = int(json_link["trace_id"][-16:], base=16)
            link["span_id"] = int(json_link["span_id"], base=16)
            if len(json_link["trace_id"]) > 16:
                link["trace_id_high"] = int(json_link["trace_id"][:16], base=16)
            if "attributes" in json_link:
                link["attributes"] = json_link.get("attributes")
            if "tracestate" in json_link:
                link["tracestate"] = json_link.get("tracestate")
            elif "trace_state" in json_link:
                link["tracestate"] = json_link.get("trace_state")
            if "flags" in json_link:
                link["flags"] = json_link.get("flags") | 1 << 31
            else:
                link["flags"] = 0
            links.append(link)
        return links
    return None


# The Datadog specific tracecontext flags to mark flags are set
TRACECONTEXT_FLAGS_SET = 1 << 31


@scenarios.default
@features.datadog_headers_propagation
class Test_Synthetics_APM_Datadog:
    def setup_synthetics(self):
        self.r = weblog.get(
            "/",
            headers={
                "x-datadog-trace-id": "1234567890",
                "x-datadog-parent-id": "0",
                "x-datadog-sampling-priority": "1",
                "x-datadog-origin": "synthetics",
            },
        )

    def test_synthetics(self):
        interfaces.library.assert_trace_exists(self.r)
        traces = list(interfaces.agent.get_traces(self.r))
        assert len(traces) == 1, "Agent received the incorrect amount of traces"

        _, trace, trace_format = traces[0]
        self.assert_trace_id_equals(trace, trace_format, "1234567890")
        spans = list(interfaces.agent.get_spans(self.r))
        assert len(spans) == 1, "Agent received the incorrect amount of spans"
        _, span, span_format = spans[0]
        # parentID is an agent format field, not library format - keep direct access
        assert "parentID" not in span or span.get("parentID") == 0 or span.get("parentID") is None

        meta = interfaces.agent.get_span_meta(span, span_format)
        metrics = interfaces.agent.get_span_metrics(span, span_format)
        assert meta[ORIGIN] == "synthetics"
        assert metrics[SAMPLING_PRIORITY_KEY] == 1

    def setup_synthetics_browser(self):
        self.r = weblog.get(
            "/",
            headers={
                "x-datadog-trace-id": "1234567891",
                "x-datadog-parent-id": "0",
                "x-datadog-sampling-priority": "1",
                "x-datadog-origin": "synthetics-browser",
            },
        )

    def test_synthetics_browser(self):
        interfaces.library.assert_trace_exists(self.r)
        traces = list(interfaces.agent.get_traces(self.r))
        assert len(traces) == 1, "Agent received the incorrect amount of traces"
        _, trace, trace_format = traces[0]
        self.assert_trace_id_equals(trace, trace_format, "1234567891")

        spans = list(interfaces.agent.get_spans(self.r))
        assert len(spans) == 1, "Agent received the incorrect amount of spans"
        _, span, span_format = spans[0]
        # parentID is an agent format field, not library format - keep direct access
        assert "parentID" not in span or span.get("parentID") == 0 or span.get("parentID") is None

        meta = interfaces.agent.get_span_meta(span, span_format)
        metrics = interfaces.agent.get_span_metrics(span, span_format)
        assert meta[ORIGIN] == "synthetics-browser"
        assert metrics[SAMPLING_PRIORITY_KEY] == 1

    @staticmethod
    def assert_trace_id_equals(trace: dict, trace_format: TraceAgentPayloadFormat, expected_trace_id: str) -> None:
        if trace_format == TraceAgentPayloadFormat.legacy:
            actual_trace_id = str(trace["spans"][0]["traceID"])
            assert expected_trace_id == actual_trace_id
        elif trace_format == TraceAgentPayloadFormat.efficient_trace_payload_format:
            actual_trace_id = str(trace["traceID"])
            # In efficient trace payload format, traceID is in hex format
            actual_trace_id = str(int(actual_trace_id, 16))
            assert actual_trace_id == expected_trace_id
        else:
            raise ValueError(f"Unknown span format: {trace_format}")
