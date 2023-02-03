from parametric.spec.trace import find_trace_by_root
from parametric.spec.trace import find_span_in_traces
from parametric.spec.trace import find_span
from parametric.spec.otel_trace import OtelSpan
import time

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
OTEL_UNSET_CODE = "UNSET"
OTEL_ERROR_CODE = "ERROR"
OTEL_OK_CODE = "OK"

SK_UNSPECIFIED = 0
SK_INTERNAL = 1
SK_SERVER = 2
SK_CLIENT = 3
SK_PRODUCER = 4
SK_CONSUMER = 5


def test_otel_span_top_level_attributes(test_agent, test_otel_library):
    """Do a simple trace to ensure that the test client is working properly.
        - start parent span and child span
        - set attributes
    """
    with test_otel_library:
        with test_otel_library.start_otel_span(
            "operation", span_kind=SK_PRODUCER, timestamp=int(time.time()), new_root=True, attributes={"zoowee": "mama"}
        ) as parent:
            parent.set_attributes({"key": "val"})

            with test_otel_library.start_otel_span(
                name="child", span_kind=SK_PRODUCER, timestamp=int(time.time()), parent_id=parent.span_id
            ) as child:

                child.set_attributes({"key2": "val2"})
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
    assert root_span["meta"]["key"] == "val"
    assert root_span["meta"]["zoowee"] == "mama"
    child_span = find_span(trace, OtelSpan(name="operation.child"))
    assert child_span["name"] == "operation.child"
    assert child_span["meta"]["key2"] == "val2"


# def test_start_otel_tracer(test_agent, test_otel_library):
#     """start tracer with various options, verify those options are set"""
#     pass

# def test_end_otel_span(test_agent, test_otel_library):
#     """want to verify that span operations become noop after end"""
#     pass


def test_is_recording_otel(test_agent, test_otel_library):
    with test_otel_library:
        with test_otel_library.start_otel_span(name="test_span") as span:
            span.set_attributes({"key": "val"})
            assert span.is_recording()
            span.finish()
            assert not span.is_recording()


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


def test_set_otel_span_status(test_agent, test_otel_library):
    """want to verify set status logic is correct"""
    with test_otel_library:
        with test_otel_library.start_otel_span(name="test_span") as span:
            span.set_status(OTEL_ERROR_CODE, "error_desc")
            span.set_status(OTEL_UNSET_CODE, "unset_desc")
    traces = test_agent.wait_for_num_traces(1)
    span = find_span_in_traces(traces, OtelSpan(name="test_span"))
    tags = span.get("meta")
    assert tags is not None
    assert tags.get("error.message") == "error_desc"


# def test_start_otel_api_span_with_set_name(test_agent, test_otel_library):
#     """Test span is created with OTel API of Datadog Tracing Library"""
#     with test_otel_library:
#         with test_otel_library.start_otel_span(
#             name="operation"
#         ) as parent:
#             parent.set_attributes({"key": "val"})
#             parent.set_name("new_op")

#     span = find_span_in_traces(test_agent.wait_for_num_traces(1), OtelSpan(name="web.otel"))
#     assert span.get("name") == "new_op"
#     assert span.get("resource") == "operation"
