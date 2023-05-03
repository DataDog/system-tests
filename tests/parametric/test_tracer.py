from typing import Dict

import pytest
import time

from parametric.spec.trace import Span
from parametric.spec.trace import find_trace_by_root
from parametric.spec.trace import find_span
from .conftest import _TestAgentAPI
from .conftest import APMLibrary
from utils import missing_feature, context, scenarios


@scenarios.parametric
class Test_Tracer:

    parametrize = pytest.mark.parametrize

    @missing_feature(context.library == "nodejs", reason="nodejs overrides the manually set service name")
    def test_tracer_span_top_level_attributes(self, test_agent: _TestAgentAPI, test_library: APMLibrary) -> None:
        """Do a simple trace to ensure that the test client is working properly."""
        with test_library:
            with test_library.start_span(
                "operation", service="my-webserver", resource="/endpoint", typestr="web"
            ) as parent:
                parent.set_metric("number", 10)
                with test_library.start_span("operation.child", parent_id=parent.span_id) as child:
                    child.set_meta("key", "val")

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace_by_root(traces, Span(name="operation"))
        assert len(trace) == 2

        root_span = find_span(trace, Span(name="operation"))
        assert root_span["name"] == "operation"
        assert root_span["service"] == "my-webserver"
        assert root_span["resource"] == "/endpoint"
        assert root_span["type"] == "web"
        assert root_span["metrics"]["number"] == 10
        child_span = find_span(trace, Span(name="operation.child"))
        assert child_span["name"] == "operation.child"
        assert child_span["meta"]["key"] == "val"

    @missing_feature(reason="Libraries use empty string for service")
    @parametrize("library_env", [{"DD_SERVICE": "service1"}])
    def test_tracer_service_name_environment_variable(
        self, library_env: Dict[str, str], test_agent: _TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """
        When DD_SERVICE is specified
            When a span is created
                The span should use the value of DD_SERVICE for span.service
        """
        with test_library:
            with test_library.start_span("operation"):
                pass

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace_by_root(traces, Span(name="operation"))

        span = find_span(trace, Span(name="operation"))
        assert span["name"] == "operation"
        assert span["service"] == library_env["DD_SERVICE"]

    @parametrize("library_env", [{"DD_ENV": "prod"}])
    def test_tracer_env_environment_variable(
        self, library_env: Dict[str, str], test_agent: _TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """
        When DD_ENV is specified
            When a span is created
                The span should have the value of DD_ENV in meta.env
        """
        with test_library:
            with test_library.start_span("operation"):
                pass

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace_by_root(traces, Span(name="operation"))

        span = find_span(trace, Span(name="operation"))
        assert span["name"] == "operation"
        assert span["meta"]["env"] == library_env["DD_ENV"]