import pytest

from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.spec.trace import find_span, find_trace, retrieve_span_links, span_has_no_parent

from .conftest import APMLibrary

# Parametric analog of tests/test_library_conf.py::Test_ExtractBehavior_*.
# Kept in sync manually - if the e2e fixtures/assertions change, check both.

DATADOG_TRACECONTEXT_BAGGAGE_HEADERS = [
    ("x-datadog-trace-id", "1"),
    ("x-datadog-parent-id", "1"),
    ("x-datadog-sampling-priority", "2"),
    ("x-datadog-tags", "_dd.p.tid=1111111111111111,_dd.p.dm=-4"),
    ("traceparent", "00-11111111111111110000000000000001-0000000000000001-01"),
    ("tracestate", "dd=s:2;t.dm:-4,foo=1"),
    ("baggage", "key1=value1"),
]

CONFLICTING_TRACECONTEXT_HEADERS = [
    ("x-datadog-trace-id", "2"),
    ("x-datadog-parent-id", "2"),
    ("x-datadog-sampling-priority", "2"),
    ("x-datadog-tags", "_dd.p.tid=1111111111111111,_dd.p.dm=-4"),
    ("traceparent", "00-12345678901234567890123456789012-1234567890123456-01"),
    ("baggage", "key1=value1"),
]

# Same conflicting traceparent as above, but with the Datadog trace id matching
# DATADOG_TRACECONTEXT_BAGGAGE_HEADERS (1) instead of 2. The e2e fixtures for
# Restart/Restart_With_Extract_First::test_multiple_tracecontexts use trace id
# 1 here (unlike Default/Ignore, which use trace id 2), since the resulting
# span link is expected to carry trace id 1.
RESTARTED_CONFLICTING_TRACECONTEXT_HEADERS = [
    ("x-datadog-trace-id", "1"),
    ("x-datadog-parent-id", "1"),
    ("x-datadog-sampling-priority", "2"),
    ("x-datadog-tags", "_dd.p.tid=1111111111111111,_dd.p.dm=-4"),
    ("traceparent", "00-12345678901234567890123456789012-1234567890123456-01"),
    ("baggage", "key1=value1"),
]

OVERRIDING_SPAN_ID_HEADERS = [
    ("x-datadog-trace-id", "1"),
    ("x-datadog-parent-id", "1"),
    ("x-datadog-sampling-priority", "2"),
    ("x-datadog-tags", "_dd.p.tid=1111111111111111,_dd.p.dm=-4"),
    ("traceparent", "00-11111111111111110000000000000001-1234567890123456-01"),
    ("baggage", "key1=value1"),
]

NONDEFAULT_EXTRACT_STYLE = "datadog,tracecontext,b3multi,baggage"


def assert_no_span_links(span: dict) -> None:
    """retrieve_span_links raises ValueError when a span carries no span links."""
    with pytest.raises(ValueError):
        retrieve_span_links(span)


def injected_headers(test_library: APMLibrary, span_id: int) -> dict[str, str]:
    return {k.lower(): v for k, v in test_library.dd_inject_headers(span_id)}


