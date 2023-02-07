import time
import pytest

from parametric.spec.trace import find_trace_by_root
from parametric.spec.trace import find_span_in_traces
from parametric.spec.trace import find_span
from parametric.spec.otel_trace import OtelSpan

# todo: add prefix_library to run otel_*

OTEL_UNSET_CODE = "UNSET"
OTEL_ERROR_CODE = "ERROR"
OTEL_OK_CODE = "OK"

SK_UNSPECIFIED = 0
SK_INTERNAL = 1
SK_SERVER = 2
SK_CLIENT = 3
SK_PRODUCER = 4
SK_CONSUMER = 5

@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("golang", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.skip_library("python", "Not implemented")
@pytest.mark.skip_library("java", "Not implemented")
def test_otel_span_top_level_attributes(test_agent, test_otel_library):
    """Do a simple trace to ensure that the test client is working properly.
        - start tracer with tracer options
        - start parent span and child span
        - set attributes
    """
    test_otel_library.service = "test_service"
    test_otel_library.env = "test_env"

    # entering test_otel_library starts the tracer with the above options
    with test_otel_library:
        with test_otel_library.start_otel_span(
            "operation", span_kind=SK_PRODUCER, timestamp=int(time.time()), new_root=True
        ) as parent:
            parent.set_attributes({"key": ["val1", "val2"]})
            parent.set_attributes({"key2": [1]})
            parent.set_attributes({"pi": 3.14, "hi": "bye"})

            with test_otel_library.start_otel_span(
                name="child", span_kind=SK_PRODUCER, timestamp=int(time.time()), parent_id=parent.span_id
            ) as child:
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
    assert root_span["service"] == "test_service"
    assert root_span["meta"]["env"] == "test_env"

    assert "val2" in root_span["meta"]["key"]
    assert "val1" in root_span["meta"]["key"]
    assert "1" in root_span["meta"]["key2"]
    assert "3.14" in root_span["meta"]["pi"]
    assert "bye" in root_span["meta"]["hi"]

    child_span = find_span(trace, OtelSpan(name="operation.child"))
    assert child_span["name"] == "operation.child"
    assert "val2" in child_span["meta"]["key2"]
    assert "val3" in child_span["meta"]["key2"]

@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("golang", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.skip_library("python", "Not implemented")
@pytest.mark.skip_library("java", "Not implemented")
def test_is_recording_otel(test_agent, test_otel_library):
    with test_otel_library:
        with test_otel_library.start_otel_span(name="test_span") as span:
            span.set_attributes({"key": "val"})
            assert span.is_recording()
            span.finish()
            assert not span.is_recording()

@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("golang", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.skip_library("python", "Not implemented")
@pytest.mark.skip_library("java", "Not implemented")
def test_force_flush_otel(test_agent, test_otel_library):
    """verify that force flush flushed the spans"""
    with test_otel_library:
        with test_otel_library.start_otel_span(name="test_span") as span:
            pass
        # force flush with 5 second time out
        flushed = test_otel_library.force_flush(1)
        assert flushed, "ForceFlush error"
        # check if trace is flushed
        traces = test_agent.wait_for_num_traces(1)
        span = find_span_in_traces(traces, OtelSpan(name="test_span"))
        assert span.get("name") == "test_span"

@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("golang", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.skip_library("python", "Not implemented")
@pytest.mark.skip_library("java", "Not implemented")
def test_otel_span_end(test_agent, test_otel_library):
    """
    Test functionality of ending a span. After ending:
        - operations on that span become noop
        - span.is_recording() is false
        - child spans are still running and can be ended later
        - still possible to start child spans from parent context
    """
    with test_otel_library:
        # start parent
        with test_otel_library.start_otel_span(name="parent") as parent:
            pid = parent.span_id
            # start first child
            with test_otel_library.start_otel_span(name="child1", parent_id=pid) as child1:
                parent.finish()
                parent.set_name("grandparent")  # should have no affect

                # start second child after parent has been ended
                with test_otel_library.start_otel_span(name="child2", parent_id=pid) as child2:
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
@pytest.mark.skip_library("golang", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.skip_library("python", "Not implemented")
@pytest.mark.skip_library("java", "Not implemented")
def test_set_otel_span_status(test_agent, test_otel_library):
    """want to verify set status logic is correct"""
    with test_otel_library:
        with test_otel_library.start_otel_span(name="test_span") as span:
            span.set_status(OTEL_ERROR_CODE, "error_desc")
            # error code > unset code, so status does not change
            span.set_status(OTEL_UNSET_CODE, "unset_desc")
    traces = test_agent.wait_for_num_traces(1)
    span = find_span_in_traces(traces, OtelSpan(name="test_span"))
    tags = span.get("meta")
    assert tags is not None
    assert tags.get("error.message") == "error_desc"
