import pytest

from parametric.spec.otel_trace import OtelSpan
from parametric.spec.otel_trace import find_otel_span_in_traces


# todo: add prefix_library to run otel_*


def test_start_otel_api_tracer(test_agent, test_otel_library):
    """Test span sampling tags are added when a rule with glob patterns with special characters * and ? match"""
    with test_otel_library:
        with test_otel_library.start_otel_span(name="web.otel"):
            pass
    print(test_agent.wait_for_num_traces(1))
    span = find_otel_span_in_traces(test_agent.wait_for_num_traces(1), OtelSpan(name="web.request"))
    print(span)

    assert span.get("name") == "web.otel"
