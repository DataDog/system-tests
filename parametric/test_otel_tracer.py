import time
import pytest

from parametric.spec.trace import find_trace_by_root
from parametric.spec.trace import find_span_in_traces
from parametric.spec.trace import find_span
from parametric.spec.otel_trace import OtelSpan
from parametric.spec.otel_trace import OTEL_UNSET_CODE, OTEL_ERROR_CODE
from parametric.spec.otel_trace import SK_PRODUCER

# todo: add prefix_library to run otel_*


@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.skip_library("python", "Not implemented")
@pytest.mark.skip_library("java", "Not implemented")
def test_otel_span_options(test_agent, test_library):
    """
        - Start/end a span with start and end options
        - Start a tracer with options
    """
    test_library.otel_env = "otel_env"
    test_library.otel_service = "otel_serv"
    # entering test_otel_library starts the tracer with the above options
    start_time = int(time.time())
    with test_library:
        starting_attributes = {"start_attr_key": "start_attr_val"}
        with test_library.start_otel_span(
            "operation", span_kind=SK_PRODUCER, timestamp=start_time, new_root=True, attributes=starting_attributes,
        ) as parent:
            end_time = start_time + 200
            parent.finish(timestamp=end_time)

    traces = test_agent.wait_for_num_traces(1)
    trace = find_trace_by_root(traces, OtelSpan(name="operation"))
    assert len(trace) == 1

    root_span = find_span(trace, OtelSpan(name="operation"))
    assert root_span["meta"]["env"] == "otel_env"
    assert root_span["service"] == "otel_serv"
    assert root_span["name"] == "operation"
    assert root_span["resource"] == "operation"
    assert root_span["meta"]["start_attr_key"] == "start_attr_val"
    assert root_span["duration"] * (1e-9) == end_time - start_time


@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.skip_library("python", "Not implemented")
@pytest.mark.skip_library("java", "Not implemented")
def test_otel_span_methods(test_agent, test_library):
    """
        Do a simple trace to ensure span methods are working properly
            - start a child span from parent span
            - set attributes of various types
    """
    parent_start_time = int(time.time())
    with test_library:
        with test_library.start_otel_span(
            "operation", span_kind=SK_PRODUCER, timestamp=parent_start_time, new_root=True,
        ) as parent:
            parent.set_attributes({"key": ["val1", "val2"]})
            parent.set_attributes({"key2": [1]})
            parent.set_attributes({"pi": 3.14, "hi": "bye"})
            with test_library.start_otel_span(name="child", span_kind=SK_PRODUCER, parent_id=parent.span_id) as child:
                child.set_attributes({"key2": ["val2", "val3"]})
                child.set_name("operation.child")
                assert parent.span_context()["trace_id"] == child.span_context()["trace_id"]
                assert parent.span_context()["trace_flags"] == child.span_context()["trace_flags"]
                assert parent.span_context()["trace_state"] == child.span_context()["trace_state"]
                assert parent.span_context()["remote"] == child.span_context()["remote"]

    traces = test_agent.wait_for_num_traces(1)
    trace = find_trace_by_root(traces, OtelSpan(name="operation"))
    assert len(trace) == 2

    root_span = find_span(trace, OtelSpan(name="operation"))

    assert root_span["name"] == "operation"
    assert root_span["resource"] == "operation"
    assert "val2" in root_span["meta"]["key"]
    assert "val1" in root_span["meta"]["key"]
    assert root_span["metrics"]["key2"] == 1
    assert root_span["metrics"]["pi"] == 3.14
    assert root_span["meta"]["hi"] == "bye"

    child_span = find_span(trace, OtelSpan(name="operation.child"))
    assert child_span["name"] == "operation.child"
    assert "val2" in child_span["meta"]["key2"]
    assert "val3" in child_span["meta"]["key2"]


@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.skip_library("python", "Not implemented")
@pytest.mark.skip_library("java", "Not implemented")
def test_is_recording_otel(test_agent, test_library):
    with test_library:
        with test_library.start_otel_span(name="test_span") as span:
            span.set_attributes({"key": "val"})
            assert span.is_recording()
            span.finish()
            assert not span.is_recording()


@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.skip_library("python", "Not implemented")
@pytest.mark.skip_library("java", "Not implemented")
def test_force_flush_otel(test_agent, test_library):
    """verify that force flush flushed the spans"""
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


@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.skip_library("python", "Not implemented")
@pytest.mark.skip_library("java", "Not implemented")
def test_otel_span_end(test_agent, test_library):
    """
    Test functionality of ending a span. After ending:
        - operations on that span become noop
        - span.is_recording() is false
        - child spans are still running and can be ended later
        - still possible to start child spans from parent context
    """
    with test_library:
        # start parent
        with test_library.start_otel_span(name="parent") as parent:
            pid = parent.span_id
            # start first child
            with test_library.start_otel_span(name="child1", parent_id=pid) as child1:
                parent.finish()
                parent.set_name("grandparent")  # should have no affect

                # start second child after parent has been ended
                with test_library.start_otel_span(name="child2", parent_id=pid) as child2:
                    child1.set_attributes({"key": "value"})
                    child2.set_attributes({"k2": "v2"})

                    assert child1.is_recording()
                    assert child2.is_recording()
                    assert not parent.is_recording()

                    child1.finish()
                    child2.finish()

    traces = test_agent.wait_for_num_traces(1)
    trace = find_trace_by_root(traces, OtelSpan(name="parent"))
    assert len(trace) == 3

    root_span = find_span(trace, OtelSpan(name="parent"))
    assert root_span["name"] == "parent"

    c1 = find_span(trace, OtelSpan(name="child1"))
    c2 = find_span(trace, OtelSpan(name="child2"))
    assert "value" in c1["meta"]["key"]
    assert "v2" in c2["meta"]["k2"]


@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.skip_library("python", "Not implemented")
@pytest.mark.skip_library("java", "Not implemented")
def test_set_otel_span_status(test_agent, test_library):
    """want to verify set status logic is correct"""
    with test_library:
        with test_library.start_otel_span(name="test_span") as span:
            span.set_status(OTEL_ERROR_CODE, "error_desc")
            # error code > unset code, so status does not change
            span.set_status(OTEL_UNSET_CODE, "unset_desc")
    traces = test_agent.wait_for_num_traces(1)
    span = find_span_in_traces(traces, OtelSpan(name="test_span"))
    tags = span.get("meta")
    assert tags is not None
    assert tags.get("error.message") == "error_desc"
