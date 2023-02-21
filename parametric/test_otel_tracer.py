import pytest

from parametric.spec.trace import find_trace_by_root
from parametric.spec.trace import find_span_in_traces
from parametric.spec.trace import find_span
from parametric.spec.otel_trace import OtelSpan

# todo: add prefix_library to run otel_*


@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.skip_library("python", "Not implemented")
@pytest.mark.skip_library("java", "Not implemented")
def test_otel_simple_trace(test_agent, test_library):
    """
        Perform a simple trace that starts a parent and child span
    """
    with test_library:
        with test_library.start_otel_span("root", new_root=True,) as parent:
            parent.set_attributes({"parent_k1": "parent_v1"})
            with test_library.start_otel_span(name="child", parent_id=parent.span_id) as child:
                assert parent.span_context()["trace_id"] == child.span_context()["trace_id"]

    traces = test_agent.wait_for_num_traces(1)
    trace = find_trace_by_root(traces, OtelSpan(name="root"))
    assert len(trace) == 2

    child_span = find_span(trace, OtelSpan(name="child"))
    assert child_span["name"] == "child"


@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.skip_library("python", "Not implemented")
@pytest.mark.skip_library("java", "Not implemented")
def test_otel_force_flush(test_agent, test_library):
    """
        Verify that force flush flushed the spans
    """
    with test_library:
        with test_library.start_otel_span(name="test_span") as span:
            pass
        # force flush with 5 second time out
        flushed = test_library.flush_otel(5)
        assert flushed, "ForceFlush error"
        # check if trace is flushed
        traces = test_agent.wait_for_num_traces(1)
        span = find_span_in_traces(traces, OtelSpan(name="test_span"))
        assert span.get("name") == "test_span"
