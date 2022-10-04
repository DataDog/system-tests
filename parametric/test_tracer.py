from typing import Dict

import pytest

from parametric.spec.trace import Span
from parametric.spec.trace import find_trace_by_root
from parametric.spec.trace import find_span
from .conftest import _TestAgentAPI
from .conftest import APMLibrary


parametrize = pytest.mark.parametrize


def test_tracer_span_top_level_attributes(test_library: APMLibrary, test_agent: _TestAgentAPI) -> None:
    """Do a simple trace to ensure that the test client is working properly."""
    with test_library:
        with test_library.start_span(
            "operation", service="my-webserver", resource="/endpoint", typestr="web"
        ) as parent:
            parent.set_metric("number", 10)
            with test_library.start_span("operation.child", parent_id=parent.span_id) as child:
                child.set_meta("key", "val")

    traces = test_agent.traces()
    trace = find_trace_by_root(traces, Span(name="operation"))
    assert len(trace) == 2

    root_span = find_span(trace, Span(name="operation"))
    child_span = find_span(trace, Span(name="operation.child"))
    # assert trace[0]["name"] == "operation"
    # assert trace[0]["service"] == "my-webserver"
    # assert trace[0]["resource"] == "/endpoint"
    # assert trace[0]["type"] == "web"


@pytest.mark.skip(reason="Libraries handle empty string for service")
@parametrize("library_env", [{"DD_SERVICE": "service1"}, {"DD_SERVICE": "service2"}])
def test_tracer_service_name_environment_variable(
    library_env: Dict[str, str], test_library: APMLibrary, test_agent: _TestAgentAPI
) -> None:
    """Traces should use DD_SERVICE for the service name of traces which do not specify a service name."""
    with test_library:
        with test_library.start_span("operation"):
            pass

    traces = test_agent.traces()
    trace = find_trace_by_root(traces, Span(name="operation"))
    assert len(trace) == 1

    span = find_span(trace, Span(name="operation"))
    assert span["name"] == "operation"
    assert span["service"] == library_env["DD_SERVICE"]


@parametrize("library_env", [{"DD_ENV": "prod"}, {"DD_ENV": "dev"}])
def test_tracer_env_environment_variable(
    library_env: Dict[str, str], test_library: APMLibrary, test_agent: _TestAgentAPI
) -> None:
    """
    When DD_ENV is specified
        Spans should set the value of DD_ENV in the meta map.
    """
    with test_library:
        with test_library.start_span("operation"):
            pass

    traces = test_agent.traces()
    trace = find_trace_by_root(traces, Span(name="operation"))
    assert len(trace) == 1

    span = find_span(trace, Span(name="operation"))
    assert span["name"] == "operation"
    assert span["meta"]["env"] == library_env["DD_ENV"]
