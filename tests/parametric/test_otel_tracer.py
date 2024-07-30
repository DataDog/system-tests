import pytest

from utils.parametric.spec.trace import find_trace_by_root
from utils.parametric.spec.trace import find_span_in_traces
from utils.parametric.spec.trace import find_span
from utils.parametric.spec.otel_trace import OtelSpan
from utils import missing_feature, irrelevant, context, scenarios, features, bug

# this global mark applies to all tests in this file.
#   DD_TRACE_OTEL_ENABLED=true is required in some tracers (.NET, Python?)
#   CORECLR_ENABLE_PROFILING=1 is required in .NET to enable auto-instrumentation
pytestmark = pytest.mark.parametrize(
    "library_env", [{"DD_TRACE_OTEL_ENABLED": "true", "CORECLR_ENABLE_PROFILING": "1"}],
)


@scenarios.parametric
@features.open_tracing_api
@bug(context.library >= "python@2.9.3", reason="APMAPI-180")
class Test_Otel_Tracer:
    @irrelevant(context.library == "cpp", reason="library does not implement OpenTelemetry")
    def test_otel_simple_trace(self, test_agent, test_library):
        """
        Perform two traces
        """
        with test_library:
            with test_library.otel_start_span("root_one") as parent:
                parent.set_attributes({"parent_k1": "parent_v1"})
                with test_library.otel_start_span(name="child", parent_id=parent.span_id) as child:
                    assert parent.span_context()["trace_id"] == child.span_context()["trace_id"]
                    child.end_span()
                parent.end_span()
            with test_library.otel_start_span("root_two") as parent:
                with test_library.otel_start_span(name="child", parent_id=parent.span_id) as child:
                    assert parent.span_context()["trace_id"] == child.span_context()["trace_id"]
                    child.end_span()
                parent.end_span()

        traces = test_agent.wait_for_num_traces(2)
        trace_one = find_trace_by_root(traces, OtelSpan(resource="root_one"))
        assert len(trace_one) == 2

        root_span = find_span(trace_one, OtelSpan(resource="root_one"))
        assert root_span["resource"] == "root_one"
        assert root_span["meta"]["parent_k1"] == "parent_v1"

        child_span = find_span(trace_one, OtelSpan(resource="child"))
        assert child_span["resource"] == "child"

        trace_two = find_trace_by_root(traces, OtelSpan(resource="root_two"))
        assert len(trace_two) == 2

        root_span = find_span(trace_two, OtelSpan(resource="root_two"))
        assert root_span["resource"] == "root_two"

        child_span = find_span(trace_one, OtelSpan(resource="child"))
        assert child_span["resource"] == "child"

    @irrelevant(context.library == "cpp", reason="library does not implement OpenTelemetry")
    @missing_feature(context.library <= "java@1.23.0", reason="OTel resource naming implemented in 1.24.0")
    @missing_feature(context.library == "nodejs", reason="Not implemented")
    @missing_feature(
        context.library == "ruby", reason="Ruby is instrumenting telemetry calls, creating 2 spans instead of 1"
    )
    def test_otel_force_flush(self, test_agent, test_library):
        """
        Verify that force flush flushed the spans
        """
        with test_library:
            with test_library.otel_start_span(name="test_span") as span:
                span.end_span()
            # force flush with 5 second time out
            flushed = test_library.otel_flush(5)
            assert flushed, "ForceFlush error"
            # check if trace is flushed
            traces = test_agent.wait_for_num_traces(1)
            span = find_span_in_traces(traces, OtelSpan(resource="test_span"))
            assert span.get("name") == "internal"
