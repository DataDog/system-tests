from typing import Any

import pytest

from utils.parametric.headers import make_single_request_and_get_inject_headers
from utils.parametric.spec.trace import ORIGIN
from utils.parametric.spec.trace import SAMPLING_PRIORITY_KEY
from utils.parametric.spec.trace import span_has_no_parent
from utils.parametric.spec.trace import find_only_span
from utils.parametric.spec.trace import retrieve_span_links, find_span, find_trace, find_span_in_traces
from utils import missing_feature, irrelevant, context, scenarios, features, bug

parametrize = pytest.mark.parametrize

def enable_extract_behavior_continue() -> Any:
    env = {
        "DD_TRACE_PROPAGATION_BEHAVIOR_EXTRACT": "continue",
    }
    return parametrize("library_env", [env])

def enable_extract_behavior_restart() -> Any:
    env = {
        "DD_TRACE_PROPAGATION_BEHAVIOR_EXTRACT": "restart",
    }
    return parametrize("library_env", [env])

def enable_extract_behavior_ignore() -> Any:
    env = {
        "DD_TRACE_PROPAGATION_BEHAVIOR_EXTRACT": "ignore",
    }
    return parametrize("library_env", [env])


@scenarios.parametric
class Test_Propagation:
    def test_propagation_extract_behavior_default(self, test_agent, test_library):
        self.test_propagation_extract_behavior_continue(test_agent, test_library)

    @enable_extract_behavior_continue()
    def test_propagation_extract_behavior_continue(self, test_agent, test_library):
        """Ensure that a new trace is started and a span link to the incoming
        span context is created.
        """
        with test_library:
            headers = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["x-datadog-trace-id", "1"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-sampling-priority", "2"],
                    ["x-datadog-origin", "synthetics"],
                    ["x-datadog-tags", "_dd.p.tid=1111111111111111,_dd.p.dm=-4"],
                ],
            )

        span = find_only_span(test_agent.wait_for_num_traces(1))
        assert span.get("trace_id") == 1
        assert span.get("parent_id") == 987654321
        assert span["meta"].get(ORIGIN) == "synthetics"
        assert span["meta"].get("_dd.p.tid") == "1111111111111111"
        assert span["meta"].get("_dd.p.dm") == "-4"
        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == 2

        assert retrieve_span_links(span) is None

    @enable_extract_behavior_restart()
    def test_propagation_extract_behavior_restart(self, test_agent, test_library):
        """Ensure that a new trace is started and a span link to the incoming
        span context is created.
        """
        with test_library:
            headers = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["x-datadog-trace-id", "1"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-sampling-priority", "2"],
                    ["x-datadog-origin", "synthetics"],
                    ["x-datadog-tags", "_dd.p.tid=1111111111111111,_dd.p.dm=-4"],
                ],
            )

        span = find_only_span(test_agent.wait_for_num_traces(1))
        assert span.get("trace_id") != 1
        assert span_has_no_parent(span)

        links = retrieve_span_links(span)
        assert len(links) == 1

        link0 = links[0]
        assert link0["trace_id"] == 1
        assert link0["span_id"] == 987654321
        assert link0["trace_id_high"] == 1229782938247303441
        # At this time we are not asserting tracestate or traceflags

    @enable_extract_behavior_ignore()
    def test_propagation_extract_behavior_ignore(self, test_agent, test_library):
        """Ensure that a new trace is started and a span link to the incoming
        span context is created.
        """
        with test_library:
            headers = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["x-datadog-trace-id", "1"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-sampling-priority", "2"],
                    ["x-datadog-origin", "synthetics"],
                    ["x-datadog-tags", "_dd.p.tid=1111111111111111,_dd.p.dm=-4"],
                ],
            )

        span = find_only_span(test_agent.wait_for_num_traces(1))
        assert span.get("trace_id") != 1
        assert span_has_no_parent(span)

        assert retrieve_span_links(span) is None
