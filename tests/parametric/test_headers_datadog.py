import pytest

from utils.parametric.spec.trace import SAMPLING_PRIORITY_KEY, ORIGIN
from utils.parametric.spec.trace import span_has_no_parent
from utils.parametric.headers import make_single_request_and_get_inject_headers
from utils.parametric.test_agent import get_span
from utils import bug, context, scenarios


@scenarios.parametric
class Test_Headers_Datadog:
    def test_distributed_headers_extract_datadog_D001(self, test_agent, test_library):
        """Ensure that Datadog distributed tracing headers are extracted
        and activated properly.
        """
        with test_library:
            headers = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["x-datadog-trace-id", "123456789"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-sampling-priority", "2"],
                    ["x-datadog-origin", "synthetics;=web,z"],
                    ["x-datadog-tags", "_dd.p.dm=-4"],
                ],
            )

        span = get_span(test_agent)
        assert span.get("trace_id") == 123456789
        assert span.get("parent_id") == 987654321
        origin = span["meta"].get(ORIGIN)
        # allow implementations to split origin at the first ','
        assert origin == "synthetics;=web,z" or origin == "synthetics;=web"
        assert span["meta"].get("_dd.p.dm") == "-4"
        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == 2

    def test_distributed_headers_extract_datadog_invalid_D002(self, test_agent, test_library):
        """Ensure that invalid Datadog distributed tracing headers are not extracted.
        """
        with test_library:
            headers = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["x-datadog-trace-id", "0"],
                    ["x-datadog-parent-id", "0"],
                    ["x-datadog-sampling-priority", "2"],
                    ["x-datadog-origin", "synthetics"],
                    ["x-datadog-tags", "_dd.p.dm=-4"],
                ],
            )

        span = get_span(test_agent)
        assert span.get("trace_id") != 0
        assert span_has_no_parent(span)
        # assert span["meta"].get(ORIGIN) is None # TODO: Determine if we keep x-datadog-origin for an invalid trace-id/parent-id
        assert span["meta"].get("_dd.p.dm") != "-4"
        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) != 2

    def test_distributed_headers_inject_datadog_D003(self, test_agent, test_library):
        """Ensure that Datadog distributed tracing headers are injected properly.
        """
        with test_library:
            headers = make_single_request_and_get_inject_headers(test_library, [])

        span = get_span(test_agent)
        assert int(headers["x-datadog-trace-id"]) == span.get("trace_id")
        assert int(headers["x-datadog-parent-id"]) == span.get("span_id")
        assert int(headers["x-datadog-sampling-priority"]) == span["metrics"].get(SAMPLING_PRIORITY_KEY)

    def test_distributed_headers_propagate_datadog_D004(self, test_agent, test_library):
        """Ensure that Datadog distributed tracing headers are extracted
        and injected properly.
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
        assert headers["x-datadog-trace-id"] == "123456789"
        assert headers["x-datadog-parent-id"] != "987654321"
        assert headers["x-datadog-sampling-priority"] == "2"
        assert headers["x-datadog-origin"] == "synthetics"
        assert "_dd.p.dm=-4" in headers["x-datadog-tags"]

    def test_distributed_headers_extractandinject_datadog_invalid_D005(self, test_agent, test_library):
        """Ensure that invalid Datadog distributed tracing headers are not extracted
        and the new span context is injected properly.
        """
        with test_library:
            headers = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["x-datadog-trace-id", "0"],
                    ["x-datadog-parent-id", "0"],
                    ["x-datadog-sampling-priority", "2"],
                    ["x-datadog-origin", "synthetics"],
                    ["x-datadog-tags", "_dd.p.dm=-4"],
                ],
            )

        assert headers["x-datadog-trace-id"] != "0"
        assert headers["x-datadog-parent-id"] != "0"
        assert headers["x-datadog-sampling-priority"] != "2"
        # assert headers["x-datadog-origin"] == '' # TODO: Determine if we keep x-datadog-origin for an invalid trace-id/parent-id
        assert "_dd.p.dm=-4" not in headers["x-datadog-tags"]
