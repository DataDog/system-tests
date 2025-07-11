import json
import pytest

from utils.parametric.spec.trace import ORIGIN
from utils.parametric.spec.trace import SAMPLING_PRIORITY_KEY
from utils.parametric.spec.trace import AUTO_DROP_KEY
from utils.parametric.spec.trace import span_has_no_parent
from utils.parametric.spec.tracecontext import TRACECONTEXT_FLAGS_SET
from utils import scenarios, missing_feature, features
from utils.parametric.spec.trace import retrieve_span_links, find_span, find_trace, find_span_in_traces


@scenarios.parametric
@features.span_links
class Test_Span_Links:
    @pytest.mark.parametrize("library_env", [{"DD_TRACE_API_VERSION": "v0.4"}])
    @missing_feature(library="nodejs", reason="only supports span links encoding through _dd.span_links tag")
    def test_span_started_with_link_v04(self, test_agent, test_library):
        """Test adding a span link created from another span and serialized in the expected v0.4 format.
        This tests the functionality of "create a direct link between two spans
        given two valid span (or SpanContext) objects" as specified in the RFC.
        """
        with test_library:
            with test_library.dd_start_span("first") as s1:
                pass

            with test_library.dd_start_span("second") as s2:
                s2.add_link(s1.span_id, attributes={"foo": "bar", "array": ["a", "b", "c"]})

        traces = test_agent.wait_for_num_traces(2)
        trace1 = find_trace(traces, s1.trace_id)
        assert len(trace1) == 1
        trace2 = find_trace(traces, s2.trace_id)
        assert len(trace2) == 1

        first = find_span(trace1, s1.span_id)
        second = find_span(trace2, s2.span_id)

        span_links = second["span_links"]
        assert len(span_links) == 1
        link = span_links[0]
        assert link["span_id"] == first["span_id"]
        assert link["trace_id"] == first["trace_id"]
        first_tid = first.get("meta", {}).get("_dd.p.tid", 0)
        assert (link.get("trace_id_high") or 0) == int(first_tid, 16)
        assert link["attributes"].get("foo") == "bar"
        assert link["attributes"].get("array.0") == "a"
        assert link["attributes"].get("array.1") == "b"
        assert link["attributes"].get("array.2") == "c"

    @missing_feature(library="ruby", reason="v0.5 is not supported in Ruby")
    @pytest.mark.parametrize("library_env", [{"DD_TRACE_API_VERSION": "v0.5"}])
    def test_span_started_with_link_v05(self, test_agent, test_library):
        """Test adding a span link created from another span and serialized in the expected v0.5 format.
        This tests the functionality of "create a direct link between two spans
        given two valid span (or SpanContext) objects" as specified in the RFC.
        """
        with test_library:
            # create a span that will be sampled
            with test_library.dd_start_span("first") as s1:
                pass

            with test_library.dd_start_span("second") as s2:
                s2.add_link(parent_id=s1.span_id, attributes={"foo": "bar", "array": ["a", "b", "c"]})

        traces = test_agent.wait_for_num_traces(2)
        trace1 = find_trace(traces, s1.trace_id)
        assert len(trace1) == 1
        trace2 = find_trace(traces, s2.trace_id)
        assert len(trace2) == 1

        first = find_span(trace1, s1.span_id)
        second = find_span(trace2, s2.span_id)

        span_links = json.loads(second.get("meta", {}).get("_dd.span_links"))
        assert len(span_links) == 1
        link = span_links[0]
        first_tid_upper64 = first.get("meta", {}).get("_dd.p.tid", "0000000000000000")
        first_tid_lower64 = "{:016x}".format(first["trace_id"])
        assert link.get("trace_id") == f"{first_tid_upper64}{first_tid_lower64}"
        assert link.get("span_id") == "{:016x}".format(first["span_id"])
        assert link["attributes"].get("foo") == "bar"
        assert link["attributes"].get("array.0") == "a"
        assert link["attributes"].get("array.1") == "b"
        assert link["attributes"].get("array.2") == "c"

    @missing_feature(
        library="nodejs", reason="does not currently support creating a link from distributed datadog headers"
    )
    def test_span_link_from_distributed_datadog_headers(self, test_agent, test_library):
        """Properly inject datadog distributed tracing information into span links when trace_api is v0.4.
        Testing the conversion of x-datadog-* headers to tracestate for
        representation in span links.
        """
        with test_library, test_library.dd_start_span("root") as rs:
            parent_id = test_library.dd_extract_headers(
                http_headers=[
                    ["x-datadog-trace-id", "1234567890"],
                    ["x-datadog-parent-id", "9876543210"],
                    ["x-datadog-sampling-priority", "2"],
                    ["x-datadog-origin", "synthetics"],
                    ["x-datadog-tags", "_dd.p.dm=-4,_dd.p.tid=0000000000000010"],
                ]
            )
            rs.add_link(parent_id=parent_id, attributes={"foo": "bar"})

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace(traces, rs.trace_id)
        span = find_span(trace, rs.span_id)
        assert span_has_no_parent(span)
        assert span.get("trace_id") != 1234567890
        assert span["meta"].get(ORIGIN) is None

        span_links = retrieve_span_links(span)
        assert len(span_links) == 1
        link = span_links[0]
        assert link.get("span_id") == 9876543210
        assert link.get("trace_id") == 1234567890
        assert link.get("trace_id_high") == 16

        # link has a sampling priority of 2, so it should be sampled
        assert link.get("flags", 1) == 1 | TRACECONTEXT_FLAGS_SET
        assert link["attributes"] == {"foo": "bar"}

    def test_span_link_from_distributed_w3c_headers(self, test_agent, test_library):
        """Properly inject w3c distributed tracing information into span links.
        This mostly tests that the injected tracestate and flags are accurate.
        """
        with test_library, test_library.dd_start_span("root") as rs:
            parent_id = test_library.dd_extract_headers(
                http_headers=[
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                    ["tracestate", "foo=1,dd=t.dm:-4;s:2,bar=baz"],
                ]
            )
            rs.add_link(parent_id=parent_id)

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace(traces, rs.trace_id)
        span = find_span(trace, rs.span_id)
        assert span_has_no_parent(span)
        assert span.get("trace_id") != 1234567890

        span_links = retrieve_span_links(span)
        assert len(span_links) == 1
        link = span_links[0]
        assert link.get("span_id") == 1311768467284833366
        assert link.get("trace_id") == 8687463697196027922
        assert link.get("trace_id_high") == 1311768467284833366

        assert link.get("tracestate") is not None
        tracestate_arr = link["tracestate"].split(",")
        assert len(tracestate_arr) >= 2, tracestate_arr
        assert next(filter(lambda x: x.startswith("foo="), tracestate_arr)) == "foo=1"
        assert next(filter(lambda x: x.startswith("bar="), tracestate_arr)) == "bar=baz"
        if "dd=" in tracestate_arr:
            # ruby does not store dd members in tracestate
            tracestate_dd = next(filter(lambda x: x.startswith("dd="), tracestate_arr))
            assert "s:2" in tracestate_dd
            assert "t.dm:-4" in tracestate_dd

        # link has a sampling priority of 2, so it should be sampled
        assert link.get("flags") == 1 | TRACECONTEXT_FLAGS_SET
        assert len(link.get("attributes") or {}) == 0

    def test_span_with_attached_links(self, test_agent, test_library):
        """Test adding a span link from a span to another span."""
        with test_library:
            with (
                test_library.dd_start_span("first") as s1,
                test_library.dd_start_span("second", parent_id=s1.span_id) as s2,
            ):
                pass
            with test_library.dd_start_span("third") as s3:
                s3.add_link(s1.span_id)
                s3.add_link(s2.span_id, attributes={"bools": [True, False], "nested": [1, 2]})

        traces = test_agent.wait_for_num_traces(2)
        trace1 = find_trace(traces, s1.trace_id)
        assert len(trace1) == 2
        trace2 = find_trace(traces, s3.trace_id)
        assert len(trace2) == 1

        root = find_span(trace1, s1.span_id)
        root_tid = root["meta"].get("_dd.p.tid") or "0" if "meta" in root else "0"

        second = find_span(trace1, s2.span_id)
        third = find_span(trace2, s3.span_id)

        assert second.get("parent_id") == root.get("span_id")
        assert third.get("parent_id") != root.get("span_id")

        span_links = retrieve_span_links(third)
        assert len(span_links) == 2

        link = span_links[0]
        assert link.get("span_id") == root.get("span_id")
        assert link.get("trace_id") == root.get("trace_id")
        assert (link.get("trace_id_high") or 0) == int(root_tid, 16)
        assert len(link.get("attributes") or {}) == 0

        link = span_links[1]
        assert link.get("span_id") == second.get("span_id")
        assert link.get("trace_id") == second.get("trace_id")
        assert (link.get("trace_id_high") or 0) == int(root_tid, 16)
        assert len(link.get("attributes")) == 4
        assert link["attributes"].get("bools.0") == "true"
        assert link["attributes"].get("bools.1") == "false"
        assert link["attributes"].get("nested.0") == "1"
        assert link["attributes"].get("nested.1") == "2"

    @missing_feature(library="python", reason="links do not influence the sampling decision of spans")
    @missing_feature(library="nodejs", reason="links do not influence the sampling decision of spans")
    @missing_feature(library="ruby", reason="links do not influence the sampling decision of spans")
    def test_span_link_propagated_sampling_decisions(self, test_agent, test_library):
        """Sampling decisions made by an upstream span should be propagated via span links to
        downstream spans.
        """
        with test_library:
            with test_library.dd_start_span("link_w_manual_keep") as s1:
                parent_id = test_library.dd_extract_headers(
                    http_headers=[
                        ["x-datadog-trace-id", "666"],
                        ["x-datadog-parent-id", "777"],
                        ["x-datadog-sampling-priority", "2"],
                        ["x-datadog-tags", "_dd.p.dm=-0,_dd.p.tid=0000000000000010"],
                    ]
                )
                s1.add_link(parent_id=parent_id)

            with test_library.dd_start_span("link_w_manual_drop") as s2:
                parent_id = test_library.dd_extract_headers(
                    http_headers=[
                        ["traceparent", "00-66645678901234567890123456789012-0000000000000011-01"],
                        ["tracestate", "foo=1,dd=t.dm:-3;s:-1,bar=baz"],
                    ]
                )
                s2.add_link(parent_id=parent_id)

            with test_library.dd_start_span("auto_dropped_span") as ads:
                ads.set_meta(AUTO_DROP_KEY, "")
                # We must add a link to linked_to_auto_dropped_span before auto_dropped_span ends
                with test_library.dd_start_span("linked_to_auto_dropped_span") as s3:
                    s3.add_link(parent_id=ads.span_id)

        traces = test_agent.wait_for_num_traces(4)
        # Span Link generated from datadog headers containing manual keep
        trace1 = find_trace(traces, s1.trace_id)
        link_w_manual_keep = find_span(trace1, s1.span_id)
        # assert that span link is set up correctly
        span_links = retrieve_span_links(link_w_manual_keep)
        assert len(span_links) == 1
        assert span_links[0]["span_id"] == 777
        # assert that sampling decision is propagated by the span link
        assert link_w_manual_keep["meta"].get("_dd.p.dm") == "-0"
        assert link_w_manual_keep["metrics"].get(SAMPLING_PRIORITY_KEY) == 2

        # Span Link generated from tracecontext headers containing manual drop
        trace2 = find_trace(traces, s2.trace_id)
        link_w_manual_drop = find_span(trace2, s2.span_id)
        # assert that span link is set up correctly
        span_links = retrieve_span_links(link_w_manual_drop)
        assert len(span_links) == 1
        assert span_links[0]["span_id"] == 17
        # assert that sampling decision is propagated by the span link
        assert link_w_manual_drop["meta"].get("_dd.p.dm") == "-3"
        assert link_w_manual_drop["metrics"].get(SAMPLING_PRIORITY_KEY) == -1

        # Span Link generated between two root spans
        auto_dropped_span = find_span_in_traces(traces, ads.trace_id, ads.span_id)
        linked_to_auto_dropped_span = find_span_in_traces(traces, s3.trace_id, s3.span_id)
        # assert that span link is set up correctly
        span_links = retrieve_span_links(linked_to_auto_dropped_span)
        assert len(span_links) == 1
        assert span_links[0]["span_id"] == auto_dropped_span["span_id"]
        # ensure autodropped span has the set sampling decision
        assert auto_dropped_span["metrics"].get(SAMPLING_PRIORITY_KEY) == 0
        # assert that sampling decision is propagated by the span link
        assert linked_to_auto_dropped_span["metrics"].get(SAMPLING_PRIORITY_KEY) == 0
