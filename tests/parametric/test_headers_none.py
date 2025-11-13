import pytest

from utils.parametric.spec.trace import SAMPLING_PRIORITY_KEY, ORIGIN
from utils.parametric.spec.trace import find_only_span
from utils import scenarios, features
from utils.docker_fixtures import TestAgentAPI

from .conftest import APMLibrary

parametrize = pytest.mark.parametrize


def enable_none() -> pytest.MarkDecorator:
    env = {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "none",
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "none",
    }
    return parametrize("library_env", [env])


def enable_none_single_key() -> pytest.MarkDecorator:
    env = {
        "DD_TRACE_PROPAGATION_STYLE": "none",
    }
    return parametrize("library_env", [env])


def enable_none_invalid() -> pytest.MarkDecorator:
    env = {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "none,Datadog",
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "none,Datadog",
    }
    return parametrize("library_env", [env])


@scenarios.parametric
@features.datadog_headers_propagation
class Test_Headers_None:
    @enable_none()
    def test_headers_none_extract(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Ensure that no distributed tracing headers are extracted."""
        with test_library:
            test_library.dd_make_child_span_and_get_headers(
                [
                    ("x-datadog-trace-id", "123456789"),
                    ("x-datadog-parent-id", "987654321"),
                    ("x-datadog-sampling-priority", "2"),
                    ("x-datadog-origin", "synthetics"),
                    ("x-datadog-tags", "_dd.p.dm=-4"),
                ],
            )

        span = find_only_span(test_agent.wait_for_num_traces(1))
        assert span.get("trace_id") != 123456789
        assert span.get("parent_id") != 987654321
        assert span["meta"].get(ORIGIN) is None
        assert span["meta"].get("_dd.p.dm") != "-4"
        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) != 2

    @enable_none_invalid()
    def test_headers_none_extract_with_other_propagators(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Ensure that the 'none' propagator is ignored when other propagators are present.
        In this case, ensure that the Datadog distributed tracing headers are extracted
        and activated properly.
        """
        with test_library:
            test_library.dd_make_child_span_and_get_headers(
                [
                    ("x-datadog-trace-id", "123456789"),
                    ("x-datadog-parent-id", "987654321"),
                    ("x-datadog-sampling-priority", "2"),
                    ("x-datadog-origin", "synthetics"),
                    ("x-datadog-tags", "_dd.p.dm=-4"),
                ],
            )

        span = find_only_span(test_agent.wait_for_num_traces(1))
        assert span.get("trace_id") == 123456789
        assert span.get("parent_id") == 987654321
        assert span["meta"].get(ORIGIN) == "synthetics"
        assert span["meta"].get("_dd.p.dm") == "-4"
        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == 2

    @enable_none()
    def test_headers_none_inject(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Ensure that the 'none' propagator is used and
        no Datadog distributed tracing headers are injected.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers([])

        assert "traceparent" not in headers
        assert "tracestate" not in headers
        assert "x-datadog-trace-id" not in headers
        assert "x-datadog-parent-id" not in headers
        assert "x-datadog-sampling-priority" not in headers
        assert "x-datadog-origin" not in headers
        assert "x-datadog-tags" not in headers

    @enable_none_invalid()
    def test_headers_none_inject_with_other_propagators(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Ensure that the 'none' propagator is ignored when other propagators are present.
        In this case, ensure that the Datadog distributed tracing headers are injected properly.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers([])

        span = find_only_span(test_agent.wait_for_num_traces(1))
        assert int(headers["x-datadog-trace-id"]) == span.get("trace_id")
        assert int(headers["x-datadog-parent-id"]) == span.get("span_id")
        assert int(headers["x-datadog-sampling-priority"]) == span["metrics"].get(SAMPLING_PRIORITY_KEY)

    @enable_none()
    def test_headers_none_propagate(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Ensure that the 'none' propagator is used and
        no Datadog distributed tracing headers are extracted or injected.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [
                    ("x-datadog-trace-id", "123456789"),
                    ("x-datadog-parent-id", "987654321"),
                    ("x-datadog-sampling-priority", "2"),
                    ("x-datadog-origin", "synthetics"),
                    ("x-datadog-tags", "_dd.p.dm=-4"),
                ],
            )

        span = find_only_span(test_agent.wait_for_num_traces(1))
        assert span.get("trace_id") != 123456789
        assert span.get("parent_id") != 987654321
        assert span["meta"].get(ORIGIN) is None
        assert span["meta"].get("_dd.p.dm") != "-4"
        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) != 2

        assert "traceparent" not in headers
        assert "tracestate" not in headers
        assert "x-datadog-trace-id" not in headers
        assert "x-datadog-parent-id" not in headers
        assert "x-datadog-sampling-priority" not in headers
        assert "x-datadog-origin" not in headers
        assert "x-datadog-tags" not in headers

    @enable_none_single_key()
    def test_headers_none_single_key_propagate(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Ensure that the 'none' propagator is used and
        no Datadog distributed tracing headers are extracted or injected.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [
                    ("x-datadog-trace-id", "123456789"),
                    ("x-datadog-parent-id", "987654321"),
                    ("x-datadog-sampling-priority", "2"),
                    ("x-datadog-origin", "synthetics"),
                    ("x-datadog-tags", "_dd.p.dm=-4"),
                ],
            )

        span = find_only_span(test_agent.wait_for_num_traces(1))
        assert span.get("trace_id") != 123456789
        assert span.get("parent_id") != 987654321
        assert span["meta"].get(ORIGIN) is None
        assert span["meta"].get("_dd.p.dm") != "-4"
        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) != 2

        assert "traceparent" not in headers
        assert "tracestate" not in headers
        assert "x-datadog-trace-id" not in headers
        assert "x-datadog-parent-id" not in headers
        assert "x-datadog-sampling-priority" not in headers
        assert "x-datadog-origin" not in headers
        assert "x-datadog-tags" not in headers
