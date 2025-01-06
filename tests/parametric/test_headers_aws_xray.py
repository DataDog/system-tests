from typing import Any

import pytest

from utils.parametric.spec.trace import SAMPLING_PRIORITY_KEY, ORIGIN
from utils.parametric.spec.trace import span_has_no_parent
from utils.parametric.spec.trace import find_only_span
from utils import missing_feature, context, scenarios, features, bug
from utils.tools import logger

parametrize = pytest.mark.parametrize


def enable_aws_xray() -> Any:
    env = {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "xray",
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "xray",
    }
    return parametrize("library_env", [env])


@features.aws_xray_headers_propagation
@scenarios.parametric
class Test_Headers_AWS_Xray:
    @enable_aws_xray()
    @missing_feature(context.library == "ruby", reason="AWS Xray propagation formatted not supported yet.")
    @missing_feature(context.library == "cpp", reason="AWS Xray propagation formatted not supported yet.")
    @missing_feature(context.library == "dotnet", reason="AWS Xray propagation formatted not supported yet.")
    @missing_feature(context.library == "golang", reason="AWS Xray propagation formatted not supported yet.")
    @missing_feature(context.library == "php", reason="AWS Xray propagation formatted not supported yet.")
    def test_headers_aws_xray_extract_valid(self, test_agent, test_library):
        """Ensure that AWS Xray distributed tracing headers are extracted
        and activated properly.
        """
        with test_library:
            test_library.dd_make_child_span_and_get_headers(
                [["x-amzn-trace-id", "Root=1-00000000-000000000000000012345678;Parent=000000987654321;Sampled=1"]]
            )

        span = find_only_span(test_agent.wait_for_num_traces(1))

        assert span.get("trace_id") == int("12345678", 16)
        assert span.get("parent_id") == int("987654321", 16)
        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == 1
        assert span["meta"].get(ORIGIN) is None

    @enable_aws_xray()
    @missing_feature(context.library == "ruby", reason="AWS Xray propagation formatted not supported yet.")
    @missing_feature(context.library == "cpp", reason="AWS Xray propagation formatted not supported yet.")
    @missing_feature(context.library == "dotnet", reason="AWS Xray propagation formatted not supported yet.")
    @missing_feature(context.library == "golang", reason="AWS Xray propagation formatted not supported yet.")
    @missing_feature(context.library == "php", reason="AWS Xray propagation formatted not supported yet.")
    def test_headers_aws_xray_extract_invalid(self, test_agent, test_library):
        """Ensure that invalid AWS Xray distributed tracing headers are not extracted."""
        with test_library:
            test_library.dd_make_child_span_and_get_headers([["x-amzn-trace-id", "0-0-1"]])

        span = find_only_span(test_agent.wait_for_num_traces(1))
        assert span.get("trace_id") != 0
        assert span_has_no_parent(span)
        assert span["meta"].get(ORIGIN) is None

    @enable_aws_xray()
    @missing_feature(context.library == "ruby", reason="AWS Xray propagation formatted not supported yet.")
    @missing_feature(context.library == "cpp", reason="AWS Xray propagation formatted not supported yet.")
    @missing_feature(context.library == "dotnet", reason="AWS Xray propagation formatted not supported yet.")
    @missing_feature(context.library == "golang", reason="AWS Xray propagation formatted not supported yet.")
    @missing_feature(context.library == "php", reason="AWS Xray propagation formatted not supported yet.")
    def test_headers_aws_xray_inject_valid(self, test_agent, test_library):
        """Ensure that AWS Xray distributed tracing headers are injected properly."""
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers([])

        span = find_only_span(test_agent.wait_for_num_traces(1))

        xray_arr = parse_aws_header(headers["x-amzn-trace-id"])

        logger.info(f"AWS Xray header is {headers['x-amzn-trace-id']}")
        xray_trace_id = xray_arr[0]
        xray_span_id = xray_arr[1]
        xray_sampling = xray_arr[2]

        assert len(xray_trace_id) == 24
        assert int(xray_trace_id[-16:], base=16) == span.get("trace_id")
        assert int(xray_span_id, base=16) == span.get("span_id") and len(xray_span_id) == 16
        assert xray_sampling == "1" if span["metrics"].get(SAMPLING_PRIORITY_KEY) > 0 else "0"
        assert span["meta"].get(ORIGIN) is None

    @enable_aws_xray()
    @missing_feature(context.library == "ruby", reason="AWS Xray propagation formatted not supported yet.")
    @missing_feature(context.library == "cpp", reason="AWS Xray propagation formatted not supported yet.")
    @missing_feature(context.library == "dotnet", reason="AWS Xray propagation formatted not supported yet.")
    @missing_feature(context.library == "golang", reason="AWS Xray propagation formatted not supported yet.")
    @missing_feature(context.library == "php", reason="AWS Xray propagation formatted not supported yet.")
    def test_headers_aws_xray_propagate_valid(self, test_agent, test_library):
        """Ensure that AWS Xray distributed tracing headers are extracted
        and injected properly.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [["x-amzn-trace-id", "Root=1-00000000-000000000000000012345678;Parent=000000987654321;Sampled=1"]]
            )

        span = find_only_span(test_agent.wait_for_num_traces(1))

        xray_arr = parse_aws_header(headers["x-amzn-trace-id"])

        xray_trace_id = xray_arr[0]
        xray_span_id = xray_arr[1]
        xray_sampling = xray_arr[2]

        assert len(xray_trace_id) == 24
        assert int(xray_trace_id, base=16) == span.get("trace_id")
        assert int(xray_span_id, base=16) == span.get("span_id") and len(xray_span_id) == 16
        assert xray_sampling == "1"
        assert span["meta"].get(ORIGIN) is None

    @enable_aws_xray()
    @missing_feature(context.library == "ruby", reason="AWS Xray propagation formatted not supported yet.")
    @missing_feature(context.library == "cpp", reason="AWS Xray propagation formatted not supported yet.")
    @missing_feature(context.library == "dotnet", reason="AWS Xray propagation formatted not supported yet.")
    @missing_feature(context.library == "golang", reason="AWS Xray propagation formatted not supported yet.")
    @missing_feature(context.library == "php", reason="AWS Xray propagation formatted not supported yet.")
    def test_headers_aws_xray_propagate_invalid(self, test_agent, test_library):
        """Ensure that invalid AWS Xray distributed tracing headers are not extracted
        and the new span context is injected properly.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [["x-amzn-trace-id", "Root=1-00000000-0;Parent=0"]]
            )

        span = find_only_span(test_agent.wait_for_num_traces(1))
        assert span_has_no_parent(span)
        assert span["meta"].get(ORIGIN) is None

        assert span.get("trace_id") != 0
        assert span.get("span_id") != 0


def parse_aws_header(header):
    key_value_pairs = header.split(";")
    results = []
    for pair in key_value_pairs:
        if "=" in pair:
            key, value = pair.split("=", 1)
            if key.lower() == "root":
                trace_id = value[-24:]
                results.append(trace_id)
            elif key.lower() == "parent":
                results.append(value)
            elif key.lower() == "sampled":
                results.append(value)
            elif key.lower() == "_dd.origin":
                results.append(value)

    return results
