from utils.parametric.spec.trace import SAMPLING_PRIORITY_KEY, ORIGIN
from utils.parametric.spec.trace import span_has_no_parent
from utils.parametric.spec.trace import find_only_span
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI

from .conftest import APMLibrary


@features.datadog_headers_propagation
@scenarios.parametric
class Test_Headers_Datadog:
    def test_distributed_headers_extract_datadog_D001(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Ensure that Datadog distributed tracing headers are extracted
        and activated properly.
        """
        with test_library:
            test_library.dd_make_child_span_and_get_headers(
                [
                    ("x-datadog-trace-id", "123456789"),
                    ("x-datadog-parent-id", "987654321"),
                    ("x-datadog-sampling-priority", "2"),
                    ("x-datadog-origin", "synthetics;=web,z"),
                    ("x-datadog-tags", "_dd.p.dm=-4"),
                ],
            )

        span = find_only_span(test_agent.wait_for_num_traces(1))
        assert span.get("trace_id") == 123456789
        assert span.get("parent_id") == 987654321
        origin = span["meta"].get(ORIGIN)
        # allow implementations to split origin at the first ','
        assert origin in ("synthetics;=web,z", "synthetics;=web")
        assert span["meta"].get("_dd.p.dm") == "-4"
        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == 2

    def test_distributed_headers_extract_datadog_invalid_D002(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Ensure that invalid Datadog distributed tracing headers are not extracted."""
        with test_library:
            test_library.dd_make_child_span_and_get_headers(
                [
                    ("x-datadog-trace-id", "0"),
                    ("x-datadog-parent-id", "0"),
                    ("x-datadog-sampling-priority", "2"),
                    ("x-datadog-origin", "synthetics"),
                    ("x-datadog-tags", "_dd.p.dm=-4"),
                ],
            )

        span = find_only_span(test_agent.wait_for_num_traces(1))
        assert span.get("trace_id") != 0
        assert span_has_no_parent(span)
        # assert span["meta"].get(ORIGIN) is None # TODO: Determine if we keep x-datadog-origin for an invalid trace-id/parent-id
        assert span["meta"].get("_dd.p.dm") != "-4"
        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) != 2

    def test_distributed_headers_inject_datadog_D003(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Ensure that Datadog distributed tracing headers are injected properly."""
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers([])

        span = find_only_span(test_agent.wait_for_num_traces(1))
        assert int(headers["x-datadog-trace-id"]) == span.get("trace_id")
        assert int(headers["x-datadog-parent-id"]) == span.get("span_id")
        assert int(headers["x-datadog-sampling-priority"]) == span["metrics"].get(SAMPLING_PRIORITY_KEY)

    def test_distributed_headers_propagate_datadog_D004(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Ensure that Datadog distributed tracing headers are extracted
        and injected properly.
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

        find_only_span(test_agent.wait_for_num_traces(1))
        assert headers["x-datadog-trace-id"] == "123456789"
        assert headers["x-datadog-parent-id"] != "987654321"
        assert headers["x-datadog-sampling-priority"] == "2"
        assert headers["x-datadog-origin"] == "synthetics"
        assert "_dd.p.dm=-4" in headers["x-datadog-tags"]

    def test_distributed_headers_extractandinject_datadog_invalid_D005(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ):
        """Ensure that invalid Datadog distributed tracing headers are not extracted
        and the new span context is injected properly.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [
                    ("x-datadog-trace-id", "0"),
                    ("x-datadog-parent-id", "0"),
                    ("x-datadog-sampling-priority", "2"),
                    ("x-datadog-origin", "synthetics"),
                    ("x-datadog-tags", "_dd.p.dm=-4"),
                ],
            )

        assert headers["x-datadog-trace-id"] != "0"
        assert headers["x-datadog-parent-id"] != "0"
        assert headers["x-datadog-sampling-priority"] != "2"
        # assert headers["x-datadog-origin"] == '' # TODO: Determine if we keep x-datadog-origin for an invalid trace-id/parent-id
        assert "_dd.p.dm=-4" not in headers["x-datadog-tags"]
