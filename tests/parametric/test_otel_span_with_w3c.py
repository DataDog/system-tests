import time

import pytest

from utils.dd_constants import SpanKind
from utils.parametric.spec.trace import SAMPLING_PRIORITY_KEY, ORIGIN
from utils.parametric.spec.trace import find_only_span
from utils import missing_feature, irrelevant, context, scenarios, features

# this global mark applies to all tests in this file.
#   DD_TRACE_OTEL_ENABLED=true is required in some tracers (.NET, Python?)
#   CORECLR_ENABLE_PROFILING=1 is required in .NET to enable auto-instrumentation
pytestmark = pytest.mark.parametrize(
    "library_env", [{"DD_TRACE_OTEL_ENABLED": "true", "CORECLR_ENABLE_PROFILING": "1"}],
)


@scenarios.parametric
@features.open_tracing_api
class Test_Otel_Span_With_W3c:
    @irrelevant(context.library == "cpp", reason="library does not implement OpenTelemetry")
    @missing_feature(context.library == "python", reason="Not implemented")
    @missing_feature(context.library <= "java@1.23.0", reason="OTel resource naming implemented in 1.24.0")
    @missing_feature(context.library == "nodejs", reason="Not implemented")
    def test_otel_start_span_with_w3c(self, test_agent, test_library):
        """
        - Start/end a span with start and end options
        """
        with test_library:
            duration_us = int(2 * 1_000_000)
            start_time = int(time.time())
            with test_library.otel_start_span(
                "operation",
                span_kind=SpanKind.PRODUCER,
                timestamp=start_time,
                attributes={"start_attr_key": "start_attr_val"},
            ) as parent:
                parent.end_span(timestamp=start_time + duration_us)
        duration_ns = int(duration_us * 1_000)  # OTEL durations are microseconds, must convert to ns for dd

        root_span = find_only_span(test_agent.wait_for_num_traces(1))
        assert root_span["name"] == "producer"
        assert root_span["resource"] == "operation"
        assert root_span["meta"]["start_attr_key"] == "start_attr_val"
        assert root_span["duration"] == duration_ns
