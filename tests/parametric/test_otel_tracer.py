import pytest

from utils.parametric.spec.trace import find_trace
from utils.parametric.spec.trace import find_span
from utils import missing_feature, irrelevant, context, scenarios, features
from utils.docker_fixtures import TestAgentAPI
from .conftest import APMLibrary

# this global mark applies to all tests in this file.
#   DD_TRACE_OTEL_ENABLED=true is required in some tracers (.NET, Python?)
#   CORECLR_ENABLE_PROFILING=1 is required in .NET to enable auto-instrumentation
pytestmark = pytest.mark.parametrize(
    "library_env", [{"DD_TRACE_OTEL_ENABLED": "true", "CORECLR_ENABLE_PROFILING": "1"}]
)


@scenarios.parametric
@features.open_tracing_api
class Test_Otel_Tracer:
    @irrelevant(context.library == "cpp", reason="library does not implement OpenTelemetry")
    def test_otel_simple_trace(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Perform two traces"""
        with test_library:
            with test_library.otel_start_span("root_one") as parent1:
                parent1.set_attributes({"parent_k1": "parent_v1"})
                with test_library.otel_start_span(name="child1", parent_id=parent1.span_id) as child1:
                    assert parent1.span_context()["trace_id"] == child1.span_context()["trace_id"]

            with (
                test_library.otel_start_span("root_two") as parent2,
                test_library.otel_start_span(name="child2", parent_id=parent2.span_id) as child2,
            ):
                assert parent2.span_context()["trace_id"] == child2.span_context()["trace_id"]

        traces = test_agent.wait_for_num_traces(2)
        trace_one = find_trace(traces, parent1.trace_id)
        assert len(trace_one) == 2

        root_span1 = find_span(trace_one, parent1.span_id)
        assert root_span1["resource"] == "root_one"
        assert root_span1["meta"]["parent_k1"] == "parent_v1"

        child_span1 = find_span(trace_one, child1.span_id)
        assert child_span1["resource"] == "child1"

        trace_two = find_trace(traces, parent2.trace_id)
        assert len(trace_two) == 2

        root_span2 = find_span(trace_two, parent2.span_id)
        assert root_span2["resource"] == "root_two"

        child_span2 = find_span(trace_two, child2.span_id)
        assert child_span2["resource"] == "child2"

    @irrelevant(context.library == "cpp", reason="library does not implement OpenTelemetry")
    @missing_feature(context.library <= "java@1.23.0", reason="OTel resource naming implemented in 1.24.0")
    @missing_feature(context.library == "nodejs", reason="Not implemented")
    def test_otel_force_flush(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Verify that force flush flushed the spans"""
        with test_library:
            with test_library.otel_start_span(name="test_span") as otel_span:
                pass

            # force flush with 5 second time out
            flushed = test_library.otel_flush(5)
            assert flushed, "ForceFlush error"
            # check if trace is flushed
            traces = test_agent.wait_for_num_traces(1)
            trace = find_trace(traces, otel_span.trace_id)
            span = find_span(trace, otel_span.span_id)
            assert span.get("name") == "internal"
