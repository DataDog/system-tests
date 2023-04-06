import time

import pytest

from parametric.spec.otel_trace import OTEL_UNSET_CODE, OTEL_ERROR_CODE, OTEL_OK_CODE
from parametric.spec.otel_trace import OtelSpan
from parametric.spec.otel_trace import SK_PRODUCER
from parametric.spec.trace import find_span
from parametric.spec.trace import find_trace_by_root
from parametric.utils.test_agent import get_span


@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.skip_library("python", "Not implemented")
@pytest.mark.skip_library("java", "Not implemented")
@pytest.mark.skip_library("php", "Not implemented")
@pytest.mark.skip_library("ruby", "Not implemented")
@pytest.mark.skip_library("golang", "Remove after https://github.com/DataDog/dd-trace-go/pull/1839 is merged")
def test_otel_start_span(test_agent, test_library):
    """
        - Start/end a span with start and end options
    """

    with test_library:
        duration: int = 6789
        start_time: int = 12345
        with test_library.otel_start_span(
            "operation",
            span_kind=SK_PRODUCER,
            timestamp=start_time,
            new_root=True,
            attributes={"start_attr_key": "start_attr_val"},
        ) as parent:
            parent.end_span(timestamp=start_time + duration)

    root_span = get_span(test_agent)
    assert root_span["name"] == "operation"
    assert root_span["resource"] == "operation"
    assert root_span["meta"]["start_attr_key"] == "start_attr_val"
    assert root_span["duration"] == duration * 1_000  # OTEL expects microseconds but we convert it to ns internally


@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.skip_library("python", "Not implemented")
@pytest.mark.skip_library("java", "Not implemented")
@pytest.mark.skip_library("php", "Not implemented")
@pytest.mark.skip_library("ruby", "Not implemented")
@pytest.mark.skip_library("golang", "Remove after https://github.com/DataDog/dd-trace-go/pull/1839 is merged")
def test_otel_set_attributes_different_types(test_agent, test_library):
    """
        - Set attributes of multiple types for an otel span
    """
    parent_start_time = int(time.time())
    with test_library:
        with test_library.otel_start_span(
            "operation", span_kind=SK_PRODUCER, timestamp=parent_start_time, new_root=True,
        ) as parent:
            parent.set_attributes({"key": ["val1", "val2"]})
            parent.set_attributes({"key2": [1]})
            parent.set_attributes({"pi": 3.14, "hi": "bye"})
            parent.end_span()
    traces = test_agent.wait_for_num_traces(1)
    trace = find_trace_by_root(traces, OtelSpan(name="operation"))
    assert len(trace) == 1

    root_span = get_span(test_agent)

    assert root_span["name"] == "operation"
    assert root_span["resource"] == "operation"
    assert "val2" in root_span["meta"]["key"]
    assert "val1" in root_span["meta"]["key"]
    assert root_span["metrics"]["key2"] == 1
    assert root_span["metrics"]["pi"] == 3.14
    assert root_span["meta"]["hi"] == "bye"


@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.skip_library("php", "Not implemented")
@pytest.mark.skip_library("python", "Not implemented")
@pytest.mark.skip_library("ruby", "Not implemented")
@pytest.mark.skip_library("java", "Not implemented")
@pytest.mark.skip_library("golang", "Remove after https://github.com/DataDog/dd-trace-go/pull/1839 is merged")
def test_otel_span_is_recording(test_agent, test_library):
    """
    Test functionality of ending a span.
        - before ending - span.is_recording() is true
        - after ending - span.is_recording() is false
    """
    with test_library:
        # start parent
        with test_library.otel_start_span(name="parent") as parent:
            assert parent.is_recording()
            parent.end_span()
            assert not parent.is_recording()


@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.skip_library("python", "Not implemented")
@pytest.mark.skip_library("java", "Not implemented")
@pytest.mark.skip_library("ruby", "Not implemented")
@pytest.mark.skip_library("php", "Not implemented")
@pytest.mark.skip_library("golang", "Remove after https://github.com/DataDog/dd-trace-go/pull/1839 is merged")
def test_otel_span_finished_end_options(test_agent, test_library):
    """
    Test functionality of ending a span with end options.
    After finishing the span, finishing the span with different end options has no effect
    """
    start_time: int = 12345
    duration: int = 6789
    with test_library:
        with test_library.otel_start_span(name="operation", timestamp=start_time) as s:
            assert s.is_recording()
            s.end_span(timestamp=start_time + duration)
            assert not s.is_recording()
            s.end_span(timestamp=start_time + duration * 2)

    s = get_span(test_agent)
    assert s.get("name") == "operation"
    assert s.get("start") == start_time * 1_000  # OTEL expects microseconds but we convert it to ns internally
    assert s.get("duration") == duration * 1_000


