import json
import pytest

from ddapm_test_agent.trace import Span
from ddapm_test_agent.trace import root_span
from utils.parametric.spec.trace import SAMPLING_PRIORITY_KEY, ORIGIN
from utils.parametric.spec.trace import find_span
from utils.parametric.spec.trace import find_trace_by_root
from utils.parametric.spec.trace import span_has_no_parent
from utils import context, scenarios, missing_feature, bug
from utils.parametric._library_client import Link


@scenarios.parametric
class Test_Span_Links:
    @staticmethod
    def _get_span_links(span):
        if span.get("span_links"):
            # trace API v0.4
            return span["span_links"]
        # trace API v0.5
        encoded_span_links = span.get("meta", {}).get("_dd.span_links")
        if not encoded_span_links:
            return None

        span_links = json.loads(encoded_span_links)
        # convert v0.5 SpanLinks trace IDs to the v0.4 format. This will simplify tests
        for link in span_links:
            tid_high = int(link["trace_id"][:16], 16)
            if tid_high:
                link["trace_id_high"] = tid_high
            link["trace_id"] = int(link["trace_id"][16:], 16)
            link["span_id"] = int(link["span_id"], 16)
        return span_links

    @pytest.mark.parametrize("library_env", [{"DD_TRACE_API_VERSION": "v0.5"}, {"DD_TRACE_API_VERSION": "v0.4"}])
    def test_span_started_with_link(self, test_agent, test_library):
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
        root = traces[0][0]
        span = traces[1][0]

        span_links = self._get_span_links(span)
        assert span_links is not None

        assert len(span_links) == 1
        link = span_links[0]
        assert link["span_id"] == first.span_id
        assert link["trace_id"] == root["trace_id"]

        root_tid = root.get("meta", {}).get("_dd.p.tid", "0")
        assert link.get("trace_id_high", 0) == int(root_tid, 16)

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
            with test_library.start_span("first") as first:
                pass

                with test_library.start_span(
                    "remote_span",
                    http_headers=[
                        ["x-datadog-trace-id", "1234567890"],
                        ["x-datadog-parent-id", "9876543210"],
                        ["x-datadog-sampling-priority", "2"],
                        ["x-datadog-origin", "synthetics"],
                        ["x-datadog-tags", "_dd.p.dm=-4,_dd.p.tid=0000000000000010"],
                    ],
                ):
                    pass

                with test_library.start_span("second") as second:
                    pass

        traces = test_agent.wait_for_num_traces(1)

        span = traces[0][2]
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

    @missing_feature(library="python", reason="test not implemented")
    def test_span_link_from_distributed_w3c_headers(self, test_agent, test_library):
        """Properly inject w3c distributed tracing information into span links.
        This mostly tests that the injected tracestate and flags are accurate.
        """
        with test_library:
            with test_library.start_span(
                "root",
                http_headers=[
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                    ["tracestate", "foo=1,dd=t.dm:-4;s:2,bar=baz"],
                ],
            ):
                pass

            with test_library.start_span("span"):
                pass

        traces = test_agent.wait_for_num_traces(2)
        root = traces[0][0]
        span = traces[1][0]
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

    #
    @pytest.mark.parametrize("library_env", [{"DD_TRACE_API_VERSION": "v0.5"}, {"DD_TRACE_API_VERSION": "v0.4"}])
    def test_span_with_attached_links(self, test_agent, test_library):
        """Test adding a span link from a span to another span.
        """
        with test_library:
            with test_library.start_span("root") as parent:
                with test_library.start_span("first", parent_id=parent.span_id) as first:
                    pass

            with test_library.start_span("second") as second:
                second.add_link(trace_id=parent.trace_id, span_id=parent.span_id)
                second.add_link(
                    trace_id=first.trace_id,
                    span_id=first.span_id,
                    attributes={"bools": [True, False], "nested": [1, 2]},
                )

        traces = test_agent.wait_for_num_traces(2)
        print(f"ggg {traces}")
        assert len(traces[0]) == 2
        assert len(traces[1]) == 1

        root = traces[0][0]
        root_tid = root["meta"].get("_dd.p.tid") or "0" if "meta" in root else "0"
        first = traces[0][1]

        span = traces[1][0]

        span_links = self._get_span_links(span)
        assert len(span_links) == 2

        link = span_links[0]
        assert link.get("span_id") == root.get("span_id")
        assert link.get("trace_id") == root.get("trace_id")
        assert (link.get("trace_id_high") or 0) == int(root_tid, 16)
        assert len(link.get("attributes") or {}) == 0
        assert (link.get("tracestate") or "") == ""
        assert (link.get("flags") or 0) == 0

        link = span_links[1]
        assert link.get("span_id") == first.get("span_id")
        assert link.get("trace_id") == first.get("trace_id")
        assert (link.get("trace_id_high") or 0) == int(root_tid, 16)
        assert len(link.get("attributes")) == 4
        assert link["attributes"].get("bools.0") == "True"
        assert link["attributes"].get("bools.1") == "False"
        assert link["attributes"].get("nested.0") == "1"
        assert link["attributes"].get("nested.1") == "2"
        assert (link.get("tracestate") or "") == ""
        assert (link.get("flags") or 0) == 0
