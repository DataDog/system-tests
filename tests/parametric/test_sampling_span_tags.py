import json

import pytest
from utils import bug, scenarios  # noqa
from utils.parametric.spec.trace import MANUAL_DROP_KEY  # noqa
from utils.parametric.spec.trace import MANUAL_KEEP_KEY  # noqa
from utils.parametric.spec.trace import SAMPLING_AGENT_PRIORITY_RATE  # noqa
from utils.parametric.spec.trace import SAMPLING_DECISION_MAKER_KEY  # noqa
from utils.parametric.spec.trace import SAMPLING_LIMIT_PRIORITY_RATE  # noqa
from utils.parametric.spec.trace import SAMPLING_PRIORITY_KEY  # noqa
from utils.parametric.spec.trace import SAMPLING_RULE_PRIORITY_RATE  # noqa
from utils.parametric.spec.trace import Span  # noqa
from utils.parametric.spec.trace import find_span_in_traces  # noqa

UNSET = -420


def _get_spans(test_agent, test_library):
    with test_library:
        with test_library.start_span(name="parent", service="webserver") as ps:
            with test_library.start_span(name="child", service="webserver", parent_id=ps.span_id):
                pass

    traces = test_agent.wait_for_num_spans(2, clear=True)

    parent_span = find_span_in_traces(traces, Span(name="parent", service="webserver"))
    child_span = find_span_in_traces(traces, Span(name="child", service="webserver"))
    return parent_span, child_span, traces[0][0]


def _assert_sampling_tags(
    parent_span, child_span, first_span, dm, parent_priority, rule_rate=UNSET, agent_rate=UNSET, limit_rate=UNSET
):
    if dm is not None or "meta" in first_span:
        assert first_span["meta"].get(SAMPLING_DECISION_MAKER_KEY) == dm
    assert parent_span["metrics"].get(SAMPLING_PRIORITY_KEY) == parent_priority
    for rate_key, rate_expectation in (
        (SAMPLING_AGENT_PRIORITY_RATE, agent_rate),
        (SAMPLING_LIMIT_PRIORITY_RATE, limit_rate),
        (SAMPLING_RULE_PRIORITY_RATE, rule_rate),
    ):
        if rate_expectation != UNSET:
            assert parent_span["metrics"].get(rate_key) == rate_expectation
        else:
            assert rate_key not in parent_span["metrics"]
        assert rate_key not in child_span.get("metrics", {})
    if child_span != first_span:
        assert child_span.get("meta", {}).get(SAMPLING_DECISION_MAKER_KEY) is None