@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.skip_library("php", "Not implemented")
@pytest.mark.skip_library("ruby", "Not implemented")
@pytest.mark.skip_library("python", "Not implemented")
@pytest.mark.skip_library("java", "Not implemented")
@pytest.mark.skip_library("golang", "Remove after https://github.com/DataDog/dd-trace-go/pull/1839 is merged")
def test_otel_span_end(test_agent, test_library):
    """
    Test functionality of ending a span. After ending:
        - operations on that span become noop
        - child spans are still running and can be ended later
        - still possible to start child spans from parent context
    """
    with test_library:
        with test_library.otel_start_span(name="parent") as parent:
            parent.end_span()
            # setting attributes after finish has no effect
            parent.set_name("new_name")
            parent.set_attributes({"after_finish": "true"})  # should have no affect
            with test_library.otel_start_span(name="child", parent_id=parent.span_id) as child:
                child.end_span()

    trace = find_trace_by_root(test_agent.wait_for_num_traces(1), OtelSpan(name="parent"))
    assert len(trace) == 2

    parent_span = find_span(trace, OtelSpan(name="parent"))
    assert parent_span["name"] == "parent"
    assert parent_span["meta"].get("after_finish") is None

    child = find_span(trace, OtelSpan(name="child"))
    assert child["name"] == "child"
    assert child["parent_id"] == parent_span["span_id"]


@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("ruby", "Not implemented")
@pytest.mark.skip_library("php", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.skip_library("python", "Not implemented")
@pytest.mark.skip_library("java", "Not implemented")
@pytest.mark.skip_library("golang", "Remove after https://github.com/DataDog/dd-trace-go/pull/1839 is merged")
def test_otel_set_span_status_error(test_agent, test_library):
    """
        This test verifies that setting the status of a span
        behaves accordingly to the Otel API spec
        (https://opentelemetry.io/docs/reference/specification/trace/api/#set-status)
        By checking the following:
        1. attempts to set the value of `Unset` are ignored
        2. description must only be used with `Error` value

    """
    with test_library:
        with test_library.otel_start_span(name="error_span") as s:
            s.set_status(OTEL_ERROR_CODE, "error_desc")
            s.set_status(OTEL_UNSET_CODE, "unset_desc")
            s.end_span()
    s = get_span(test_agent)
    assert s.get("meta").get("error.message") == "error_desc"
    assert s.get("name") == "error_span"


@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("ruby", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.skip_library("php", "Not implemented")
@pytest.mark.skip_library("python", "Not implemented")
@pytest.mark.skip_library("java", "Not implemented")
@pytest.mark.skip_library("golang", "Remove after https://github.com/DataDog/dd-trace-go/pull/1839 is merged")
def test_otel_set_span_status_ok(test_agent, test_library):
    """
        This test verifies that setting the status of a span
        behaves accordingly to the Otel API spec
        (https://opentelemetry.io/docs/reference/specification/trace/api/#set-status)
        By checking the following:
        1. attempts to set the value of `Unset` are ignored
        3. setting the status to `Ok` is final and will override any
            prior or future status values
    """
    with test_library:
        with test_library.otel_start_span(name="ok_span") as span:
            span.set_status(OTEL_OK_CODE, "ok_desc")
            span.set_status(OTEL_ERROR_CODE, "error_desc")
            span.end_span()

    span = get_span(test_agent)
    assert span.get("meta").get("error.message") is None
    assert span.get("name") == "ok_span"


@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("ruby", "Not implemented")
@pytest.mark.skip_library("php", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.skip_library("python", "Not implemented")
@pytest.mark.skip_library("java", "Not implemented")
@pytest.mark.skip_library("golang", "Remove after https://github.com/DataDog/dd-trace-go/pull/1839 is merged")
def test_otel_get_span_context(test_agent, test_library):
    """
        This test verifies retrieving the span context of a span
        accordingly to the Otel API spec
        (https://opentelemetry.io/docs/reference/specification/trace/api/#get-context)
    """
    with test_library:
        with test_library.otel_start_span(name="operation", new_root=True) as parent:
            parent.end_span()
            with test_library.otel_start_span(name="operation", parent_id=parent.span_id, new_root=False) as span:
                span.end_span()
                context = span.span_context()
                assert context.get("trace_id") == parent.span_context().get("trace_id")
                assert context.get("span_id") == "{:016x}".format(span.span_id)
                assert context.get("trace_flags") == "01"
