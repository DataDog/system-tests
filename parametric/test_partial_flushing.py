import pytest
from parametric.spec.trace import Span
from parametric.spec.trace import find_span_in_traces


@pytest.mark.parametrize("library_env", [{"DD_TRACE_PARTIAL_FLUSH_MIN_SPANS": "1",}])
@pytest.mark.skip_library("java", "java uses '>' so it needs one more span to force a partial flush")
@pytest.mark.skip_library("ruby", "no way to configure partial flushing")
@pytest.mark.skip_library("golang,", "partial flushing not implemented")
@pytest.mark.skip_library("php,", "partial flushing not implemented")
def test_partial_flushing_one_span(test_agent, test_library):
    with test_library:
        with test_library.start_span(name="root") as parent_span:
            with test_library.start_span(name="child1", parent_id=parent_span.span_id):
                pass
            partial_trace = test_agent.wait_for_num_traces(1, clear=True)
            child_span = find_span_in_traces(partial_trace, Span(name="child1"))
            assert len(partial_trace) == 1
            assert child_span["name"] == "child1"
    traces = test_agent.wait_for_num_traces(1, clear=True)
    root_span = find_span_in_traces(traces, Span(name="root"))
    assert len(traces) == 1
    assert root_span["name"] == "root"


@pytest.mark.parametrize("library_env", [{"DD_TRACE_PARTIAL_FLUSH_MIN_SPANS": "5",}])
@pytest.mark.skip_library(
    "dotnet", "due to the way the child span is made it's not part of the spanContext so a flush still happens here"
)
@pytest.mark.skip_library("golang,", "partial flushing not implemented")
@pytest.mark.skip_library("php,", "partial flushing not implemented")
@pytest.mark.skip_library("ruby", "no way to configure partial flushing")
def test_partial_flushing_under_limit_one_payload(test_agent, test_library):
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
