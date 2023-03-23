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
        Perform two traces
    """
    with test_library:
        with test_library.start_otel_span("root_one", new_root=True,) as parent:
            parent.set_attributes({"parent_k1": "parent_v1"})
            with test_library.start_otel_span(name="child", parent_id=parent.span_id) as child:
                assert parent.span_context()["trace_id"] == child.span_context()["trace_id"]
                child.otel_end_span()
            parent.otel_end_span()
        with test_library.start_otel_span("root_two", new_root=True) as parent:
            with test_library.start_otel_span(name="child", parent_id=parent.span_id) as child:
                assert parent.span_context()["trace_id"] == child.span_context()["trace_id"]
                child.otel_end_span()
            parent.otel_end_span()

    traces = test_agent.wait_for_num_traces(2)
    trace_one = find_trace_by_root(traces, OtelSpan(name="root_one"))
    assert len(trace_one) == 2

    root_span = find_span(trace_one, OtelSpan(name="root_one"))
    assert root_span["name"] == "root_one"
    assert root_span["meta"]["parent_k1"] == "parent_v1"

    child_span = find_span(trace_one, OtelSpan(name="child"))
    assert child_span["name"] == "child"

    trace_two = find_trace_by_root(traces, OtelSpan(name="root_two"))
    assert len(trace_two) == 2

    root_span = find_span(trace_two, OtelSpan(name="root_two"))
    assert root_span["name"] == "root_two"

    child_span = find_span(trace_one, OtelSpan(name="child"))
    assert child_span["name"] == "child"


@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.skip_library("python", "Not implemented")
@pytest.mark.skip_library("java", "Not implemented")
def test_force_flush_otel(test_agent, test_library):
    """
        Verify that force flush flushed the spans
    """
    with test_library:
        with test_library.start_otel_span(name="test_span") as span:
            span.otel_end_span()
        # force flush with 5 second time out
        flushed = test_library.flush_otel(5)
        assert flushed, "ForceFlush error"
        # check if trace is flushed
        traces = test_agent.wait_for_num_traces(1)
        span = find_span_in_traces(traces, OtelSpan(name="test_span"))
        assert span.get("name") == "test_span"
