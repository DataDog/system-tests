import pytest
from utils.parametric.spec.trace import Span
from utils.parametric.spec.trace import find_span_in_traces
from utils import missing_feature, bug, context, scenarios


@scenarios.parametric
class Test_Partial_Flushing:
    @pytest.mark.parametrize(
        "library_env", [{"DD_TRACE_PARTIAL_FLUSH_MIN_SPANS": "1", "DD_TRACE_PARTIAL_FLUSH_ENABLED": "true",}]
    )
    @missing_feature(context.library == "cpp", reason="partial flushing not implemented")
    @missing_feature(
        context.library == "java", reason="java uses '>' so it needs one more span to force a partial flush"
    )
    @missing_feature(context.library == "ruby", reason="no way to configure partial flushing")
    @missing_feature(context.library == "php", reason="partial flushing not implemented")
    def test_partial_flushing_one_span(self, test_agent, test_library):
        """
            Create a trace with a root span and a single child. Finish the child, and ensure
            partial flushing triggers. This test explicitly enables partial flushing.
        """
        do_partial_flush_test(self, test_agent, test_library)

    @pytest.mark.parametrize("library_env", [{"DD_TRACE_PARTIAL_FLUSH_MIN_SPANS": "1",}])
    @missing_feature(context.library == "cpp", reason="partial flushing not implemented")
    @missing_feature(
        context.library == "java", reason="java uses '>' so it needs one more span to force a partial flush"
    )
    @missing_feature(context.library == "ruby", reason="no way to configure partial flushing")
    @missing_feature(context.library == "php", reason="partial flushing not implemented")
    @missing_feature(context.library == "golang", reason="partial flushing not enabled by default")
    @missing_feature(context.library == "dotnet", reason="partial flushing not enabled by default")
    def test_partial_flushing_one_span_default(self, test_agent, test_library):
        """
            Create a trace with a root span and a single child. Finish the child, and ensure
            partial flushing triggers. This test assumes partial flushing is enabled by default.
        """
        do_partial_flush_test(self, test_agent, test_library)

    @pytest.mark.parametrize(
        "library_env", [{"DD_TRACE_PARTIAL_FLUSH_MIN_SPANS": "5", "DD_TRACE_PARTIAL_FLUSH_ENABLED": "true",}]
    )
    @missing_feature(context.library == "cpp", reason="partial flushing not implemented")
    @missing_feature(context.library == "php", reason="partial flushing not implemented")
    @missing_feature(context.library == "ruby", reason="no way to configure partial flushing")
    def test_partial_flushing_under_limit_one_payload(self, test_agent, test_library):
        """
            Create a trace with a root span and a single child. Finish the child, and ensure
            partial flushing does NOT trigger, since the partial flushing min spans is set to 5.
        """
        no_partial_flush_test(self, test_agent, test_library)

    @pytest.mark.parametrize(
        "library_env", [{"DD_TRACE_PARTIAL_FLUSH_MIN_SPANS": "1", "DD_TRACE_PARTIAL_FLUSH_ENABLED": "false",}]
    )
    @missing_feature(context.library == "cpp", reason="partial flushing not implemented")
    @missing_feature(context.library == "java", reason="does not use DD_TRACE_PARTIAL_FLUSH_ENABLED")
    @missing_feature(context.library == "ruby", reason="no way to configure partial flushing")
    @missing_feature(context.library == "php", reason="partial flushing not implemented")
    def test_partial_flushing_disabled(self, test_agent, test_library):
        """
            Create a trace with a root span and a single child. Finish the child, and ensure
            partial flushing does NOT trigger, since it's explicitly disabled.
        """
        no_partial_flush_test(self, test_agent, test_library)


def do_partial_flush_test(self, test_agent, test_library):
    """
        Create a trace with a root span and a single child. Finish the child, and ensure
        partial flushing triggers.
    """
    with test_library:
        with test_library.start_span(name="root") as parent_span:
            with test_library.start_span(name="child1", parent_id=parent_span.span_id):
                pass
            partial_trace = test_agent.wait_for_num_traces(1, clear=True, wait_loops=30)
            child_span = find_span_in_traces(partial_trace, Span(name="child1"))
            assert len(partial_trace) == 1
            assert child_span["name"] == "child1"
    traces = test_agent.wait_for_num_traces(1, clear=True)
    root_span = find_span_in_traces(traces, Span(name="root"))
    assert len(traces) == 1
    assert root_span["name"] == "root"


def no_partial_flush_test(self, test_agent, test_library):
    """
        Create a trace with a root span and one child. Finish the child, and ensure
        partial flushing does NOT trigger.
    """
    with test_library:
        with test_library.start_span(name="root") as parent_span:
            with test_library.start_span(name="child1", parent_id=parent_span.span_id):
                pass
            try:
                partial_traces = test_agent.wait_for_num_traces(1, clear=True)
                assert partial_traces is None
            except ValueError:
                pass  # We expect there won't be a flush, so catch this exception
    traces = test_agent.wait_for_num_traces(1, clear=True)
    root_span = find_span_in_traces(traces, Span(name="root"))
    assert len(traces) == 1
    assert root_span["name"] == "root"
