import json

import pytest
from utils import bug, scenarios
from utils.parametric.spec.trace import MANUAL_DROP_KEY  # noqa
from utils.parametric.spec.trace import MANUAL_KEEP_KEY  # noqa
from utils.parametric.spec.trace import SAMPLING_AGENT_PRIORITY_RATE  # noqa
from utils.parametric.spec.trace import SAMPLING_DECISION_MAKER_KEY  # noqa
from utils.parametric.spec.trace import SAMPLING_PRIORITY_KEY  # noqa
from utils.parametric.spec.trace import SAMPLING_RULE_PRIORITY_RATE  # noqa
from utils.parametric.spec.trace import Span  # noqa
from utils.parametric.spec.trace import find_span_in_traces  # noqa


def _get_parent_and_child_span(test_agent, test_library):
    with test_library:
        with test_library.start_span(name="parent", service="webserver") as parent_span:
            with test_library.start_span(
                name="child", service="webserver", parent_id=parent_span.span_id
            ) as child_span:
                pass

    traces = test_agent.wait_for_num_spans(2, clear=True)

    parent_span = find_span_in_traces(traces, Span(name="parent", service="webserver"))
    child_span = find_span_in_traces(traces, Span(name="child", service="webserver"))
    return parent_span, child_span


def _assert_sampling_tags(parent_span, child_span, child_dm, parent_dm, parent_priority, parent_rate):
    if child_dm is not None or "meta" in child_span:
        assert child_span["meta"].get(SAMPLING_DECISION_MAKER_KEY) == child_dm
    if parent_dm is not None or "meta" in parent_span:
        assert parent_span["meta"].get(SAMPLING_DECISION_MAKER_KEY) == parent_dm
    assert parent_span["metrics"].get(SAMPLING_PRIORITY_KEY) == parent_priority
    assert parent_span["metrics"].get(SAMPLING_RULE_PRIORITY_RATE) == parent_rate


@scenarios.parametric
class Test_Sampling_Span_Tags:
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

        _assert_sampling_tags(parent_span, child_span, None, "-3", 1, 1)
        # golang: parent dm -3
        # python: child dm -3
        # java: parent dm -3
        # dotnet: parent dm -3
        # nodejs: parent dm None

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

        _assert_sampling_tags(parent_span, child_span, None, "-4", 2, 1)
        # golang: child dm None
        # php: child dm None
        # python: agent rate None
        # dotnet: child dm None
        # java: child dm None
        # nodejs: child dm None
        # ruby: child dm None
        # cpp: child dm None

    @bug(library="python", reason="Python sets dm tag on child span")
    def test_tags_defaults_sst002(self, test_agent, test_library):
        parent_span, child_span = _get_parent_and_child_span(test_agent, test_library)
        _assert_sampling_tags(parent_span, child_span, None, "-0", 1, 1)
        # golang: child dm None
        # php: child no tags
        # dotnet: child dm None
        # java: child dm None
        # nodejs: child dm None
        # ruby: child dm None
        # cpp: child dm None

    @pytest.mark.parametrize("library_env", [{"DD_TRACE_SAMPLE_RATE": 1}])
    @bug(library="python", reason="Python sets dm tag on child span")
    def test_tags_defaults_rate_1_sst003(self, test_agent, test_library):
        parent_span, child_span = _get_parent_and_child_span(test_agent, test_library)
        _assert_sampling_tags(parent_span, child_span, None, "-3", 2, 1)
        # golang: child dm None
        # php: child no tags
        # dotnet: child dm None
        # java: child dm None
        # nodejs: child dm None
        # ruby: child dm None
        # cpp: child dm None

    @pytest.mark.parametrize("library_env", [{"DD_TRACE_SAMPLE_RATE": 1e-06}])
    def test_tags_defaults_rate_tiny_sst004(self, test_agent, test_library):
        parent_span, child_span = _get_parent_and_child_span(test_agent, test_library)
        _assert_sampling_tags(parent_span, child_span, None, None, -1, 1e-06)
        # php: child no tags
        # dotnet: parent rate 9.99999
        # java: parent rate 9.99999

    @pytest.mark.parametrize(
        "library_env", [{"DD_TRACE_SAMPLE_RATE": 1, "DD_TRACE_SAMPLING_RULES": json.dumps([{"sample_rate": 1}])}]
    )
    @bug(library="python", reason="Python sets dm tag on child span")
    def test_tags_defaults_rate_1_and_rule_1_sst005(self, test_agent, test_library):
        parent_span, child_span = _get_parent_and_child_span(test_agent, test_library)
        _assert_sampling_tags(parent_span, child_span, None, "-3", 2, 1)
        # golang: child dm None
        # php: child no tags
        # dotnet: child dm None
        # java: child dm None
        # nodejs: child dm None
        # ruby: child dm None
        # cpp: child dm None

    @pytest.mark.parametrize(
        "library_env", [{"DD_TRACE_SAMPLE_RATE": 1, "DD_TRACE_SAMPLING_RULES": json.dumps([{"sample_rate": 0}])}]
    )
    def test_tags_defaults_rate_1_and_rule_0_sst006(self, test_agent, test_library):
        parent_span, child_span = _get_parent_and_child_span(test_agent, test_library)
        _assert_sampling_tags(parent_span, child_span, None, None, -1, 0)
        # golang: parent dm -3
        # php: child no tags
