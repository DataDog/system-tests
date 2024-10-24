import pytest

from utils.parametric.spec.trace import find_trace
from utils.parametric.spec.trace import find_span
from utils.parametric.spec.trace import find_span_in_traces
from utils import missing_feature, irrelevant, context, scenarios, features


@scenarios.parametric
@features.parametric_endpoint_parity
class Test_DD_Parametric_Endpoints:
    @irrelevant(
        library="nodejs", reason="The service and resouce name of the child span is overidden by th parent span."
    )
    def test_start_span(self, test_agent, test_library):
        """
        Test that start_span with no arguments creates a valid span.
        """
        with test_library:
            with test_library.start_span("parent") as s1:
                pass

            with test_library.start_span("child", "myservice", "myresource", s1.span_id, "web") as s2:
                pass

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace(traces, s1.trace_id)
        assert len(trace) == 2

        parent_span = find_span(trace, s1.span_id)
        assert parent_span["name"] == "parent"
        assert parent_span["resource"] == "parent"
        assert parent_span["service"] in ["", "nodejs", "ApmTestApi"]

        child_span = find_span(trace, s2.span_id)
        assert child_span["name"] == "child"
        assert child_span["service"] == "myservice"
        assert child_span["resource"] == "myresource"
        # nodejs and dotnet libraries returns span and trace_ids as strings
        assert child_span["parent_id"] == int(s1.span_id)
        assert child_span["type"] == "web"

    def test_extract_headers(self, test_agent, test_library):
        """
        Test that extract_headers returns the correct parent_id and stored a valid SpanContext in the parametric app.
        """
        with test_library:
            parent_id = test_library.extract_headers([["x-datadog-trace-id", "1"], ["x-datadog-parent-id", "2"]])
            # nodejs library returns span and trace_ids as strings
            assert int(parent_id) == 2

            with test_library.start_span("local_root_span", parent_id=parent_id) as s1:
                pass

        traces = test_agent.wait_for_num_traces(1)
        span = find_span_in_traces(traces, s1.trace_id, s1.span_id)
        assert span["name"] == "local_root_span"
        assert span["trace_id"] == 1
        assert span["parent_id"] == 2
