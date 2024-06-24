from typing import Any

import pytest

from utils.parametric.spec.trace import SAMPLING_PRIORITY_KEY, ORIGIN
from utils.parametric.spec.trace import span_has_no_parent
from utils.parametric.headers import make_single_request_and_get_inject_headers
from utils.parametric.test_agent import get_span
from utils import missing_feature, irrelevant, context, scenarios, features, bug

parametrize = pytest.mark.parametrize


def enable_b3multi() -> Any:
    env = {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "b3multi",
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "b3multi",
    }
    return parametrize("library_env", [env])


def enable_b3multi_single_key() -> Any:
    env = {
        "DD_TRACE_PROPAGATION_STYLE": "b3multi",
    }
    return parametrize("library_env", [env])


def enable_b3_deprecated() -> Any:
    env1 = {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "b3",
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "b3",
    }
    env2 = {
        "DD_TRACE_PROPAGATION_STYLE": "b3",
    }
    return parametrize("library_env", [env1, env2])


def enable_case_insensitive_b3multi() -> Any:
    env1 = {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "B3MULTI",
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "b3multi",
    }
    env2 = {
        "DD_TRACE_PROPAGATION_STYLE": "B3multi",
    }
    return parametrize("library_env", [env1, env2])


@features.b3_headers_propagation
@scenarios.parametric
class Test_Headers_B3multi:
    @enable_b3multi()
    def test_headers_b3multi_extract_valid(self, test_agent, test_library):
        """Ensure that b3multi distributed tracing headers are extracted
        and activated properly.
        """
        with test_library:
            headers = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["x-b3-traceid", "000000000000000000000000075bcd15"],
                    ["x-b3-spanid", "000000003ade68b1"],
                    ["x-b3-sampled", "1"],
                ],
            )

        span = get_span(test_agent)
        assert span.get("trace_id") == 123456789
        assert span.get("parent_id") == 987654321
        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == 1
        assert span["meta"].get(ORIGIN) is None

    @enable_b3multi()
    def test_headers_b3multi_extract_invalid(self, test_agent, test_library):
        """Ensure that invalid b3multi distributed tracing headers are not extracted."""
        with test_library:
            headers = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["x-b3-traceid", "0"],
                    ["x-b3-spanid", "0"],
                    ["x-b3-sampled", "1"],
                ],
            )

        span = get_span(test_agent)
        assert span.get("trace_id") != 0
        assert span_has_no_parent(span)
        assert span["meta"].get(ORIGIN) is None

    @enable_b3multi()
    def test_headers_b3multi_inject_valid(self, test_agent, test_library):
        """Ensure that b3multi distributed tracing headers are injected properly."""
        with test_library:
            headers = make_single_request_and_get_inject_headers(test_library, [])

        span = get_span(test_agent)
        b3_trace_id = headers["x-b3-traceid"]
        b3_span_id = headers["x-b3-spanid"]
        b3_sampling = headers["x-b3-sampled"]

        assert len(b3_trace_id) == 16 or len(b3_trace_id) == 32
        assert int(b3_trace_id[-16:], base=16) == span.get("trace_id")
        assert int(b3_span_id, base=16) == span.get("span_id") and len(b3_span_id) == 16
        assert b3_sampling == "1" if span["metrics"].get(SAMPLING_PRIORITY_KEY) > 0 else "0"
        assert span["meta"].get(ORIGIN) is None

    @enable_b3multi()
    def test_headers_b3multi_propagate_valid(self, test_agent, test_library):
        """Ensure that b3multi distributed tracing headers are extracted
        and injected properly.
        """
        with test_library:
            headers = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["x-b3-traceid", "000000000000000000000000075bcd15"],
                    ["x-b3-spanid", "000000003ade68b1"],
                    ["x-b3-sampled", "1"],
                ],
            )

        span = get_span(test_agent)
        assert "x-b3-traceid" in headers
        b3_trace_id = headers["x-b3-traceid"]
        b3_span_id = headers["x-b3-spanid"]
        b3_sampling = headers["x-b3-sampled"]

        assert len(b3_trace_id) == 16 or len(b3_trace_id) == 32
        assert int(b3_trace_id, base=16) == span.get("trace_id")
        assert int(b3_span_id, base=16) == span.get("span_id") and len(b3_span_id) == 16
        assert b3_sampling == "1"
        assert span["meta"].get(ORIGIN) is None

    @enable_b3multi()
    def test_headers_b3multi_propagate_invalid(self, test_agent, test_library):
        """Ensure that invalid b3multi distributed tracing headers are not extracted
        and the new span context is injected properly.
        """
        with test_library:
            headers = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["x-b3-traceid", "0"],
                    ["x-b3-spanid", "0"],
                    ["x-b3-sampled", "1"],
                ],
            )

        span = get_span(test_agent)
        assert span.get("trace_id") != 0
        assert span.get("span_id") != 0

        b3_trace_id = headers["x-b3-traceid"]
        b3_span_id = headers["x-b3-spanid"]
        b3_sampling = headers["x-b3-sampled"]

        assert len(b3_trace_id) == 16 or len(b3_trace_id) == 32
        assert int(b3_trace_id[-16:], base=16) == span.get("trace_id")
        assert int(b3_span_id, base=16) == span.get("span_id") and len(b3_span_id) == 16
        assert b3_sampling == "1" if span["metrics"].get(SAMPLING_PRIORITY_KEY) > 0 else "0"
        assert span["meta"].get(ORIGIN) is None

    @enable_b3multi_single_key()
    @missing_feature(
        context.library == "ruby",
        reason="Propagators not configured for DD_TRACE_PROPAGATION_STYLE config",
    )
    def test_headers_b3multi_single_key_propagate_valid(self, test_agent, test_library):
        """Ensure that b3multi distributed tracing headers are extracted
        and injected properly.
        """
        self.test_headers_b3multi_propagate_valid(test_agent, test_library)

    @enable_case_insensitive_b3multi()
    @missing_feature(context.library == "ruby", reason="Ruby doesn't support case-insensitive distributed headers")
    def test_headers_b3multi_case_insensitive_propagate_valid(self, test_agent, test_library):
        self.test_headers_b3multi_propagate_valid(test_agent, test_library)

    @enable_b3_deprecated()
    @irrelevant(context.library == "ruby", reason="library does not use deprecated b3 config")
    @irrelevant(context.library == "python", reason="library removed deprecated b3 config")
    def test_headers_b3multi_deprecated_extract_valid(self, test_agent, test_library):
        self.test_headers_b3multi_extract_valid(test_agent, test_library)

    @enable_b3_deprecated()
    @irrelevant(context.library == "ruby", reason="library does not use deprecated b3 config")
    def test_headers_b3multi_deprecated_extract_invalid(self, test_agent, test_library):
        self.test_headers_b3multi_extract_invalid(test_agent, test_library)

    @enable_b3_deprecated()
    @irrelevant(context.library == "ruby", reason="library does not use deprecated b3 config")
    @irrelevant(context.library == "python", reason="library removed deprecated b3 config")
    def test_headers_b3multi_deprecated_inject_valid(self, test_agent, test_library):
        self.test_headers_b3multi_inject_valid(test_agent, test_library)

    @enable_b3_deprecated()
    @irrelevant(context.library == "ruby", reason="library does not use deprecated b3 config")
    @irrelevant(context.library == "python", reason="library removed deprecated b3 config")
    def test_headers_b3multi_deprecated_propagate_valid(self, test_agent, test_library):
        self.test_headers_b3multi_propagate_valid(test_agent, test_library)

    @enable_b3_deprecated()
    @irrelevant(context.library == "ruby", reason="library does not use deprecated b3 config")
    @irrelevant(context.library == "python", reason="library removed deprecated b3 config")
    def test_headers_b3multi_deprecated_propagate_invalid(self, test_agent, test_library):
        self.test_headers_b3multi_propagate_invalid(test_agent, test_library)
