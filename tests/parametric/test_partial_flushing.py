import pytest
from utils.docker_fixtures.spec.trace import find_first_span_in_trace_payload, find_span, find_trace
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI
from .conftest import APMLibrary


@features.partial_flush
@scenarios.parametric
class Test_Partial_Flushing:
    @pytest.mark.parametrize(
        "library_env", [{"DD_TRACE_PARTIAL_FLUSH_MIN_SPANS": "1", "DD_TRACE_PARTIAL_FLUSH_ENABLED": "true"}]
    )
    def test_partial_flushing_one_span(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Create a trace with a root span and a single child. Finish the child, and ensure
        partial flushing triggers. This test explicitly enables partial flushing.
        """
        self.do_partial_flush_test(test_agent, test_library)

    @pytest.mark.parametrize("library_env", [{"DD_TRACE_PARTIAL_FLUSH_MIN_SPANS": "1"}])
    def test_partial_flushing_one_span_default(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Create a trace with a root span and a single child. Finish the child, and ensure
        partial flushing triggers. This test assumes partial flushing is enabled by default.
        """
        self.do_partial_flush_test(test_agent, test_library)

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "true",
                "DD_TRACE_PARTIAL_FLUSH_MIN_SPANS": "2",
                "DD_TRACE_PARTIAL_FLUSH_ENABLED": "true",
                "DD_TRACE_SAMPLE_RATE": "1",
            }
        ],
    )
    def test_partial_flushing_propagation_tags(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Create a trace with a root span and two children. Finish the children, and ensure
        partial flushing places propagation tags on the first span in the chunk.
        """
        self.do_propagation_tags_test(test_agent, test_library)

    @pytest.mark.parametrize(
        "library_env", [{"DD_TRACE_PARTIAL_FLUSH_MIN_SPANS": "5", "DD_TRACE_PARTIAL_FLUSH_ENABLED": "true"}]
    )
    def test_partial_flushing_under_limit_one_payload(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Create a trace with a root span and a single child. Finish the child, and ensure
        partial flushing does NOT trigger, since the partial flushing min spans is set to 5.
        """
        self.no_partial_flush_test(test_agent, test_library)

    @pytest.mark.parametrize(
        "library_env", [{"DD_TRACE_PARTIAL_FLUSH_MIN_SPANS": "1", "DD_TRACE_PARTIAL_FLUSH_ENABLED": "false"}]
    )
    def test_partial_flushing_disabled(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Create a trace with a root span and a single child. Finish the child, and ensure
        partial flushing does NOT trigger, since it's explicitly disabled.
        """
        self.no_partial_flush_test(test_agent, test_library)

    def do_partial_flush_test(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Create a trace with a root span and a single child. Finish the child, and ensure
        partial flushing triggers.
        """
        with test_library, test_library.dd_start_span(name="root") as parent_span:
            with test_library.dd_start_span(name="child1", parent_id=parent_span.span_id) as child1:
                pass
            partial_traces = test_agent.wait_for_num_traces(1, clear=True, wait_loops=30)
            partial_trace = find_trace(partial_traces, parent_span.trace_id)
            assert len(partial_trace) == 1
            child_span = find_span(partial_trace, child1.span_id)
            assert child_span["name"] == "child1"
            # verify the partially flushed chunk has proper "trace level" tags
            assert child_span["metrics"]["_sampling_priority_v1"] == 1.0
            assert len(child_span["meta"]["_dd.p.tid"]) > 0
            assert len(child_span["meta"]["_dd.p.dm"]) > 0

        traces = test_agent.wait_for_num_traces(1, clear=True)
        full_trace = find_trace(traces, parent_span.trace_id)
        root_span = find_span(full_trace, parent_span.span_id)
        assert len(traces) == 1
        assert root_span["name"] == "root"

    def do_propagation_tags_test(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Create a trace with a root span and two children. Finish the children, and ensure
        partial flushing emits them in a chunk before the root.
        """
        with test_library, test_library.dd_start_span(name="root") as parent_span:
            child_span_ids: dict[str, int | str] = {}
            for child_name in ("child1", "child2"):
                with test_library.dd_start_span(name=child_name, parent_id=parent_span.span_id) as child_span:
                    child_span_ids[child_name] = child_span.span_id

            partial_traces = test_agent.wait_for_num_traces(1, clear=True, wait_loops=30, sort_by_start=False)
            partial_trace = find_trace(partial_traces, parent_span.trace_id)
            assert len(partial_trace) == 2
            for child_name, child_span_id in child_span_ids.items():
                assert find_span(partial_trace, child_span_id)["name"] == child_name

            first_span = find_first_span_in_trace_payload(partial_trace)
            assert first_span["metrics"]["_sampling_priority_v1"] == 2.0
            assert first_span["meta"]["_dd.p.tid"]
            assert first_span["meta"]["_dd.p.dm"] == "-3"
            for later_span in partial_trace[1:]:
                assert "_dd.p.dm" not in later_span.get("meta", {})

        traces = test_agent.wait_for_num_traces(1, clear=True, sort_by_start=False)
        full_trace = find_trace(traces, parent_span.trace_id)
        root_span = find_span(full_trace, parent_span.span_id)
        assert len(traces) == 1
        assert root_span["name"] == "root"
        assert root_span == find_first_span_in_trace_payload(full_trace)
        assert root_span["meta"]["_dd.p.tid"]
        assert root_span["meta"]["_dd.p.dm"] == "-3"

    def no_partial_flush_test(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Create a trace with a root span and one child. Finish the child, and ensure
        partial flushing does NOT trigger.
        """
        with test_library, test_library.dd_start_span(name="root") as parent_span:
            with test_library.dd_start_span(name="child1", parent_id=parent_span.span_id):
                pass
            try:
                partial_traces = test_agent.wait_for_num_traces(1, clear=True)
                assert partial_traces is None
            except ValueError:
                pass  # We expect there won't be a flush, so catch this exception
        traces = test_agent.wait_for_num_traces(1, clear=True)
        trace = find_trace(traces, parent_span.trace_id)
        assert len(traces) == 1
        root_span = find_span(trace, parent_span.span_id)
        assert root_span["name"] == "root"
