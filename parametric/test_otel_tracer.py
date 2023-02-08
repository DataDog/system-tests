from parametric.spec.otel_trace import find_otel_span_in_traces, OtelSpan


def test_start_otel_api_span_with_set_name(test_agent, test_library):
    """Test span is created with OTel API of Datadog Tracing Library"""
    with test_library:
        with test_library.start_otel_span(name="operation", service="my-webserver", resource="/endpoint",) as parent:
            parent.set_attributes({"key": "val"})
            parent.set_name("new_op")

    span = find_otel_span_in_traces(test_agent.wait_for_num_traces(1), OtelSpan(name="web.otel"))
    assert span.get("name") == "new_op"
    assert span.get("resource") == "operation"
