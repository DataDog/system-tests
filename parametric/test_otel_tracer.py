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



def test_start_otel_api_span_with_set_name(test_agent, test_otel_library):
    """Test span is created with OTel API of Datadog Tracing Library"""
    with test_otel_library:
        with test_otel_library.start_otel_span(name="operation",
                                               service="my-webserver",
                                               resource="/endpoint",
                                               ) as parent:
            parent.set_attributes({"key": "val"})
            parent.set_name("new_op")

    span = find_otel_span_in_traces(test_agent.wait_for_num_traces(1), OtelSpan(name="web.otel"))
    assert span.get("name") == "new_op"
    assert span.get("resource") == "operation"
