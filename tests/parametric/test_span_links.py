import json
import pytest


from utils.parametric.spec.trace import SAMPLING_PRIORITY_KEY, ORIGIN
from utils import scenarios, missing_feature
from utils.parametric._library_client import Link


@scenarios.parametric
class Test_Span_Links:
    @pytest.mark.parametrize("library_env", [{"DD_TRACE_API_VERSION": "v0.4"}])
    def test_span_started_with_link_v04(self, test_agent, test_library):
        """Test adding a span link created from another span.
        This tests the functionality of "create a direct link between two spans
        given two valid span (or SpanContext) objects" as specified in the RFC.
        """
        with test_library:
            with test_library.start_span("first") as first:
                pass

            first_span_link = Link(
                trace_id=first.trace_id,
                span_id=first.span_id,
                attributes={"foo": "bar", "array": ["a", "b", "c"]},
                flags=1,
                tracestate="foo=bar",
            )
            with test_library.start_span(
                "second", links=[first_span_link],
            ):
                pass

        traces = test_agent.wait_for_num_traces(2)
        first_span = traces[0][0]
        second_span = traces[1][0]

        span_links = second_span["span_links"]
        assert span_links is not None

        assert len(span_links) == 1
        link = span_links[0]
        assert link["span_id"] == first.span_id
        assert link["trace_id"] == first_span["trace_id"]

        first_span_tid = first_span.get("meta", {}).get("_dd.p.tid", "0")
        assert link.get("trace_id_high", 0) == int(first_span_tid, 16)

        assert link["attributes"].get("foo") == "bar"
        assert link["attributes"].get("array.0") == "a"
        assert link["attributes"].get("array.1") == "b"
        assert link["attributes"].get("array.2") == "c"

        assert link.get("flags") == 1
        assert link.get("tracestate") == "foo=bar"

    @missing_feature(library="python", reason="test not implemented")
    def test_span_link_from_distributed_datadog_headers(self, test_agent, test_library):
        """Properly inject datadog distributed tracing information into span links.
        Testing the conversion of x-datadog-* headers to tracestate for
        representation in span links.
        """
        with test_library:
            with test_library.start_span("parent") as parent:
                pass

                with test_library.start_span(
                    "child_span",
                    parent_id=parent.span_id,
                    http_headers=[  # http headers should be set as a span link
                        ["x-datadog-trace-id", "1234567890"],
                        ["x-datadog-parent-id", "9876543210"],
                        ["x-datadog-sampling-priority", "2"],
                        ["x-datadog-origin", "synthetics"],
                        ["x-datadog-tags", "_dd.p.dm=-4,_dd.p.tid=0000000000000010"],
                    ],
                ):
                    pass

        traces = test_agent.wait_for_num_traces(1)
        child_span = traces[0][1]
        assert child_span.get("trace_id") != 1234567890
        assert child_span["meta"].get(ORIGIN) is None
        assert child_span["meta"].get("_dd.p.dm") == "-4"
        assert child_span["metrics"].get(SAMPLING_PRIORITY_KEY) == 2

        assert child_span.get("span_links") is not None

        span_links = child_span["span_links"]
        assert len(span_links) == 1
        link = span_links[0]
        assert link.get("span_id") == 9876543210
        assert link.get("trace_id") == 1234567890
        assert link.get("trace_id_high") == 16

        assert link.get("tracestate") is not None
        tracestateArr = link["tracestate"].split(",")
        assert len(tracestateArr) == 1 and tracestateArr[0].startswith("dd=")
        tracestateDD = tracestateArr[0][3:].split(";")
        assert len(tracestateDD) == 3
        assert "o:synthetics" in tracestateDD
        assert "s:2" in tracestateDD
        assert "t.dm:-4" in tracestateDD

        assert (link.get("flags") or 0) == 0
        assert len(link.get("attributes")) == 1
        assert link["attributes"].get("foo") == "bar"

    @missing_feature(library="python", reason="test not implemented")
    def test_span_link_from_distributed_w3c_headers(self, test_agent, test_library):
        """Properly inject w3c distributed tracing information into span links.
        This mostly tests that the injected tracestate and flags are accurate.
        """
        with test_library:
            with test_library.start_span("parent_span",) as parent:
                with test_library.start_span(
                    name="child_with_links",
                    parent_id=parent.span_id,
                    http_headers=[  # http headers should be set as a span link
                        ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                        ["tracestate", "foo=1,dd=t.dm:-4;s:2,bar=baz"],
                    ],
                ):
                    pass

        traces = test_agent.wait_for_num_traces(1)
        child_span = traces[0][1]
        assert child_span.get("trace_id") != 1234567890
        assert child_span["meta"].get("_dd.p.dm") == "-4"
        assert child_span["metrics"].get(SAMPLING_PRIORITY_KEY) == 2

        assert child_span.get("span_links") is not None

        span_links = child_span["span_links"]
        assert len(span_links) == 1
        link = span_links[0]
        assert link.get("span_id") == 1311768467284833366
        assert link.get("trace_id") == 8687463697196027922
        assert link.get("trace_id_high") == 1311768467284833366

        assert link.get("tracestate") is not None
        tracestateArr = link["tracestate"].split(",")
        assert len(tracestateArr) == 3
        dd_num = 0 if tracestateArr[0].startswith("dd=") else 1
        other_num = 0 if dd_num == 1 else 1
        assert tracestateArr[other_num] == "foo=1"
        assert tracestateArr[2] == "bar=baz"
        tracestateDD = tracestateArr[dd_num][3:].split(";")
        assert len(tracestateDD) == 2
        assert "s:2" in tracestateDD
        assert "t.dm:-4" in tracestateDD

        assert link.get("flags") == 1 | -2147483648
        assert len(link.get("attributes") or {}) == 0

    @pytest.mark.parametrize("library_env", [{"DD_TRACE_API_VERSION": "v0.4"}])
    def test_span_with_attached_links_v04(self, test_agent, test_library):
        """Test adding a span link from a span to another span.
        """
        with test_library:
            with test_library.start_span("first") as first:
                pass

            with test_library.start_span("second") as second:
                pass

            with test_library.start_span("third_with_links") as third:
                third.add_link(trace_id=first.trace_id, span_id=first.span_id)
                third.add_link(
                    trace_id=second.trace_id,
                    span_id=second.span_id,
                    attributes={"bools": [True, False], "nested": [1, 2]},
                )

        traces = test_agent.wait_for_num_traces(3)
        first_span = traces[0][0]
        second_span = traces[1][0]
        third_span = traces[2][0]
        assert first_span["name"] == "first"
        assert second_span["name"] == "second"
        assert third_span["name"] == "third_with_links"

        span_links = third_span["span_links"]
        assert len(span_links) == 2

        link = span_links[0]
        assert link.get("span_id") == first_span.get("span_id")
        assert link.get("trace_id") == first_span.get("trace_id")
        first_tid = first_span.get("meta", {}).get("_dd.p.tid") or "0"
        assert (link.get("trace_id_high") or 0) == int(first_tid, 16)
        assert len(link.get("attributes") or {}) == 0
        assert (link.get("tracestate") or "") == ""
        assert (link.get("flags") or 0) == 0

        link = span_links[1]
        assert link.get("span_id") == second_span.get("span_id")
        assert link.get("trace_id") == second_span.get("trace_id")
        second_tid = second_span.get("meta", {}).get("_dd.p.tid") or "0"
        assert (link.get("trace_id_high") or 0) == int(second_tid, 16)
        assert len(link.get("attributes")) == 4
        assert link["attributes"].get("bools.0") == "true"
        assert link["attributes"].get("bools.1") == "false"
        assert link["attributes"].get("nested.0") == "1"
        assert link["attributes"].get("nested.1") == "2"
        assert (link.get("tracestate") or "") == ""
        assert (link.get("flags") or 0) == 0

    @pytest.mark.parametrize("library_env", [{"DD_TRACE_API_VERSION": "v0.5"}])
    def test_span_with_attached_links_v05(self, test_agent, test_library):
        """Test adding a span link from a span to another span.
        """
        with test_library:
            with test_library.start_span("first") as first:
                pass

            with test_library.start_span("second") as second:
                pass

            with test_library.start_span("third_with_links") as third:
                third.add_link(trace_id=first.trace_id, span_id=first.span_id)
                third.add_link(
                    trace_id=second.trace_id,
                    span_id=second.span_id,
                    attributes={"bools": [True, False], "nested": [1, 2]},
                )

        traces = test_agent.wait_for_num_traces(3)
        first_span = traces[0][0]
        second_span = traces[1][0]
        third_span = traces[2][0]
        assert first_span["name"] == "first"
        assert second_span["name"] == "second"
        assert third_span["name"] == "third_with_links"

        span_links = json.loads(third_span.get("meta", {}).get("_dd.span_links"))
        assert len(span_links) == 2

        link = span_links[0]
        first_tid = first_span.get("meta", {}).get("_dd.p.tid") or "0000000000000000"
        first_t64 = "{:016x}".format(first_span["trace_id"])
        assert link.get("trace_id") == f"{first_tid}{first_t64}"
        assert link.get("span_id") == "{:016x}".format(first_span["span_id"])
        assert len(link.get("attributes") or {}) == 0
        assert (link.get("tracestate") or "") == ""
        assert (link.get("flags") or 0) == 0

        link = span_links[1]
        second_tid = second_span.get("meta", {}).get("_dd.p.tid") or "0000000000000000"
        second_t64 = "{:016x}".format(second_span["trace_id"])
        assert link.get("trace_id") == f"{second_tid}{second_t64}"
        assert link.get("span_id") == "{:016x}".format(second_span["span_id"])
        assert len(link.get("attributes")) == 4
        assert link["attributes"].get("bools.0") == "true"
        assert link["attributes"].get("bools.1") == "false"
        assert link["attributes"].get("nested.0") == "1"
        assert link["attributes"].get("nested.1") == "2"
        assert (link.get("tracestate") or "") == ""
        assert (link.get("flags") or 0) == 0
