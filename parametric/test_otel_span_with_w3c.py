import time

import pytest

from parametric.spec.otel_trace import SK_PRODUCER
from parametric.spec.trace import SAMPLING_PRIORITY_KEY, ORIGIN
from parametric.utils.test_agent import get_span
from utils import missing_feature, context, scenarios


@scenarios.parametric
class Test_Otel_Span_With_W3c:
    @missing_feature(context.library == "dotnet", reason="Not implemented")
    @missing_feature(context.library == "nodejs", reason="Not implemented")
    @missing_feature(context.library == "php", reason="Not implemented")
    @missing_feature(context.library == "ruby", reason="Not implemented")
    @missing_feature(
        context.library == "golang", reason="Remove after https://github.com/DataDog/dd-trace-go/pull/1839 is merged"
    )
    def test_otel_start_span_with_w3c(self, test_agent, test_library):
        """
            - Start/end a span with start and end options
        """
        with test_library:
            duration_us = int(2 * 1_000_000)
            start_time = int(time.time())
            with test_library.otel_start_span(
                "operation",
                span_kind=SK_PRODUCER,
                timestamp=start_time,
                attributes={"start_attr_key": "start_attr_val"},
            ) as parent:
                parent.end_span(timestamp=start_time + duration_us)
        duration_ns = int(duration_us * 1_000)  # OTEL durations are microseconds, must convert to ns for dd

        root_span = get_span(test_agent)
        assert root_span["name"] == "operation"
        assert root_span["resource"] == "operation"
        assert root_span["meta"]["start_attr_key"] == "start_attr_val"
        assert root_span["duration"] == duration_ns

    @missing_feature(context.library == "dotnet", reason="Not implemented")
    @missing_feature(context.library == "nodejs", reason="Not implemented")
    @missing_feature(context.library == "java", reason="Not implemented")
    @missing_feature(context.library == "php", reason="Not implemented")
    @missing_feature(context.library == "ruby", reason="Not implemented")
    @missing_feature(context.library == "golang", reason="BUG - waiting for 128bit work")
    def test_otel_span_with_w3c_headers(self, test_agent, test_library):
        with test_library:
            with test_library.otel_start_span(
                name="name", http_headers=[["traceparent", "00-00000000000000001111111111111111-2222222222222222-01"]],
            ) as span:
                context = span.span_context()
                assert context.get("trace_flags") == "01"
                assert context.get("trace_id") == "00000000000000001111111111111111"
                span.end_span()

        span = get_span(test_agent)
        assert span.get("trace_id") == 1229782938247303441
        assert span.get("parent_id") == 2459565876494606882
        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == 1
        assert span["meta"].get(ORIGIN) is None
