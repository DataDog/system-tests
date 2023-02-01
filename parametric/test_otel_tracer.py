import pytest

from parametric.spec.otel_trace import find_otel_span_in_traces, OtelSpan

# todo: add prefix_library to run otel_*
# @pytest.mark.skip_library("golang", "parent context can't be passed")
# def test_tracer_span_top_level_attributes(test_agent, test_otel_library):
#     """Do a simple trace to ensure that the test client is working properly."""
#     with test_otel_library:
#         with test_otel_library.start_otel_span(name="operation",
#                                                service="my-webserver",
#                                                resource="/endpoint",
#                                                ) as parent:
#             parent.set_attributes({"key": "val"})
#             with test_otel_library.start_otel_span("operation.child", parent_id=parent.span_id) as child:
#                 child.set_attributes({"key": "val"})
#
#     traces = test_agent.wait_for_num_traces(1)
#     trace = find_trace_by_root(traces, Span(name="operation"))
#     assert len(trace) == 2
#
#     root_span = find_span_in_traces(trace, Span(name="operation"))
#     assert root_span["name"] == "operation"
#     assert root_span["service"] == "my-webserver"
#     assert root_span["resource"] == "/endpoint"
#     assert root_span["type"] == "web"
#     assert root_span["metrics"]["number"] == 10
#     child_span = find_span_in_traces(trace, Span(name="operation.child"))
#     assert child_span["name"] == "operation.child"
#     assert child_span["meta"]["key"] == "val"

OTEL_UNSET_CODE="UNSET"
OTEL_ERROR_CODE="ERROR"
OTEL_OK_CODE="OK"

def test_otel_span_top_level_attributes(test_agent, test_otel_library):
    """Do a simple trace to ensure that the test client is working properly."""
    with test_otel_library:
        with test_otel_library.start_otel_span(
            name="operation", service="my-webserver", resource="/endpoint"
        ) as parent:
            parent.set_attributes({"key": "val"})
            with test_otel_library.start_otel_span(name="hello", parent_id=parent.span_id) as child:
                child.set_attributes({"key2": "val2"})

    # test agent recieves two different traces
    traces = test_agent.wait_for_num_traces(2)
    parent = find_otel_span_in_traces(traces, OtelSpan(name="operation"))
    child = find_otel_span_in_traces(traces, OtelSpan(name="hello"))

    assert parent.get("name") == "operation"
    # child name is "operation"
    # assert child.get("name") == "hello"

    tags = parent.get("meta")
    assert tags is not None
    assert tags.get("key") == "val"
    # assert child.get("meta").get("key2") == "val2"
    # assert parent.get("service") == "my-webserver"
    # assert parent.get("resource") == "/endpoint"
    # assert child.get("parent_id") == parent.get("span_id")

# def test_start_otel_tracer(test_agent, test_otel_library):
#     """start tracer with various options, verify those options are set"""
#     pass

# def test_end_otel_span(test_agent, test_otel_library):
#     """want to verify that span operations become noop after end"""
#     pass
def test_span_context_otel(test_agent, test_otel_library):
    with test_otel_library:
        with test_otel_library.start_otel_span(name="test_span") as span:
            span_ctx = span.span_context()
    # TODO

def test_is_recording_otel(test_agent, test_otel_library):
    with test_otel_library:
        with test_otel_library.start_otel_span(name="test_span") as span:
            span.set_attributes({"key": "val"})
            assert span.is_recording()
            span.finish()
            assert not span.is_recording()

def test_force_flush_otel(test_agent, test_otel_library):
    """verify that force flush flushed the spans"""
    # plan: start a bunch of spans, call flush
    # before the with statement ends -- wait_for_num_traces
    with test_otel_library:
        with test_otel_library.start_otel_span(name="test_span") as span:
            pass
        # force flush with 5 second time out
        flushed = test_otel_library.force_flush(1)
        assert flushed, "ForceFlush error"
        # check if trace is flushed
        traces = test_agent.wait_for_num_traces(1)
        span = find_otel_span_in_traces(traces, OtelSpan(name="test_span"))
        assert span.get("name") == "test_span"

def test_set_otel_span_status(test_agent, test_otel_library):
    """want to verify set status logic is correct"""
    with test_otel_library:
        with test_otel_library.start_otel_span(name="test_span") as span:
            span.set_status(OTEL_ERROR_CODE, "error_desc")
            span.set_status(OTEL_UNSET_CODE, "unset_desc")
    traces = test_agent.wait_for_num_traces(1)
    span = find_otel_span_in_traces(traces, OtelSpan(name="test_span"))
    tags = span.get("meta")
    assert tags is not None
    assert tags.get("error.message") == "error_desc"

def test_start_otel_api_span_with_set_name(test_agent, test_otel_library):
    """Test span is created with OTel API of Datadog Tracing Library"""
    with test_otel_library:
        with test_otel_library.start_otel_span(name="operation",
                                               service="my-webserver",
                                               resource="/endpoint"
                                               ) as parent:
            parent.set_attributes({"key": "val"})
            parent.set_name("new_op")

    span = find_otel_span_in_traces(test_agent.wait_for_num_traces(1), OtelSpan(name="web.otel"))
    assert span.get("name") == "new_op"
    assert span.get("resource") == "operation"