import json

import pytest
from utils import flaky, scenarios
from utils.parametric.spec.trace import MANUAL_DROP_KEY  # noqa
from utils.parametric.spec.trace import MANUAL_KEEP_KEY  # noqa
from utils.parametric.spec.trace import SAMPLING_AGENT_PRIORITY_RATE  # noqa
from utils.parametric.spec.trace import SAMPLING_DECISION_MAKER_KEY  # noqa
from utils.parametric.spec.trace import SAMPLING_PRIORITY_KEY  # noqa
from utils.parametric.spec.trace import SAMPLING_RULE_PRIORITY_RATE  # noqa
from utils.parametric.spec.trace import Span  # noqa
from utils.parametric.spec.trace import find_span_in_traces  # noqa


@scenarios.parametric
class Test_Sampling_Span_Tags:
    @flaky(True, library="php", reason="I don't know")
    @flaky(True, library="cpp")
    @flaky(True, library="ruby")
    @pytest.mark.parametrize("library_env", [{"DD_TRACE_SAMPLE_RATE": 1}])
    def test_tags_child_dropped_sst001(self, test_agent, test_library):
        with test_library:
            with test_library.start_span(name="parent", service="webserver") as parent_span:
                with test_library.start_span(
                    name="child", service="webserver", parent_id=parent_span.span_id
                ) as child_span:
                    child_span.set_meta(MANUAL_DROP_KEY, None)

        traces = test_agent.wait_for_num_spans(2, clear=True)

        parent_span = find_span_in_traces(traces, Span(name="parent", service="webserver"))
        child_span = find_span_in_traces(traces, Span(name="child", service="webserver"))

        assert child_span["meta"].get(SAMPLING_DECISION_MAKER_KEY) is None
        assert parent_span["meta"].get(SAMPLING_DECISION_MAKER_KEY) == "-1"
        assert parent_span["metrics"].get(SAMPLING_PRIORITY_KEY) == 1
        assert parent_span["metrics"].get(SAMPLING_AGENT_PRIORITY_RATE) == 1

    @pytest.mark.parametrize("library_env", [{"DD_TRACE_SAMPLE_RATE": 1}])
    def test_tags_child_kept_sst007(self, test_agent, test_library):
        with test_library:
            with test_library.start_span(name="parent", service="webserver") as parent_span:
                with test_library.start_span(
                    name="child", service="webserver", parent_id=parent_span.span_id
                ) as child_span:
                    child_span.set_meta(MANUAL_KEEP_KEY, None)

        traces = test_agent.wait_for_num_spans(2, clear=True)

        parent_span = find_span_in_traces(traces, Span(name="parent", service="webserver"))
        child_span = find_span_in_traces(traces, Span(name="child", service="webserver"))

        assert child_span["meta"].get(SAMPLING_DECISION_MAKER_KEY) == "-3"
        assert parent_span["meta"].get(SAMPLING_DECISION_MAKER_KEY) == "-4"
        assert parent_span["metrics"].get(SAMPLING_PRIORITY_KEY) == 2
        assert parent_span["metrics"].get(SAMPLING_AGENT_PRIORITY_RATE) == 1

    def test_tags_defaults_sst002(self, test_agent, test_library):
        with test_library:
            with test_library.start_span(name="parent", service="webserver") as parent_span:
                with test_library.start_span(
                    name="child", service="webserver", parent_id=parent_span.span_id
                ) as child_span:
                    pass

        traces = test_agent.wait_for_num_spans(2, clear=True)

        parent_span = find_span_in_traces(traces, Span(name="parent", service="webserver"))
        child_span = find_span_in_traces(traces, Span(name="child", service="webserver"))

        assert child_span["meta"].get(SAMPLING_DECISION_MAKER_KEY) == "-0"
        assert parent_span["meta"].get(SAMPLING_DECISION_MAKER_KEY) == "-0"
        assert parent_span["metrics"].get(SAMPLING_PRIORITY_KEY) == 1
        assert parent_span["metrics"].get(SAMPLING_AGENT_PRIORITY_RATE) == 1

    @pytest.mark.parametrize("library_env", [{"DD_TRACE_SAMPLE_RATE": 1}])
    def test_tags_defaults_rate_1_sst003(self, test_agent, test_library):
        with test_library:
            with test_library.start_span(name="parent", service="webserver") as parent_span:
                with test_library.start_span(
                    name="child", service="webserver", parent_id=parent_span.span_id
                ) as child_span:
                    pass

        traces = test_agent.wait_for_num_spans(2, clear=True)

        parent_span = find_span_in_traces(traces, Span(name="parent", service="webserver"))
        child_span = find_span_in_traces(traces, Span(name="child", service="webserver"))

        assert child_span["meta"].get(SAMPLING_DECISION_MAKER_KEY) == "-3"
        assert parent_span["meta"].get(SAMPLING_DECISION_MAKER_KEY) == "-3"
        assert parent_span["metrics"].get(SAMPLING_PRIORITY_KEY) == 2
        assert parent_span["metrics"].get(SAMPLING_RULE_PRIORITY_RATE) == 1

    @pytest.mark.parametrize("library_env", [{"DD_TRACE_SAMPLE_RATE": 1e-06}])
    def test_tags_defaults_rate_tiny_sst004(self, test_agent, test_library):
        with test_library:
            with test_library.start_span(name="parent", service="webserver") as parent_span:
                with test_library.start_span(
                    name="child", service="webserver", parent_id=parent_span.span_id
                ) as child_span:
                    pass

        traces = test_agent.wait_for_num_spans(2, clear=True)

        parent_span = find_span_in_traces(traces, Span(name="parent", service="webserver"))
        child_span = find_span_in_traces(traces, Span(name="child", service="webserver"))

        assert child_span["meta"].get(SAMPLING_DECISION_MAKER_KEY) is None
        assert parent_span["meta"].get(SAMPLING_DECISION_MAKER_KEY) is None
        assert parent_span["metrics"].get(SAMPLING_PRIORITY_KEY) == -1
        assert parent_span["metrics"].get(SAMPLING_RULE_PRIORITY_RATE) == 1e-06

    @pytest.mark.parametrize(
        "library_env", [{"DD_TRACE_SAMPLE_RATE": 1, "DD_TRACE_SAMPLING_RULES": json.dumps([{"sample_rate": 1}])}]
    )
    def test_tags_defaults_rate_1_and_rule_1_sst005(self, test_agent, test_library):
        with test_library:
            with test_library.start_span(name="parent", service="webserver") as parent_span:
                with test_library.start_span(
                    name="child", service="webserver", parent_id=parent_span.span_id
                ) as child_span:
                    pass

        traces = test_agent.wait_for_num_spans(2, clear=True)

        parent_span = find_span_in_traces(traces, Span(name="parent", service="webserver"))
        child_span = find_span_in_traces(traces, Span(name="child", service="webserver"))

        assert child_span["meta"].get(SAMPLING_DECISION_MAKER_KEY) == "-3"
        assert parent_span["meta"].get(SAMPLING_DECISION_MAKER_KEY) == "-3"
        assert parent_span["metrics"].get(SAMPLING_PRIORITY_KEY) == 2
        assert parent_span["metrics"].get(SAMPLING_RULE_PRIORITY_RATE) == 1

    @pytest.mark.parametrize(
        "library_env", [{"DD_TRACE_SAMPLE_RATE": 1, "DD_TRACE_SAMPLING_RULES": json.dumps([{"sample_rate": 0}])}]
    )
    def test_tags_defaults_rate_1_and_rule_0_sst006(self, test_agent, test_library):
        with test_library:
            with test_library.start_span(name="parent", service="webserver") as parent_span:
                with test_library.start_span(
                    name="child", service="webserver", parent_id=parent_span.span_id
                ) as child_span:
                    pass

        traces = test_agent.wait_for_num_spans(2, clear=True)

        parent_span = find_span_in_traces(traces, Span(name="parent", service="webserver"))
        child_span = find_span_in_traces(traces, Span(name="child", service="webserver"))

        assert child_span["meta"].get(SAMPLING_DECISION_MAKER_KEY) is None
        assert parent_span["meta"].get(SAMPLING_DECISION_MAKER_KEY) is None
        assert parent_span["metrics"].get(SAMPLING_PRIORITY_KEY) == -1
        assert parent_span["metrics"].get(SAMPLING_RULE_PRIORITY_RATE) == 0
