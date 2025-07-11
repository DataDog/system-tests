import pytest

from utils.parametric.spec.trace import SAMPLING_PRIORITY_KEY, ORIGIN
from utils.parametric.spec.trace import span_has_no_parent
from utils.parametric.spec.trace import find_only_span
from utils import missing_feature, context, scenarios, features, irrelevant, logger

parametrize = pytest.mark.parametrize


def enable_b3() -> pytest.MarkDecorator:
    env = {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "B3 single header",
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "B3 single header",
    }
    return parametrize("library_env", [env])


def enable_b3_single_key() -> pytest.MarkDecorator:
    env = {
        "DD_TRACE_PROPAGATION_STYLE": "B3 single header",
    }
    return parametrize("library_env", [env])


def enable_migrated_b3() -> pytest.MarkDecorator:
    env = {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "b3",
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "b3",
    }
    return parametrize("library_env", [env])


def enable_migrated_b3_single_key() -> pytest.MarkDecorator:
    env = {
        "DD_TRACE_PROPAGATION_STYLE": "b3",
    }
    return parametrize("library_env", [env])


@features.b3_headers_propagation
@scenarios.parametric
class Test_Headers_B3:
    @enable_b3()
    @missing_feature(context.library > "ruby@1.99.0", reason="Missing for 2.x")
    @irrelevant(context.library > "python@2.20.0", reason="Deprecated in 3.x")
    @missing_feature(context.library == "cpp", reason="format of DD_TRACE_PROPAGATION_STYLE_EXTRACT not supported")
    def test_headers_b3_extract_valid(self, test_agent, test_library):
        """Ensure that b3 distributed tracing headers are extracted
        and activated properly.
        """
        with test_library:
            test_library.dd_make_child_span_and_get_headers(
                [["b3", "000000000000000000000000075bcd15-000000003ade68b1-1"]]
            )

        span = find_only_span(test_agent.wait_for_num_traces(1))
        assert span.get("trace_id") == 123456789
        assert span.get("parent_id") == 987654321
        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == 1
        assert span["meta"].get(ORIGIN) is None

    @enable_b3()
    @missing_feature(context.library > "ruby@1.99.0", reason="Missing for 2.x")
    @missing_feature(context.library == "cpp", reason="format of DD_TRACE_PROPAGATION_STYLE_EXTRACT not supported")
    @irrelevant(context.library > "python@2.20.0", reason="Deprecated in 3.x")
    def test_headers_b3_extract_invalid(self, test_agent, test_library):
        """Ensure that invalid b3 distributed tracing headers are not extracted."""
        with test_library:
            test_library.dd_make_child_span_and_get_headers([["b3", "0-0-1"]])

        span = find_only_span(test_agent.wait_for_num_traces(1))
        assert span.get("trace_id") != 0
        assert span_has_no_parent(span)
        assert span["meta"].get(ORIGIN) is None

    @enable_b3()
    @missing_feature(context.library > "ruby@1.99.0", reason="Missing for 2.x")
    @missing_feature(context.library == "cpp", reason="format of DD_TRACE_PROPAGATION_STYLE_EXTRACT not supported")
    @irrelevant(context.library > "python@2.20.0", reason="Deprecated in 3.x")
    def test_headers_b3_inject_valid(self, test_agent, test_library):
        """Ensure that b3 distributed tracing headers are injected properly."""
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers([])

        span = find_only_span(test_agent.wait_for_num_traces(1))
        b3_arr = headers["b3"].split("-")
        logger.info(f"b3 header is {headers['b3']}")
        b3_trace_id = b3_arr[0]
        b3_span_id = b3_arr[1]
        b3_sampling = b3_arr[2]

        assert len(b3_trace_id) == 16 or len(b3_trace_id) == 32
        assert int(b3_trace_id[-16:], base=16) == span.get("trace_id")
        assert int(b3_span_id, base=16) == span.get("span_id")
        assert len(b3_span_id) == 16
        assert b3_sampling == "1" if span["metrics"].get(SAMPLING_PRIORITY_KEY) > 0 else "0"
        assert span["meta"].get(ORIGIN) is None

    @enable_b3()
    @missing_feature(context.library > "ruby@1.99.0", reason="Missing for 2.x")
    @missing_feature(context.library == "cpp", reason="format of DD_TRACE_PROPAGATION_STYLE_EXTRACT not supported")
    @irrelevant(context.library > "python@2.20.0", reason="Deprecated in 3.x")
    def test_headers_b3_propagate_valid(self, test_agent, test_library):
        """Ensure that b3 distributed tracing headers are extracted
        and injected properly.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [["b3", "000000000000000000000000075bcd15-000000003ade68b1-1"]]
            )

        span = find_only_span(test_agent.wait_for_num_traces(1))
        b3_arr = headers["b3"].split("-")
        b3_trace_id = b3_arr[0]
        b3_span_id = b3_arr[1]
        b3_sampling = b3_arr[2]

        assert len(b3_trace_id) == 16 or len(b3_trace_id) == 32
        assert int(b3_trace_id, base=16) == span.get("trace_id")
        assert int(b3_span_id, base=16) == span.get("span_id")
        assert len(b3_span_id) == 16
        assert b3_sampling == "1"
        assert span["meta"].get(ORIGIN) is None

    @enable_b3()
    @missing_feature(context.library > "ruby@1.99.0", reason="Missing for 2.x")
    @missing_feature(context.library == "cpp", reason="format of DD_TRACE_PROPAGATION_STYLE_EXTRACT not supported")
    @irrelevant(context.library > "python@2.20.0", reason="Deprecated in 3.x")
    def test_headers_b3_propagate_invalid(self, test_agent, test_library):
        """Ensure that invalid b3 distributed tracing headers are not extracted
        and the new span context is injected properly.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers([["b3", "0-0-1"]])

        span = find_only_span(test_agent.wait_for_num_traces(1))
        assert span.get("trace_id") != 0
        assert span.get("span_id") != 0

        b3_arr = headers["b3"].split("-")
        b3_trace_id = b3_arr[0]
        b3_span_id = b3_arr[1]
        b3_sampling = b3_arr[2]

        assert len(b3_trace_id) == 16 or len(b3_trace_id) == 32
        assert int(b3_trace_id[-16:], base=16) == span.get("trace_id")
        assert int(b3_span_id, base=16) == span.get("span_id")
        assert len(b3_span_id) == 16
        assert b3_sampling == "1" if span["metrics"].get(SAMPLING_PRIORITY_KEY) > 0 else "0"
        assert span["meta"].get(ORIGIN) is None

    @enable_b3_single_key()
    @missing_feature(context.library == "cpp", reason="format of DD_TRACE_PROPAGATION_STYLE_EXTRACT not supported")
    @missing_feature(
        context.library > "ruby@1.99.0",
        reason="Added DD_TRACE_PROPAGATION_STYLE config in version 1.8.0 but the name is no longer recognized in 2.x",
    )
    @irrelevant(context.library > "python@2.20.0", reason="Deprecated in 3.x")
    def test_headers_b3_single_key_propagate_valid(self, test_agent, test_library):
        self.test_headers_b3_propagate_valid(test_agent, test_library)

    @enable_migrated_b3()
    @missing_feature(context.library == "cpp", reason="Need to remove b3=b3multi alias")
    @missing_feature(context.library == "dotnet", reason="Need to remove b3=b3multi alias")
    @missing_feature(context.library == "golang", reason="Need to remove b3=b3multi alias")
    @missing_feature(context.library == "java", reason="Need to remove b3=b3multi alias")
    @missing_feature(context.library == "nodejs", reason="Need to remove b3=b3multi alias")
    @missing_feature(context.library == "php", reason="Need to remove b3=b3multi alias")
    def test_headers_b3_migrated_extract_valid(self, test_agent, test_library):
        self.test_headers_b3_extract_valid(test_agent, test_library)

    @enable_migrated_b3()
    @missing_feature(context.library == "cpp", reason="Need to remove b3=b3multi alias")
    @missing_feature(context.library == "golang", reason="Need to remove b3=b3multi alias")
    @missing_feature(context.library == "java", reason="Need to remove b3=b3multi alias")
    @missing_feature(context.library == "nodejs", reason="Need to remove b3=b3multi alias")
    @missing_feature(context.library == "php", reason="Need to remove b3=b3multi alias")
    def test_headers_b3_migrated_extract_invalid(self, test_agent, test_library):
        self.test_headers_b3_extract_invalid(test_agent, test_library)

    @enable_migrated_b3()
    @missing_feature(context.library == "cpp", reason="Need to remove b3=b3multi alias")
    @missing_feature(context.library == "dotnet", reason="Need to remove b3=b3multi alias")
    @missing_feature(context.library == "golang", reason="Need to remove b3=b3multi alias")
    @missing_feature(context.library == "java", reason="Need to remove b3=b3multi alias")
    @missing_feature(context.library == "nodejs", reason="Need to remove b3=b3multi alias")
    @missing_feature(context.library == "php", reason="Need to remove b3=b3multi alias")
    def test_headers_b3_migrated_inject_valid(self, test_agent, test_library):
        self.test_headers_b3_inject_valid(test_agent, test_library)

    @enable_migrated_b3()
    @missing_feature(context.library == "cpp", reason="Need to remove b3=b3multi alias")
    @missing_feature(context.library == "dotnet", reason="Need to remove b3=b3multi alias")
    @missing_feature(context.library == "golang", reason="Need to remove b3=b3multi alias")
    @missing_feature(context.library == "java", reason="Need to remove b3=b3multi alias")
    @missing_feature(context.library == "nodejs", reason="Need to remove b3=b3multi alias")
    @missing_feature(context.library == "php", reason="Need to remove b3=b3multi alias")
    def test_headers_b3_migrated_propagate_valid(self, test_agent, test_library):
        self.test_headers_b3_propagate_valid(test_agent, test_library)

    @enable_migrated_b3()
    @missing_feature(context.library == "cpp", reason="Need to remove b3=b3multi alias")
    @missing_feature(context.library == "dotnet", reason="Need to remove b3=b3multi alias")
    @missing_feature(context.library == "golang", reason="Need to remove b3=b3multi alias")
    @missing_feature(context.library == "java", reason="Need to remove b3=b3multi alias")
    @missing_feature(context.library == "nodejs", reason="Need to remove b3=b3multi alias")
    @missing_feature(context.library == "php", reason="Need to remove b3=b3multi alias")
    def test_headers_b3_migrated_propagate_invalid(self, test_agent, test_library):
        self.test_headers_b3_propagate_invalid(test_agent, test_library)

    @enable_migrated_b3_single_key()
    @missing_feature(context.library == "cpp", reason="Need to remove b3=b3multi alias")
    @missing_feature(context.library == "dotnet", reason="Need to remove b3=b3multi alias")
    @missing_feature(context.library == "golang", reason="Need to remove b3=b3multi alias")
    @missing_feature(context.library == "java", reason="Need to remove b3=b3multi alias")
    @missing_feature(context.library == "nodejs", reason="Need to remove b3=b3multi alias")
    @missing_feature(context.library == "php", reason="Need to remove b3=b3multi alias")
    @missing_feature(context.library < "ruby@1.8.0", reason="Added DD_TRACE_PROPAGATION_STYLE config in version 1.8.0")
    def test_headers_b3_migrated_single_key_propagate_valid(self, test_agent, test_library):
        self.test_headers_b3_propagate_valid(test_agent, test_library)
