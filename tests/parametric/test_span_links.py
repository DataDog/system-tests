import pytest

from ddapm_test_agent.trace import Span
from ddapm_test_agent.trace import Trace
from ddapm_test_agent.trace import root_span
from utils.parametric.spec.trace import SAMPLING_PRIORITY_KEY, ORIGIN
from utils.parametric.spec.trace import find_span
from utils.parametric.spec.trace import find_trace_by_root
from utils.parametric.spec.trace import span_has_no_parent
from utils.parametric.headers import make_single_request_and_get_inject_headers
from utils.parametric.test_agent import get_span
from utils import bug, context, scenarios
from utils.parametric._library_client import Link


@scenarios.parametric
class Test_Span_Links:
    def test_span_started_with_link(self, test_agent, test_library):
        """Test adding a span link created from another span.
        This tests the functionality of "create a direct link between two spans
        given two valid span (or SpanContext) objects" as specified in the RFC.
        """
        with test_library:
            with test_library.start_span("root") as parent:
                with test_library.start_span(
                    "child",
                    parent_id=parent.span_id,
                    links=[Link(parent_id=parent.span_id, attributes={"foo": "bar", "array": ["a", "b", "c"]})],
                ):
                    pass

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace_by_root(traces, Span(name="root"))
        assert len(trace) == 2

        root = root_span(trace)
        span = find_span(trace, Span(name="child"))

        assert span.get("parent_id") == root.get("span_id")
        assert span.get("span_links") is not None

        span_links = span["span_links"]
        assert len(span_links) == 1
        link = span_links[0]
        assert link.get("span_id") == root.get("span_id")
        assert link.get("trace_id") == root.get("trace_id")
        assert (link.get("trace_id_high") or 0) == 0
        assert link["attributes"].get("foo") == "bar"
        assert link["attributes"].get("array.0") == "a"
        assert link["attributes"].get("array.1") == "b"
        assert link["attributes"].get("array.2") == "c"
        assert (link.get("flags") or 0) == 0

    def test_span_link_from_distributed_datadog_headers(self, test_agent, test_library):
        """Properly inject datadog distributed tracing information into span links.
        Testing the conversion of x-datadog-* headers to tracestate for
        representation in span links.
        """
        with test_library:
            with test_library.start_span(
                "root",
                links=[Link(parent_id=0, attributes={"foo": "bar"})],
                http_headers=[
                    ["x-datadog-trace-id", "1234567890"],
                    ["x-datadog-parent-id", "9876543210"],
                    ["x-datadog-sampling-priority", "2"],
                    ["x-datadog-origin", "synthetics"],
                    ["x-datadog-tags", "_dd.p.dm=-4,_dd.p.tid=0000000000000010"],
                ],
            ):
                pass

        span = get_span(test_agent)
        assert span.get("trace_id") != 1234567890
        assert span_has_no_parent(span)
        assert span["meta"].get(ORIGIN) is None
        assert span["meta"].get("_dd.p.dm") == "-4"
        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == 2

        assert span.get("span_links") is not None

        span_links = span["span_links"]
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

    def test_span_link_from_distributed_w3c_headers(self, test_agent, test_library):
        """Properly inject w3c distributed tracing information into span links.
        This mostly tests that the injected tracestate and flags are accurate.
        """
        with test_library:
            with test_library.start_span(
                "root",
                links=[Link(parent_id=0)],
                http_headers=[
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                    ["tracestate", "foo=1,dd=t.dm:-4;s:2"],
                ],
            ):
                pass

        span = get_span(test_agent)
        assert span.get("trace_id") != 1234567890
        assert span_has_no_parent(span)
        assert span["meta"].get("_dd.p.dm") == "-4"
        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == 2

        assert span.get("span_links") is not None

        span_links = span["span_links"]
        assert len(span_links) == 1
        link = span_links[0]
        assert link.get("span_id") == 1311768467284833366
        assert link.get("trace_id") == 8687463697196027922
        assert link.get("trace_id_high") == 1311768467284833366

        assert link.get("tracestate") is not None
        tracestateArr = link["tracestate"].split(",")
        assert len(tracestateArr) == 2 and tracestateArr[0].startswith("dd=")
        assert tracestateArr[1] == "foo=1"
        tracestateDD = tracestateArr[0][3:].split(";")
        assert len(tracestateDD) == 2
        assert "s:2" in tracestateDD
        assert "t.dm:-4" in tracestateDD

        assert link.get("flags") == 1 | -2147483648
        assert len(link.get("attributes") or {}) == 0

    def test_span_with_attached_links(self, test_agent, test_library):
        """Test adding a span link from a span to another span.
        """
        with test_library:
            with test_library.start_span("root") as parent:
                with test_library.start_span("first", parent_id=parent.span_id) as first:
                    pass
                with test_library.start_span(
                    "second", parent_id=parent.span_id, links=[Link(parent_id=parent.span_id)]
                ) as second:
                    second.add_link(first.span_id, attributes={"test": "success", "nested": ["a", "be"]})

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace_by_root(traces, Span(name="root"))
        assert len(trace) == 3

        root = root_span(trace)
        first = find_span(trace, Span(name="first"))
        span = find_span(trace, Span(name="second"))

        assert span.get("parent_id") == root.get("span_id")
        assert span.get("span_links") is not None

        span_links = span["span_links"]
        assert len(span_links) == 2

        link = span_links[0]
        assert link.get("span_id") == root.get("span_id")
        assert link.get("trace_id") == root.get("trace_id")
        assert (link.get("trace_id_high") or 0) == 0
        assert len(link.get("attributes") or {}) == 0
        assert (link.get("tracestate") or "") == ""
        assert (link.get("flags") or 0) == 0

        link = span_links[1]
        assert link.get("span_id") == first.get("span_id")
        assert link.get("trace_id") == first.get("trace_id")
        assert (link.get("trace_id_high") or 0) == 0
        assert len(link.get("attributes")) == 3
        assert link["attributes"].get("test") == "success"
        assert link["attributes"].get("nested.0") == "a"
        assert link["attributes"].get("nested.1") == "be"
        assert (link.get("tracestate") or "") == ""
        assert (link.get("flags") or 0) == 0
