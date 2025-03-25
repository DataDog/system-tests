import pytest
from utils.parametric.spec.trace import find_span, find_trace
from utils import missing_feature, features, context, scenarios


@features.partial_flush
@scenarios.parametric
class Test_Partial_Flushing:
    @pytest.mark.parametrize(
        "library_env", [{"DD_TRACE_PARTIAL_FLUSH_MIN_SPANS": "1", "DD_TRACE_PARTIAL_FLUSH_ENABLED": "true"}]
    )
    @missing_feature(
        context.library == "java", reason="java uses '>' so it needs one more span to force a partial flush"
    )
    def test_partial_flushing_one_span(self, test_agent, test_library):
        """Create a trace with a root span and a single child. Finish the child, and ensure
        partial flushing triggers. This test explicitly enables partial flushing.
        """
        self.do_partial_flush_test(test_agent, test_library)

    @pytest.mark.parametrize("library_env", [{"DD_TRACE_PARTIAL_FLUSH_MIN_SPANS": "1"}])
    @missing_feature(
        context.library == "java", reason="java uses '>' so it needs one more span to force a partial flush"
    )
    @missing_feature(context.library == "golang", reason="partial flushing not enabled by default")
    @missing_feature(context.library == "dotnet", reason="partial flushing not enabled by default")
    def test_partial_flushing_one_span_default(self, test_agent, test_library):
        """Create a trace with a root span and a single child. Finish the child, and ensure
        partial flushing triggers. This test assumes partial flushing is enabled by default.
        """
        self.do_partial_flush_test(test_agent, test_library)

    @pytest.mark.parametrize(
        "library_env", [{"DD_TRACE_PARTIAL_FLUSH_MIN_SPANS": "5", "DD_TRACE_PARTIAL_FLUSH_ENABLED": "true"}]
    )
    def test_partial_flushing_under_limit_one_payload(self, test_agent, test_library):
        """Create a trace with a root span and a single child. Finish the child, and ensure
        partial flushing does NOT trigger, since the partial flushing min spans is set to 5.
        """
        self.no_partial_flush_test(test_agent, test_library)

    @pytest.mark.parametrize(
        "library_env", [{"DD_TRACE_PARTIAL_FLUSH_MIN_SPANS": "1", "DD_TRACE_PARTIAL_FLUSH_ENABLED": "false"}]
    )
    def test_partial_flushing_disabled(self, test_agent, test_library):
        """Create a trace with a root span and a single child. Finish the child, and ensure
        partial flushing does NOT trigger, since it's explicitly disabled.
        """
        self.no_partial_flush_test(test_agent, test_library)

    def do_partial_flush_test(self, test_agent, test_library):
        """Create a trace with a root span and a single child. Finish the child, and ensure
        partial flushing triggers.
        """
        with test_library, test_library.dd_start_span(name="root") as parent_span:
            with test_library.dd_start_span(name="child1", parent_id=parent_span.span_id) as child1:
                pass
            partial_traces = test_agent.wait_for_num_traces(1, clear=True, wait_loops=30)
            partial_trace = find_trace(partial_traces, parent_span.trace_id)
            assert len(partial_trace) == 1
            child_span = find_span(partial_trace, child1.span_id)
            assert child_span["name"] == "child1"
            # verify the partially flushed chunk has proper "trace level" tags
            assert child_span["metrics"]["_sampling_priority_v1"] == 1.0
            assert len(child_span["meta"]["_dd.p.tid"]) > 0

        traces = test_agent.wait_for_num_traces(1, clear=True)
        full_trace = find_trace(traces, parent_span.trace_id)
        root_span = find_span(full_trace, parent_span.span_id)
        assert len(traces) == 1
        assert root_span["name"] == "root"

    def no_partial_flush_test(self, test_agent, test_library):
        """Create a trace with a root span and one child. Finish the child, and ensure
        partial flushing does NOT trigger.
        """
        with test_library, test_library.dd_start_span(name="root") as parent_span:
            with test_library.dd_start_span(name="child1", parent_id=parent_span.span_id):
                pass
            try:
                partial_traces = test_agent.wait_for_num_traces(1, clear=True)
                assert partial_traces is None
            except ValueError:
                pass  # We expect there won't be a flush, so catch this exception
        traces = test_agent.wait_for_num_traces(1, clear=True)
        trace = find_trace(traces, parent_span.trace_id)
        assert len(traces) == 1
        root_span = find_span(trace, parent_span.span_id)
        assert root_span["name"] == "root"
