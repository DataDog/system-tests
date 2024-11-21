# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

from utils import weblog, interfaces, scenarios, features
from utils.tools import retrieve_span_links, TRACECONTEXT_FLAGS_SET


@scenarios.trace_propagation_style_w3c
@features.w3c_headers_injection_and_extraction
class Test_DistributedHttp:
    """ Verify behavior of http clients and distributed traces """

    def setup_main(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777"})

    def test_main(self):

        interfaces.library.assert_trace_exists(self.r)

        assert self.r.status_code == 200
        assert self.r.json() is not None
        data = self.r.json()
        assert "traceparent" in data["request_headers"]
        assert "x-datadog-parent-id" not in data["request_headers"]
        assert "x-datadog-sampling-priority" not in data["request_headers"]
        assert "x-datadog-tags" not in data["request_headers"]
        assert "x-datadog-trace-id" not in data["request_headers"]


@scenarios.trace_propagation_style_w3c_datadog_b3
@features.w3c_headers_injection_and_extraction
class Test_Span_Links_From_Conflicting_Contexts:
    """Verify headers containing conflicting trace context information are added as span links"""

    def setup_span_links_from_conflicting_contexts(self):
        extract_headers = {
            "traceparent": "00-11111111111111110000000000000002-000000003ade68b1-01",
            "tracestate": "dd=s:2;p:000000000000000a,foo=1",
            "x-datadog-parent-id": "10",
            "x-datadog-trace-id": "2",
            "x-datadog-tags": "_dd.p.tid=2222222222222222",
            "x-datadog-sampling-priority": "2",
            "x-b3-traceid": "11111111111111110000000000000003",
            "x-b3-spanid": "a2fb4a1d1a96d312",
            "x-b3-sampled": "0",
        }

        self.req = weblog.get("/make_distant_call", params={"url": "http://weblog:7777"}, headers=extract_headers)

    def test_span_links_from_conflicting_contexts(self):
        trace = [
            span
            for _, _, span in interfaces.library.get_spans(self.req, full_trace=True)
            if retrieve_span_links(span) is not None and span["trace_id"] == 2 # Only fetch the trace that is related to the header extractions
        ]

        for span in trace:
            links = retrieve_span_links(span)
            assert len(links) == 2
            print(links)
            link1 = links[0]
            assert link1["trace_id"] == 2
            assert link1["span_id"] == 10
            assert link1["attributes"] == {"reason": "terminated_context", "context_headers": "datadog"}
            assert link1["trace_id_high"] == 2459565876494606882

            link2 = links[1]
            assert link2["trace_id"] == 3
            assert link2["span_id"] == 11744061942159299346
            assert link2["attributes"] == {"reason": "terminated_context", "context_headers": "b3multi"}
            assert link2["trace_id_high"] == 1229782938247303441
            return

        # Return false if we get no span links
        assert False

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
            if retrieve_span_links(span) is not None and span["trace_id"] == 1 # Only fetch the trace that is related to the header extractions
        ]

        assert len(trace) == 0

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
            if retrieve_span_links(span) is not None and span["trace_id"] == 5 # Only fetch the trace that is related to the header extractions
        ]

        assert len(trace) == 0

    def setup_no_span_links_from_invalid_span_id(self):
        extract_headers = {
            "x-datadog-trace-id": "6",
            "x-datadog-parent-id": "987654325",
            "x-datadog-sampling-priority": "2",
            "x-datadog-tags": "_dd.p.tid=1111111111111111",
            "x-b3-traceid": "11111111111111110000000000000003",
            "x-b3-spanid": " 0000000000000000",
            "x-b3-sampled": "1",
        }

        self.req = weblog.get("/make_distant_call", params={"url": "http://weblog:7777"}, headers=extract_headers)

    def test_no_span_links_from_invalid_span_id(self):
        trace = [
            span
            for _, _, span in interfaces.library.get_spans(self.req, full_trace=True)
            if retrieve_span_links(span) is not None and span["trace_id"] == 6 # Only fetch the trace that is related to the header extractions
        ]

        assert len(trace) == 0


