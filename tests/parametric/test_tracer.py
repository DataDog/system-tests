import os
from typing import Dict

import pytest

from utils.parametric.spec.trace import Span
from utils.parametric.spec.trace import find_trace_by_root
from utils.parametric.spec.trace import find_span
from .conftest import _TestAgentAPI
from .conftest import APMLibrary
from utils import missing_feature, context, scenarios, released


parametrize = pytest.mark.parametrize


@scenarios.parametric
class Test_Tracer:
    @missing_feature(context.library == "cpp", reason="version not detected by parametric tests yet")
    @missing_feature(context.library == "php", reason="version not detected by parametric tests yet")
    def test_tracer_parametric_version(self, test_agent: _TestAgentAPI, test_library: APMLibrary) -> None:
        """Ensure the version used by parametric tests matches the library version being tested.

        If this test fails then either the version detected/used by the parametric testing framework is wrong
        or the library is not reporting the right version.
        """
        if "PYTHON_DDTRACE_PACKAGE" in os.environ:
            pytest.skip("Custom python library versions are not yet supported by the parametric tests")
        if "RUBY_DDTRACE_SHA" in os.environ:
            pytest.skip("Custom ruby library versions are not supported by the parametric tests")

        with test_library:
            with test_library.start_span("operation"):
                pass
        test_agent.wait_for_num_traces(1)
        request = [r for r in test_agent.requests() if "trace" in r["url"]][0]
        reported_tracer_version = request["headers"]["Datadog-Meta-Tracer-Version"]
        assert reported_tracer_version == context.library.version, (
            "Parametric library detected version %r does not match library "
            "version %r seen in trace request.\n"
            "Likely reasons for this test failing: 1) Parametric library detection being wrong; 2) library reporting "
            "the wrong version"
        ) % (context.library.version, reported_tracer_version)

    @missing_feature(context.library == "cpp", reason="metrics cannot be set manually")
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


@scenarios.parametric
@released(python="1.18.0")
class Test_TracerUniversalServiceTagging:
    @missing_feature(reason="FIXME: library test client sets empty string as the service name")
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
        assert 0

    # @parametrize("library_env", [{"DD_VERSION": "1.2.3"}])
    # def test_tracer_version_environment_variable(
    #         self, library_env: Dict[str, str], test_agent: _TestAgentAPI, test_library: APMLibrary
    # ) -> None:
    #     """
    #     When DD_VERSION is specified
    #         When a service-entry span is created
    #             The service-entry span should have the value of DD_VERSION in meta.version
    #             A child span should not have the value of DD_VERSION in meta.version

    #     """
    #     with test_library:
    #         with test_library.start_span("operation"):
    #             with test_library.start_span("child"):
    #                 pass

    #     traces = test_agent.wait_for_num_traces(1)
    #     trace = find_trace_by_root(traces, Span(name="operation"))
    #     service_entry_span = find_span(trace, Span(name="operation"))
    #     child_span = find_span(trace, Span(name="child"))
    #     assert service_entry_span["meta"]["version"] == library_env["DD_VERSION"]
    #     assert "version" not in child_span["meta"]