@scenarios.parametric
class Test_Sampling_Span_Tags:
    @bug(library="python", reason="Python sets dm tag on child span")
    @bug(library="python_http", reason="Python sets dm tag on child span")
    @bug(library="nodejs", reason="NodeJS does not set priority on parent span")
    @bug(library="ruby", reason="ruby does not set dm tag on first span")
    @bug(library="dotnet", reason="dotnet does not set dm tag on first span")
    @bug(library="golang", reason="golang sets priority 2")
    @bug(library="php", reason="php sets priority 2")
    @bug(library="cpp", reason="c++ does not support magic tags")
    @bug(library="java", reason="java sets dm tag -3")
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

        _assert_sampling_tags(parent_span, child_span, traces[0][0], "-4", -1)

    @bug(library="python", reason="Python sets dm tag on child span")
    @bug(library="python_http", reason="Python sets dm tag on child span")
    @bug(library="ruby", reason="ruby does not set dm tag on first span")
    @bug(library="dotnet", reason="dotnet does not set dm tag on first span")
    @bug(library="golang", reason="golang sets dm tag -3 on first span")
    @bug(library="php", reason="php sets dm tag -3 on first span")
    @bug(library="java", reason="java sets dm tag -3 on first span")
    @bug(library="cpp", reason="c++ sets dm tag -3 on first span")
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

        _assert_sampling_tags(parent_span, child_span, traces[0][0], "-4", 2)

    @bug(library="python", reason="Python sets dm tag -0")
    @bug(library="python_http", reason="Python sets dm tag -0")
    @bug(library="ruby", reason="ruby does not set dm tag on first span")
    @bug(library="dotnet", reason="dotnet does not set dm tag on first span")
    @bug(library="cpp", reason="unknown")
    @bug(library="php", reason="php does not set agent rate tag")
    @bug(library="nodejs", reason="nodejs sets dm tag -0")
    def test_tags_defaults_sst002(self, test_agent, test_library):
        parent_span, child_span, first_span = _get_spans(test_agent, test_library)
        _assert_sampling_tags(parent_span, child_span, first_span, "-1", 1, agent_rate=1)

    @bug(library="python", reason="Python sets dm tag on child span")
    @bug(library="python_http", reason="Python sets dm tag on child span")
    @bug(library="ruby", reason="ruby does not set dm tag on first span")
    @bug(library="dotnet", reason="dotnet does not set dm tag on first span")
    @bug(library="golang", reason="golang sets limit_psr")
    @bug(library="java", reason="java sets limit_psr")
    @bug(library="nodejs", reason="nodejs sets limit_psr")
    @bug(library="cpp", reason="c++ sets limit_psr")
    @pytest.mark.parametrize("library_env", [{"DD_TRACE_SAMPLE_RATE": 1}])
    def test_tags_defaults_rate_1_sst003(self, test_agent, test_library):
        parent_span, child_span, first_span = _get_spans(test_agent, test_library)
        _assert_sampling_tags(parent_span, child_span, first_span, "-3", 2, rule_rate=1)

    @bug(library="java", reason="Java sets rate tag 9.9999 on parent span")
    @bug(library="dotnet", reason="Dotnet sets rate tag 9.9999 on parent span")
    @bug(library="nodejs", reason="NodeJS does not set dm tag on first span")
    @bug(library="golang", reason="golang does not set dm tag on first span")
    @bug(library="python", reason="python does not set dm tag on first span")
    @bug(library="python_http", reason="python does not set dm tag on first span")
    @bug(library="ruby", reason="ruby does not set dm tag on first span")
    @bug(library="cpp", reason="c++ does not set dm tag on first span")
    @bug(library="php", reason="php sets dm tag -1 on first span")
    @pytest.mark.parametrize("library_env", [{"DD_TRACE_SAMPLE_RATE": 1e-06}])
    def test_tags_defaults_rate_tiny_sst004(self, test_agent, test_library):
        parent_span, child_span, first_span = _get_spans(test_agent, test_library)
        _assert_sampling_tags(parent_span, child_span, first_span, "-3", -1, rule_rate=1e-06)

    @bug(library="python", reason="Python sets dm tag on child span")
    @bug(library="python_http", reason="Python sets dm tag on child span")
    @bug(library="ruby", reason="ruby does not set dm tag on first span")
    @bug(library="dotnet", reason="dotnet does not set dm tag on first span")
    @bug(library="golang", reason="golang sets limit_psr")
    @bug(library="java", reason="java sets limit_psr")
    @bug(library="nodejs", reason="nodejs sets limit_psr")
    @bug(library="cpp", reason="c++ sets limit_psr")
    @pytest.mark.parametrize(
        "library_env", [{"DD_TRACE_SAMPLE_RATE": 1, "DD_TRACE_SAMPLING_RULES": json.dumps([{"sample_rate": 1}])}]
    )
    def test_tags_defaults_rate_1_and_rule_1_sst005(self, test_agent, test_library):
        parent_span, child_span, first_span = _get_spans(test_agent, test_library)
        _assert_sampling_tags(parent_span, child_span, first_span, "-3", 2, rule_rate=1)

    @bug(library="nodejs", reason="NodeJS does not set dm tag on first span")
    @bug(library="php", reason="php does not set dm tag on first span")
    @bug(library="ruby", reason="ruby does not set dm tag on first span")
    @bug(library="python", reason="python does not set dm tag on first span")
    @bug(library="python_http", reason="python does not set dm tag on first span")
    @bug(library="cpp", reason="c++ does not set dm tag on first span")
    @bug(library="java", reason="java does not set dm tag on first span")
    @bug(library="dotnet", reason="dotnet does not set dm tag on first span")
    @bug(library="golang", reason="golang sets priority tag 2")
    @pytest.mark.parametrize(
        "library_env", [{"DD_TRACE_SAMPLE_RATE": 1, "DD_TRACE_SAMPLING_RULES": json.dumps([{"sample_rate": 0}])}]
    )
    def test_tags_defaults_rate_1_and_rule_0_sst006(self, test_agent, test_library):
        parent_span, child_span, first_span = _get_spans(test_agent, test_library)
        _assert_sampling_tags(parent_span, child_span, first_span, "-3", -1, rule_rate=0)

    @bug(library="golang", reason="golang does not set dm tag")
    @bug(library="python", reason="python does not set dm tag")
    @bug(library="dotnet", reason="dotnet does not set dm tag")
    @bug(library="nodejs", reason="nodejs does not set dm tag")
    @bug(library="ruby", reason="ruby does not set dm tag")
    @pytest.mark.parametrize("library_env", [{"DD_TRACE_SAMPLE_RATE": 1, "DD_TRACE_RATE_LIMIT": 0}])
    def test_tags_defaults_rate_1_and_rate_limit_0_sst008(self, test_agent, test_library):
        parent_span, child_span, first_span = _get_spans(test_agent, test_library)
        _assert_sampling_tags(parent_span, child_span, first_span, "-3", 2, limit_rate=0, rule_rate=1)

    @bug(library="golang", reason="golang sets priority tag 2")
    @bug(library="php", reason="php does not set dm tag")
    @bug(library="python", reason="python does not set dm tag")
    @bug(library="dotnet", reason="dotnet does not set dm tag")
    @bug(library="java", reason="java does not set dm tag")
    @bug(library="nodejs", reason="nodejs does not set dm tag")
    @bug(library="ruby", reason="ruby does not set dm tag")
    @bug(library="cpp", reason="c++ does not set dm tag")
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TRACE_SAMPLE_RATE": 1,
                "DD_TRACE_RATE_LIMIT": 3,
                "DD_TRACE_SAMPLING_RULES": json.dumps([{"sample_rate": 0}]),
            }
        ],
    )
    def test_tags_defaults_rate_1_and_rate_limit_3_and_rule_0_sst009(self, test_agent, test_library):
        parent_span, child_span, first_span = _get_spans(test_agent, test_library)
        _assert_sampling_tags(parent_span, child_span, first_span, "-3", -1, limit_rate=3, rule_rate=1)

    @bug(library="golang", reason="golang sets dm tag -1")
    @bug(library="php", reason="php sets dm tag -1")
    @bug(library="python", reason="python sets dm tag -0")
    @bug(library="dotnet", reason="dotnet does not set dm tag")
    @bug(library="java", reason="java sets dm tag -1")
    @bug(library="nodejs", reason="nodejs sets dm tag -0")
    @bug(library="ruby", reason="ruby does not set dm tag")
    @bug(library="cpp", reason="c++ sets dm tag -0")
    @pytest.mark.parametrize(
        "library_env", [{"DD_TRACE_RATE_LIMIT": 3}],
    )
    def test_tags_defaults_rate_1_and_rate_limit_3_sst010(self, test_agent, test_library):
        parent_span, child_span, first_span = _get_spans(test_agent, test_library)
        _assert_sampling_tags(parent_span, child_span, first_span, "-3", 2, limit_rate=3)

    @bug(library="golang", reason="golang sets dm tag -1")
    @bug(library="php", reason="php sets dm tag -1")
    @bug(library="python", reason="python sets dm tag -0")
    @bug(library="dotnet", reason="dotnet does not set dm tag")
    @bug(library="java", reason="java sets dm tag -1")
    @bug(library="nodejs", reason="nodejs sets dm tag -0")
    @bug(library="ruby", reason="ruby does not set dm tag")
    @bug(library="cpp", reason="c++ sets dm tag -0")
    @pytest.mark.parametrize(
        "library_env", [{"DD_APPSEC_ENABLED": 1}],
    )
    def test_tags_appsec_enabled_sst011(self, test_agent, test_library):
        parent_span, child_span, first_span = _get_spans(test_agent, test_library)
        _assert_sampling_tags(parent_span, child_span, first_span, "-5", 2)