@scenarios.trace_propagation_style_datadog_w3c_b3
@features.w3c_headers_injection_and_extraction
class Test_Span_Links_From_Conflicting_Contexts_Datadog_Precedence:
    """Verify headers containing conflicting trace context information are added as span links"""

    def setup_span_links_from_conflicting_contexts_datadog_precedence(self):
        extract_headers = {
           "traceparent": "00-11111111111111110000000000000001-000000003ade68b1-01",
            "tracestate": "dd=s:2;t.tid:1111111111111111,foo=1",
            "x-datadog-trace-id": "4",
            "x-datadog-parent-id": "987654323",
            "x-datadog-sampling-priority": "2",
            "x-datadog-tags": "_dd.p.tid=1111111111111111",
            "x-b3-traceid": "11111111111111110000000000000003",
            "x-b3-spanid": "a2fb4a1d1a96d312",
            "x-b3-sampled": "1",
        }

        self.req = weblog.get("/make_distant_call", params={"url": "http://weblog:7777"}, headers=extract_headers)

    def test_span_links_from_conflicting_contexts_datadog_precedence(self):
        trace = [
            span
            for _, _, span in interfaces.library.get_spans(self.req, full_trace=True)
            if retrieve_span_links(span) is not None and span["trace_id"] == 4 # Only fetch the trace that is related to the header extractions
        ]

        for span in trace:
            links = retrieve_span_links(span)
            assert len(links) == 2
            link1 = links[0]
            assert link1["trace_id"] == 1
            assert link1["span_id"] == 987654321
            assert link1["attributes"] == {"reason": "terminated_context", "context_headers": "tracecontext"}
            assert link1["tracestate"] == "dd=s:2;t.tid:1111111111111111,foo=1"
            assert link1["trace_id_high"] == 1229782938247303441
            
            link2 = links[1]
            assert link2["trace_id"] == 3
            assert link2["span_id"] == 11744061942159299346
            assert link2["attributes"] == {"reason": "terminated_context", "context_headers": "b3multi"}
            assert link2["trace_id_high"] == 1229782938247303441
            return

        # Return false if we get no span links
        assert False

@scenarios.trace_propagation_style_w3c_datadog_b3
@features.w3c_headers_injection_and_extraction
class Test_Span_Links_Flags_From_Conflicting_Contexts:
    """Verify headers containing conflicting trace context information are added as span links"""

    def setup_span_links_from_conflicting_contexts(self):
        extract_headers = {
            "traceparent": "00-11111111111111110000000000000002-000000003ade68b1-01",
            "tracestate": "dd=s:2;p:000000000000000a,foo=1",
            "x-datadog-parent-id": "10",
            "x-datadog-trace-id": "2",
            "x-datadog-tags": "_dd.p.tid=2222222222222222",
            "x-datadog-sampling-priority": "2",
            "x-b3-traceid": "11111111111111110000000000000003",
            "x-b3-spanid": "a2fb4a1d1a96d312",
            "x-b3-sampled": "0",
        }

        self.req = weblog.get("/make_distant_call", params={"url": "http://weblog:7777"}, headers=extract_headers)

    def test_span_links_from_conflicting_contexts(self):
        trace = [
            span
            for _, _, span in interfaces.library.get_spans(self.req, full_trace=True)
            if retrieve_span_links(span) is not None and span["trace_id"] == 2 # Only fetch the trace that is related to the header extractions
        ]

        for span in trace:
            span_links = retrieve_span_links(span)
            assert len(span_links) == 2
            link1 = span_links[0]
            assert link1["flags"] == 1 | TRACECONTEXT_FLAGS_SET

            link2 = span_links[1]
            assert link2["flags"] == 0 | TRACECONTEXT_FLAGS_SET
            return

        # Return false if we get no span links
        assert False

@scenarios.trace_propagation_style_w3c_datadog_b3
@features.w3c_headers_injection_and_extraction
class Test_Span_Links_Omit_Tracestate_From_Conflicting_Contexts:
    """Verify headers containing conflicting trace context information are added as span links"""

    def setup_span_links_omit_tracestate_from_conflicting_contexts(self):
        extract_headers = {
            "traceparent": "00-11111111111111110000000000000002-000000003ade68b1-01",
            "tracestate": "dd=s:2;p:000000000000000a,foo=1",
            "x-datadog-parent-id": "10",
            "x-datadog-trace-id": "2",
            "x-datadog-tags": "_dd.p.tid=2222222222222222",
            "x-datadog-sampling-priority": "2",
        }

        self.req = weblog.get("/make_distant_call", params={"url": "http://weblog:7777"}, headers=extract_headers)

    def test_span_links_omit_tracestate_from_conflicting_contexts(self):
        trace = [
            span
            for _, _, span in interfaces.library.get_spans(self.req, full_trace=True)
            if retrieve_span_links(span) is not None and span["trace_id"] == 2 # Only fetch the trace that is related to the header extractions
        ]

        for span in trace:
            links = retrieve_span_links(span)
            assert len(links) == 1
            link1 = links[0]
            assert link1.get("tracestate") == None
            return

        # Return false if we get no span links
        assert False