@scenarios.parametric
@features.context_propagation_extract_behavior
class Test_ExtractBehavior_Default:
    """DD_TRACE_PROPAGATION_BEHAVIOR_EXTRACT default (continue)."""

    def test_single_tracecontext(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        with (
            test_library,
            test_library.dd_extract_headers_and_make_child_span("root", DATADOG_TRACECONTEXT_BAGGAGE_HEADERS) as span,
        ):
            headers = injected_headers(test_library, int(span.get_span_id()))

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace(traces, span.get_trace_id())
        s = find_span(trace, span.get_span_id())

        # span.get_trace_id() is not standardized across parametric clients (some
        # return the full 128-bit trace id, others the low 64 bits) - compare
        # against the raw agent-reported span's trace_id instead, which is
        # always the low 64 bits per the agent wire protocol.
        assert s["trace_id"] == 1
        assert not span_has_no_parent(s)
        assert_no_span_links(s)

        assert headers["x-datadog-trace-id"] == "1"
        assert "_dd.p.tid=1111111111111111" in headers["x-datadog-tags"]
        assert "key1=value1" in headers["baggage"]

    def test_multiple_tracecontexts(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        with (
            test_library,
            test_library.dd_extract_headers_and_make_child_span("root", CONFLICTING_TRACECONTEXT_HEADERS) as span,
        ):
            headers = injected_headers(test_library, int(span.get_span_id()))

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace(traces, span.get_trace_id())
        s = find_span(trace, span.get_span_id())

        assert s["trace_id"] == 2

        span_links = retrieve_span_links(s)
        assert len(span_links) == 1
        link = span_links[0]
        assert link["trace_id"] == 8687463697196027922
        assert link["trace_id_high"] == 1311768467284833366
        assert link["span_id"] == 1311768467284833366
        assert link["attributes"] == {"reason": "terminated_context", "context_headers": "tracecontext"}

        assert headers["x-datadog-trace-id"] == "2"
        assert "_dd.p.tid=1111111111111111" in headers["x-datadog-tags"]
        assert "key1=value1" in headers["baggage"]


@scenarios.parametric
@features.context_propagation_extract_behavior
@pytest.mark.parametrize(
    "library_env",
    [
        {
            "DD_TRACE_PROPAGATION_STYLE_EXTRACT": NONDEFAULT_EXTRACT_STYLE,
            "DD_TRACE_PROPAGATION_BEHAVIOR_EXTRACT": "restart",
        }
    ],
)
class Test_ExtractBehavior_Restart:
    def test_single_tracecontext(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        with (
            test_library,
            test_library.dd_extract_headers_and_make_child_span("root", DATADOG_TRACECONTEXT_BAGGAGE_HEADERS) as span,
        ):
            headers = injected_headers(test_library, span.get_span_id())

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace(traces, span.get_trace_id())
        s = find_span(trace, span.get_span_id())

        assert s["trace_id"] != 1
        assert span_has_no_parent(s)

        span_links = retrieve_span_links(s)
        assert len(span_links) == 1
        link = span_links[0]
        assert link["trace_id"] == 1
        assert link["trace_id_high"] == 1229782938247303441
        assert link["span_id"] == 1
        assert link["attributes"] == {"reason": "propagation_behavior_extract", "context_headers": "datadog"}

        assert headers["x-datadog-trace-id"] != "1"
        assert "_dd.p.tid=1111111111111111" not in headers.get("x-datadog-tags", "")
        assert "key1=value1" in headers["baggage"]

    def test_multiple_tracecontexts(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        with (
            test_library,
            test_library.dd_extract_headers_and_make_child_span(
                "root", RESTARTED_CONFLICTING_TRACECONTEXT_HEADERS
            ) as span,
        ):
            headers = injected_headers(test_library, span.get_span_id())

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace(traces, span.get_trace_id())
        s = find_span(trace, span.get_span_id())

        assert s["trace_id"] != 1
        assert s["trace_id"] != 8687463697196027922
        assert span_has_no_parent(s)

        span_links = retrieve_span_links(s)
        assert len(span_links) == 1
        link = span_links[0]
        assert link["trace_id"] == 1
        assert link["trace_id_high"] == 1229782938247303441
        assert link["span_id"] == 1
        assert link["attributes"] == {"reason": "propagation_behavior_extract", "context_headers": "datadog"}

        assert headers["x-datadog-trace-id"] != "1"
        assert "_dd.p.tid=1111111111111111" not in headers.get("x-datadog-tags", "")
        assert "key1=value1" in headers["baggage"]

    def test_multiple_tracecontexts_with_overrides(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        with (
            test_library,
            test_library.dd_extract_headers_and_make_child_span("root", OVERRIDING_SPAN_ID_HEADERS) as span,
        ):
            headers = injected_headers(test_library, span.get_span_id())

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace(traces, span.get_trace_id())
        s = find_span(trace, span.get_span_id())

        assert s["trace_id"] != 1
        assert span_has_no_parent(s)

        span_links = retrieve_span_links(s)
        assert len(span_links) == 1
        link = span_links[0]
        assert link["trace_id"] == 1
        assert link["trace_id_high"] == 1229782938247303441
        assert link["span_id"] == 1311768467284833366
        assert link["attributes"] == {"reason": "propagation_behavior_extract", "context_headers": "datadog"}

        assert headers["x-datadog-trace-id"] != "1"
        assert "_dd.p.tid=1111111111111111" not in headers.get("x-datadog-tags", "")
        assert "key1=value1" in headers["baggage"]


@scenarios.parametric
@features.context_propagation_extract_behavior
@pytest.mark.parametrize(
    "library_env",
    [
        {
            "DD_TRACE_PROPAGATION_STYLE_EXTRACT": NONDEFAULT_EXTRACT_STYLE,
            "DD_TRACE_PROPAGATION_BEHAVIOR_EXTRACT": "ignore",
        }
    ],
)
class Test_ExtractBehavior_Ignore:
    def test_single_tracecontext(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        with (
            test_library,
            test_library.dd_extract_headers_and_make_child_span("root", DATADOG_TRACECONTEXT_BAGGAGE_HEADERS) as span,
        ):
            headers = injected_headers(test_library, span.get_span_id())

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace(traces, span.get_trace_id())
        s = find_span(trace, span.get_span_id())

        assert s["trace_id"] != 1
        assert span_has_no_parent(s)
        assert_no_span_links(s)

        assert headers["x-datadog-trace-id"] != "1"
        assert "_dd.p.tid=1111111111111111" not in headers.get("x-datadog-tags", "")
        assert "baggage" not in headers

    def test_multiple_tracecontexts(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        with (
            test_library,
            test_library.dd_extract_headers_and_make_child_span("root", CONFLICTING_TRACECONTEXT_HEADERS) as span,
        ):
            headers = injected_headers(test_library, span.get_span_id())

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace(traces, span.get_trace_id())
        s = find_span(trace, span.get_span_id())

        assert s["trace_id"] != 1
        assert s["trace_id"] != 8687463697196027922
        assert span_has_no_parent(s)
        assert_no_span_links(s)

        assert headers["x-datadog-trace-id"] != "2"
        assert "_dd.p.tid=1111111111111111" not in headers.get("x-datadog-tags", "")
        assert "baggage" not in headers


@scenarios.parametric
@features.context_propagation_extract_behavior
@pytest.mark.parametrize(
    "library_env",
    [
        {
            "DD_TRACE_PROPAGATION_STYLE_EXTRACT": NONDEFAULT_EXTRACT_STYLE,
            "DD_TRACE_PROPAGATION_BEHAVIOR_EXTRACT": "restart",
            "DD_TRACE_PROPAGATION_EXTRACT_FIRST": "true",
        }
    ],
)
class Test_ExtractBehavior_Restart_With_Extract_First:
    def test_single_tracecontext(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        with (
            test_library,
            test_library.dd_extract_headers_and_make_child_span("root", DATADOG_TRACECONTEXT_BAGGAGE_HEADERS) as span,
        ):
            headers = injected_headers(test_library, span.get_span_id())

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace(traces, span.get_trace_id())
        s = find_span(trace, span.get_span_id())

        assert s["trace_id"] != 1
        assert span_has_no_parent(s)

        span_links = retrieve_span_links(s)
        assert len(span_links) == 1
        link = span_links[0]
        assert link["trace_id"] == 1
        assert link["trace_id_high"] == 1229782938247303441
        assert link["span_id"] == 1
        assert link["attributes"] == {"reason": "propagation_behavior_extract", "context_headers": "datadog"}

        assert headers["x-datadog-trace-id"] != "1"
        assert "_dd.p.tid=1111111111111111" not in headers.get("x-datadog-tags", "")
        assert "key1=value1" in headers["baggage"]

    def test_multiple_tracecontexts(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        with (
            test_library,
            test_library.dd_extract_headers_and_make_child_span(
                "root", RESTARTED_CONFLICTING_TRACECONTEXT_HEADERS
            ) as span,
        ):
            headers = injected_headers(test_library, span.get_span_id())

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace(traces, span.get_trace_id())
        s = find_span(trace, span.get_span_id())

        assert s["trace_id"] != 1
        assert s["trace_id"] != 8687463697196027922
        assert span_has_no_parent(s)

        span_links = retrieve_span_links(s)
        assert len(span_links) == 1
        link = span_links[0]
        assert link["trace_id"] == 1
        assert link["trace_id_high"] == 1229782938247303441
        assert link["span_id"] == 1
        assert link["attributes"] == {"reason": "propagation_behavior_extract", "context_headers": "datadog"}

        assert headers["x-datadog-trace-id"] != "1"
        assert "_dd.p.tid=1111111111111111" not in headers.get("x-datadog-tags", "")
        assert "key1=value1" in headers["baggage"]
