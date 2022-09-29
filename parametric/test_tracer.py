from parametric.spec.trace import Span
from parametric.spec.trace import find_trace_by_root


from .conftest import _TestAgentAPI
from .conftest import _TestTracer


def test_tracer_simple(test_client: _TestTracer, test_agent: _TestAgentAPI) -> None:
    """Do a simple trace to ensure that the test client is working properly."""
    with test_client:
        with test_client.start_span("operation", service="my-webserver", resource="/endpoint", typestr="web") as parent:
            parent.set_metric("number", 10)
            with test_client.start_span("operation.child", parent_id=parent.span_id) as child:
                child.set_meta("key", "val")
    traces = test_agent.traces()
    trace = find_trace_by_root(traces, Span(name="operation"))
    assert len(trace) == 2
