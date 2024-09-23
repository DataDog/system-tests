from requests import head
from utils.parametric.spec.trace import SAMPLING_PRIORITY_KEY, ORIGIN
from utils.parametric.spec.trace import span_has_no_parent
from utils.parametric.headers import make_single_request_and_get_inject_headers
from utils.parametric.spec.trace import find_only_span
from utils import features, scenarios, bug, context
from typing import Any
import pytest
from utils.parametric.spec.trace import SAMPLING_PRIORITY_KEY, ORIGIN
from utils.parametric.headers import make_single_request_and_get_inject_headers
from utils.parametric.spec.trace import find_only_span
from utils import missing_feature, context, scenarios, features, bug

parametrize = pytest.mark.parametrize

import logging
logging.basicConfig(level=logging.INFO)  # or logging.WARNING, logging.ERROR to reduce verbosity


def disable_baggage() -> Any:
    env = {
        "DD_TRACE_PROPAGATION_STYLE": "datadog,tracecontext",
    }
    return parametrize("library_env", [env])


def only_baggage_enabled() -> Any:
    env = {
        "DD_TRACE_PROPAGATION_STYLE": "baggage",
    }
    return parametrize("library_env", [env])


@features.datadog_headers_propagation
@scenarios.parametric
class Test_Headers_Datadog:
    def test_distributed_headers_baggage_default_D001(self, test_agent, test_library):
        """Ensure baggage is enabled as a default setting and that it does not interfere with Datadog headers."""
        with test_library:
            headers = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["x-datadog-trace-id", "123456789"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-sampling-priority", "2"],
                    ["x-datadog-origin", "synthetics;=web,z"],
                    ["x-datadog-tags", "_dd.p.dm=-4"],
                    ["baggage", "foo=bar"],
                ],
            )

        span = find_only_span(test_agent.wait_for_num_traces(1))
        assert span.get("trace_id") == 123456789
        assert span.get("parent_id") == 987654321
        origin = span["meta"].get(ORIGIN)
        assert origin == "synthetics;=web,z" or origin == "synthetics;=web"
        assert span["meta"].get("_dd.p.dm") == "-4"
        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == 2
        assert any("baggage" in header for header in headers)
        assert headers["baggage"]=="foo=bar"

    @only_baggage_enabled()
    def test_distributed_headers_baggage_only_D002(self, test_library):
        """Ensure that only baggage headers are injected when baggage is the only enabled propagation style."""
        with test_library:
            headers = make_single_request_and_get_inject_headers(test_library, [["baggage", "foo=bar"]])

        assert "traceparent" not in headers
        assert "tracestate" not in headers
        assert "x-datadog-trace-id" not in headers
        assert "x-datadog-parent-id" not in headers
        assert "x-datadog-sampling-priority" not in headers
        assert "x-datadog-origin" not in headers
        assert "x-datadog-tags" not in headers
        assert "baggage" in headers
        assert headers["baggage"] == "foo=bar"

    @disable_baggage()
    def test_baggage_disable_settings_D003(self, test_agent, test_library):
        """Ensure that baggage headers are not injected when baggage is disabled and does not interfere with other headers."""
        with test_library:
            headers = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["x-datadog-trace-id", "123456789"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-sampling-priority", "2"],
                    ["x-datadog-origin", "synthetics"],
                    ["x-datadog-tags", "_dd.p.dm=-4"],
                    ["baggage", "foo=bar"],
                ],
            )

        span = find_only_span(test_agent.wait_for_num_traces(1))
        assert span.get("trace_id") == 123456789
        assert span.get("parent_id") == 987654321
        assert span["meta"].get(ORIGIN) == "synthetics"
        assert span["meta"].get("_dd.p.dm") == "-4"
        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == 2
        assert not any('baggage' in item for item in headers)

    def test_baggage_set_D005(self, test_agent, test_library):
        """Ensure that baggage headers are injected and appended properly when baggage is enabled."""
        with test_library:
            with test_library.start_span(name="test_baggage_set_D005") as span:
                span.set_baggage("foo", "bar")
                span.set_baggage("baz", "qux")
                span.set_baggage("userId", "Amélie")
                span.set_baggage("serverNode", "DF 28")

            headers = test_library.inject_headers(span.span_id)

        assert any("baggage" in header for header in headers)
        baggage_list = next((header for header in headers if header[0] == "baggage"), [])
        baggage_items = baggage_list[1].split(",")
        assert len(baggage_items) == 4
        assert "foo=bar" in baggage_items
        assert "baz=qux" in baggage_items
        assert "userId=Am%C3%A9lie" in baggage_items
        assert "serverNode=DF%2028" in baggage_items

    @disable_baggage()
    def test_baggage_set_disabled_D006(self, test_agent, test_library):
        """Ensure that baggage headers are not injected when baggage is disabled."""
        with test_library:
            with test_library.start_span(name="test_baggage_set_disabled_D006") as span:
                span.set_baggage("foo", "bar")
                span.set_baggage("baz", "qux")

            headers = test_library.inject_headers(span.span_id)

        assert not any('baggage' in item for item in headers)

    def test_baggage_get_all_D007(self, test_agent, test_library):
        """Ensure that baggage headers are extracted properly."""
        with test_library:
            with test_library.start_span(name="test_baggage_get_all_D007", service="unique-service", http_headers=[["baggage", "foo=bar,baz=qux,userId=Am%C3%A9lie,serverNode=DF%2028"]]
                ) as span:
                    baggage = span.get_baggage() 
                    assert baggage == {"foo": "bar", "baz": "qux", "userId": "Amélie", "serverNode": "DF 28"}

# # test all api fuctions (get, remove, remove_all)
#     def test_baggage_get_D008(self, test_agent)