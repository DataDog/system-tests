from typing import Any

import pytest

from utils.parametric.spec.trace import SAMPLING_PRIORITY_KEY, ORIGIN
from utils.parametric.headers import make_single_request_and_get_inject_headers
from utils.parametric.test_agent import get_span
from utils import missing_feature, context, scenarios, features, bug

parametrize = pytest.mark.parametrize


def enable_none() -> Any:
    env = {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "none",
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "none",
    }
    return parametrize("library_env", [env])


def enable_none_single_key() -> Any:
    env = {
        "DD_TRACE_PROPAGATION_STYLE": "none",
    }
    return parametrize("library_env", [env])


def enable_none_invalid() -> Any:
    env = {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "none,Datadog",
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "none,Datadog",
    }
    return parametrize("library_env", [env])


@scenarios.parametric
@features.datadog_headers_propagation
class Test_Headers_None:
    @enable_none()
    def test_headers_none_extract(self, test_agent, test_library):
        """Ensure that no distributed tracing headers are extracted."""
        with test_library:
            headers = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["x-datadog-trace-id", "123456789"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-sampling-priority", "2"],
                    ["x-datadog-origin", "synthetics"],
                    ["x-datadog-tags", "_dd.p.dm=-4"],
                ],
            )

        span = get_span(test_agent)
        assert span.get("trace_id") != 123456789
        assert span.get("parent_id") != 987654321
        assert span["meta"].get(ORIGIN) is None
        assert span["meta"].get("_dd.p.dm") != "-4"
        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) != 2

    @enable_none_invalid()
    def test_headers_none_extract_with_other_propagators(self, test_agent, test_library):
        """Ensure that the 'none' propagator is ignored when other propagators are present.
        In this case, ensure that the Datadog distributed tracing headers are extracted
        and activated properly.
        """
        with test_library:
            headers = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["x-datadog-trace-id", "123456789"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-sampling-priority", "2"],
                    ["x-datadog-origin", "synthetics"],
                    ["x-datadog-tags", "_dd.p.dm=-4"],
                ],
            )

        span = get_span(test_agent)
        assert span.get("trace_id") == 123456789
        assert span.get("parent_id") == 987654321
        assert span["meta"].get(ORIGIN) == "synthetics"
        assert span["meta"].get("_dd.p.dm") == "-4"
        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == 2

    @enable_none()
    def test_headers_none_inject(self, test_agent, test_library):
        """Ensure that the 'none' propagator is used and
        no Datadog distributed tracing headers are injected.
        """
        with test_library:
            headers = make_single_request_and_get_inject_headers(test_library, [])

        assert "traceparent" not in headers
        assert "tracestate" not in headers
        assert "x-datadog-trace-id" not in headers
        assert "x-datadog-parent-id" not in headers
        assert "x-datadog-sampling-priority" not in headers
        assert "x-datadog-origin" not in headers
        assert "x-datadog-tags" not in headers

    @enable_none_invalid()
    def test_headers_none_inject_with_other_propagators(self, test_agent, test_library):
        """Ensure that the 'none' propagator is ignored when other propagators are present.
        In this case, ensure that the Datadog distributed tracing headers are injected properly.
        """
        with test_library:
            headers = make_single_request_and_get_inject_headers(test_library, [])

        span = get_span(test_agent)
        assert int(headers["x-datadog-trace-id"]) == span.get("trace_id")
        assert int(headers["x-datadog-parent-id"]) == span.get("span_id")
        assert int(headers["x-datadog-sampling-priority"]) == span["metrics"].get(SAMPLING_PRIORITY_KEY)

    @enable_none()
    def test_headers_none_propagate(self, test_agent, test_library):
        """Ensure that the 'none' propagator is used and
        no Datadog distributed tracing headers are extracted or injected.
        """
        with test_library:
            headers = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["x-datadog-trace-id", "123456789"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-sampling-priority", "2"],
                    ["x-datadog-origin", "synthetics"],
                    ["x-datadog-tags", "_dd.p.dm=-4"],
                ],
            )

        span = get_span(test_agent)
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
    @missing_feature(
        context.library == "ruby",
        reason="Propagators not configured for DD_TRACE_PROPAGATION_STYLE config",
    )
    def test_headers_none_single_key_propagate(self, test_agent, test_library):
        """Ensure that the 'none' propagator is used and
        no Datadog distributed tracing headers are extracted or injected.
        """
        with test_library:
            headers = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["x-datadog-trace-id", "123456789"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-sampling-priority", "2"],
                    ["x-datadog-origin", "synthetics"],
                    ["x-datadog-tags", "_dd.p.dm=-4"],
                ],
            )

        span = get_span(test_agent)
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
