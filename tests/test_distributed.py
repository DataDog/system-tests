# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

import json
from utils import weblog, interfaces, scenarios, features, bug, context, missing_feature, logger
from utils.parametric.spec.trace import SAMPLING_PRIORITY_KEY, ORIGIN


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
            span
            for _, _, span in interfaces.library.get_spans(self.req, full_trace=True)
            if _retrieve_span_links(span) is not None
            and span["trace_id"] == 2
            and span["parent_id"] == 10  # Only fetch the trace that is related to the header extractions
        ]

        assert len(trace) == 1
        span = trace[0]
        links = _retrieve_span_links(span)
        assert len(links) == 1
        link1 = links[0]
        assert link1["trace_id"] == 2
        assert link1["span_id"] == 987654321
        assert link1["attributes"] == {"reason": "terminated_context", "context_headers": "tracecontext"}
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
            span
            for _, _, span in interfaces.library.get_spans(self.req, full_trace=True)
            if _retrieve_span_links(span) is not None
            and span["trace_id"] == 1
            and span["parent_id"] == 987654321  # Only fetch the trace that is related to the header extractions
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
            span
            for _, _, span in interfaces.library.get_spans(self.req, full_trace=True)
            if _retrieve_span_links(span) is not None
            and span["trace_id"] == 5
            and span["parent_id"] == 987654324  # Only fetch the trace that is related to the header extractions
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
            span
            for _, _, span in interfaces.library.get_spans(self.req, full_trace=True)
            if _retrieve_span_links(span) is not None
            and span["trace_id"] == 2
            and span["parent_id"] == 987654321  # Only fetch the trace that is related to the header extractions
        ]

        if len(spans) != 1:
            logger.error(json.dumps(spans, indent=2))
            raise ValueError(f"Expected 1 span, got {len(spans)}")

        span = spans[0]
        span_links = _retrieve_span_links(span)
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
            span
            for _, _, span in interfaces.library.get_spans(self.req, full_trace=True)
            if _retrieve_span_links(span) is not None
            and span["trace_id"] == 2
            and span["parent_id"] == 987654321  # Only fetch the trace that is related to the header extractions
        ]

        if len(spans) != 1:
            logger.error(json.dumps(spans, indent=2))
            raise ValueError(f"Expected 1 span, got {len(spans)}")

        span = spans[0]
        links = _retrieve_span_links(span)
        assert len(links) == 1
        link1 = links[0]
        assert link1.get("tracestate") is None


def _retrieve_span_links(span):
    if span.get("span_links") is not None:
        return span["span_links"]

    if span["meta"].get("_dd.span_links") is not None:
        # Convert span_links tags into msgpack v0.4 format
        json_links = json.loads(span["meta"].get("_dd.span_links"))
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
@bug(context.library > "ruby@2.17.0", reason="APMRP-360")  # API security by default
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

    @missing_feature(library="cpp_httpd", reason="A non-root span carry user agent informations")
    def test_synthetics(self):
        interfaces.library.assert_trace_exists(self.r)
        spans = interfaces.agent.get_spans_list(self.r)
        assert len(spans) == 1, "Agent received the incorrect amount of spans"

        span = spans[0]
        assert span.get("traceID") == "1234567890"
        assert "parentID" not in span or span.get("parentID") == 0 or span.get("parentID") is None
        assert span.get("meta")[ORIGIN] == "synthetics"
        assert span.get("metrics")[SAMPLING_PRIORITY_KEY] == 1

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

    @missing_feature(library="cpp_httpd", reason="A non-root span carry user agent informations")
    def test_synthetics_browser(self):
        interfaces.library.assert_trace_exists(self.r)
        spans = interfaces.agent.get_spans_list(self.r)
        assert len(spans) == 1, "Agent received the incorrect amount of spans"

        span = spans[0]
        assert span.get("traceID") == "1234567891"
        assert "parentID" not in span or span.get("parentID") == 0 or span.get("parentID") is None
        assert span.get("meta")[ORIGIN] == "synthetics-browser"
        assert span.get("metrics")[SAMPLING_PRIORITY_KEY] == 1
