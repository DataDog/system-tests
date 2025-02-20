import json

import pytest
from utils import bug, context, scenarios, features
from utils.parametric.spec.trace import MANUAL_DROP_KEY
from utils.parametric.spec.trace import MANUAL_KEEP_KEY
from utils.parametric.spec.trace import SAMPLING_AGENT_PRIORITY_RATE
from utils.parametric.spec.trace import SAMPLING_DECISION_MAKER_KEY
from utils.parametric.spec.trace import SAMPLING_LIMIT_PRIORITY_RATE
from utils.parametric.spec.trace import SAMPLING_PRIORITY_KEY
from utils.parametric.spec.trace import SAMPLING_RULE_PRIORITY_RATE
from utils.parametric.spec.trace import find_span_in_traces

UNSET = -420


class AnyRatio:
    def __eq__(self, other):
        return 0 <= other <= 1


def _get_spans(test_agent, test_library, child_span_tag=None):
    with test_library:
        with test_library.dd_start_span(name="parent", service="webserver") as ps:
            with test_library.dd_start_span(name="child", service="webserver", parent_id=ps.span_id) as cs:
                if child_span_tag:
                    cs.set_meta(child_span_tag, None)

    traces = test_agent.wait_for_num_spans(2, clear=True, sort_by_start=False)

    parent_span = find_span_in_traces(traces, ps.trace_id, ps.span_id)
    child_span = find_span_in_traces(traces, cs.trace_id, cs.span_id)
    return parent_span, child_span, traces[0][0]


def _assert_equal(elem_a, elem_b, description):
    if isinstance(elem_b, tuple):
        assert elem_a in elem_b, f"{description}\n{elem_a} not in {elem_b}"
    else:
        assert elem_a == elem_b, f"{description}\n{elem_a} != {elem_b}"


def _assert_sampling_tags(
    parent_span,
    child_span,
    first_span,
    dm,
    parent_priority,
    rule_rate=UNSET,
    agent_rate=UNSET,
    limit_rate=UNSET,
    description="",
):
    _assert_equal(first_span["meta"].get(SAMPLING_DECISION_MAKER_KEY), dm, description)
    _assert_equal(parent_span["metrics"].get(SAMPLING_PRIORITY_KEY), parent_priority, description)
    for rate_key, rate_expectation in (
        (SAMPLING_AGENT_PRIORITY_RATE, agent_rate),
        (SAMPLING_LIMIT_PRIORITY_RATE, limit_rate),
        (SAMPLING_RULE_PRIORITY_RATE, rule_rate),
    ):
        if rate_expectation != UNSET:
            _assert_equal(parent_span["metrics"].get(rate_key), rate_expectation, description)
        else:
            _assert_equal(parent_span.get("metrics", {}).get(rate_key), None, description=description)
        assert rate_key not in child_span.get("metrics", {}), "non-root spans should never include _dd.*_psr tags"
    if child_span != first_span:
        assert (
            child_span.get("meta", {}).get(SAMPLING_DECISION_MAKER_KEY) is None
        ), "non-root spans that are not first in a chunk should never includ the _dd.p.dm tag"


@scenarios.parametric
@features.trace_sampling
class Test_Sampling_Span_Tags:
    @bug(library="python", reason="APMAPI-737")  # Python sets dm tag on child span
    @bug(library="nodejs", reason="APMAPI-737")  # Node.js does not set priority on parent span
    @bug(library="ruby", reason="APMAPI-737")  # ruby does not set dm tag on first span
    @bug(library="dotnet", reason="APMAPI-737")  # dotnet does not set dm tag on first span
    @bug(library="golang", reason="APMAPI-737")  # golang sets priority 2
    @bug(library="php", reason="APMAPI-737")  # php sets priority 2
    @bug(library="java", reason="APMAPI-737")  # java sets priority 2
    @bug(library="cpp", reason="APMAPI-737")  # c++ does not support magic tags
    @bug(library="java", reason="APMAPI-737")  # java sets dm tag -3
    @pytest.mark.parametrize("library_env", [{"DD_TRACE_SAMPLE_RATE": 1}])
    def test_tags_child_dropped_sst001(self, test_agent, test_library):
        parent_span, child_span, first_span = _get_spans(test_agent, test_library, child_span_tag=MANUAL_DROP_KEY)
        _assert_sampling_tags(
            parent_span,
            child_span,
            first_span,
            "-4",
            -1,
            description="When the magic manual.drop tag is set, decisionmaker "
            "should be -4, priority should be -1, and no sample rate tags should "
            "be set",
        )

    @bug(library="python", reason="APMAPI-737")  # Python sets dm tag on child span
    @bug(library="ruby", reason="APMAPI-737")  # ruby does not set dm tag on first span
    @bug(library="dotnet", reason="APMAPI-737")  # dotnet does not set dm tag on first span
    @bug(library="golang", reason="APMAPI-737")  # golang sets dm tag -3 on first span
    @bug(library="php", reason="APMAPI-737")  # php sets dm tag -3 on first span
    @bug(library="java", reason="APMAPI-737")  # java sets dm tag -3 on first span
    @bug(library="cpp", reason="APMAPI-737")  # c++ sets dm tag -3 on first span
    @pytest.mark.parametrize("library_env", [{"DD_TRACE_SAMPLE_RATE": 1}])
    def test_tags_child_kept_sst007(self, test_agent, test_library):
        parent_span, child_span, first_span = _get_spans(test_agent, test_library, child_span_tag=MANUAL_KEEP_KEY)
        _assert_sampling_tags(
            parent_span,
            child_span,
            first_span,
            "-4",
            2,
            description="When the magic manual.keep tag is set, decisionmaker "
            "should be -4, priority should be -2, and no sample rate tags should "
            "be set",
        )

    @bug(library="python", reason="APMAPI-737")  # Python sets dm tag -0
    @bug(library="ruby", reason="APMAPI-737")  # ruby does not set dm tag on first span
    @bug(library="dotnet", reason="APMAPI-737")  # dotnet does not set dm tag on first span
    @bug(library="cpp", reason="APMAPI-737")  # unknown
    @bug(context.library < "nodejs@5.17.0", reason="APMAPI-737")  # APMRP-360  # actual fixed version is not known
    def test_tags_defaults_sst002(self, test_agent, test_library):
        parent_span, child_span, first_span = _get_spans(test_agent, test_library)
        _assert_sampling_tags(
            parent_span,
            child_span,
            first_span,
            ("-1", "-0"),
            1,
            agent_rate=(1, None),
            description="When no environment variables related to sampling or "
            "rate limiting are set, decisionmaker "
            "should be either -1 or -0, priority should be 1, and the agent sample rate tag should "
            "be either set to the default rate or unset",
        )

    @bug(library="python", reason="APMAPI-737")  # Python sets dm tag on child span
    @bug(library="ruby", reason="APMAPI-737")  # ruby does not set dm tag on first span
    @bug(library="dotnet", reason="APMAPI-737")  # dotnet does not set dm tag on first span
    @bug(library="golang", reason="APMAPI-737")  # golang sets limit_psr
    @bug(library="java", reason="APMAPI-737")  # java sets limit_psr
    @bug(library="nodejs", reason="APMAPI-737")  # nodejs sets limit_psr
    @bug(library="cpp", reason="APMAPI-737")  # c++ sets limit_psr
    @pytest.mark.parametrize("library_env", [{"DD_TRACE_SAMPLE_RATE": 1}])
    def test_tags_defaults_rate_1_sst003(self, test_agent, test_library):
        parent_span, child_span, first_span = _get_spans(test_agent, test_library)
        _assert_sampling_tags(
            parent_span,
            child_span,
            first_span,
            "-3",
            2,
            rule_rate=1,
            description="When DD_TRACE_SAMPLE_RATE=1 is set, decisionmaker "
            "should be -3, priority should be 2, and the rule sample rate tag should "
            "be set to the given rate, which is 1",
        )

    @bug(library="java", reason="APMAPI-737")  # Java sets rate tag 9.9999 on parent span
    @bug(library="dotnet", reason="APMAPI-737")  # .NET sets rate tag 9.9999 on parent span
    @bug(library="nodejs", reason="APMAPI-737")  # Node.js does not set dm tag on first span
    @bug(library="golang", reason="APMAPI-737")  # golang does not set dm tag on first span
    @bug(library="python", reason="APMAPI-737")  # python does not set dm tag on first span
    @bug(library="ruby", reason="APMAPI-737")  # ruby does not set dm tag on first span
    @bug(library="cpp", reason="APMAPI-737")  # c++ does not set dm tag on first span
    @bug(library="php", reason="APMAPI-737")  # php sets dm tag -1 on first span
    @pytest.mark.parametrize("library_env", [{"DD_TRACE_SAMPLE_RATE": 1e-06}])
    def test_tags_defaults_rate_tiny_sst004(self, test_agent, test_library):
        parent_span, child_span, first_span = _get_spans(test_agent, test_library)
        _assert_sampling_tags(
            parent_span,
            child_span,
            first_span,
            "-3",
            -1,
            rule_rate=1e-06,
            description="When DD_TRACE_SAMPLE_RATE=1 is set to a very small nonzero number, decisionmaker "
            "should be -3, priority should be -1, and the rule sample rate tag should "
            "be set to the given rate",
        )

    @bug(library="python", reason="APMAPI-737")  # Python sets dm tag on child span
    @bug(library="ruby", reason="APMAPI-737")  # ruby does not set dm tag on first span
    @bug(library="dotnet", reason="APMAPI-737")  # dotnet does not set dm tag on first span
    @bug(library="golang", reason="APMAPI-737")  # golang sets limit_psr
    @bug(library="java", reason="APMAPI-737")  # java sets limit_psr
    @bug(library="nodejs", reason="APMAPI-737")  # nodejs sets limit_psr
    @bug(library="cpp", reason="APMAPI-737")  # c++ sets limit_psr
    @pytest.mark.parametrize(
        "library_env", [{"DD_TRACE_SAMPLE_RATE": 1, "DD_TRACE_SAMPLING_RULES": json.dumps([{"sample_rate": 1}])}]
    )
    def test_tags_defaults_rate_1_and_rule_1_sst005(self, test_agent, test_library):
        parent_span, child_span, first_span = _get_spans(test_agent, test_library)
        _assert_sampling_tags(
            parent_span,
            child_span,
            first_span,
            "-3",
            2,
            rule_rate=1,
            description="When DD_TRACE_SAMPLE_RATE=1 is set and DD_TRACE_SAMPLING_RULES contains a single "
            "rule with sample_rate=1, decisionmaker "
            "should be -3, priority should be 2, and the rule sample rate tag should "
            "be set to the given rule rate, which is 1",
        )

    @bug(library="nodejs", reason="APMAPI-737")  # Node.js does not set dm tag on first span
    @bug(library="php", reason="APMAPI-737")  # php does not set dm tag on first span
    @bug(library="ruby", reason="APMAPI-737")  # ruby does not set dm tag on first span
    @bug(library="python", reason="APMAPI-737")  # python does not set dm tag on first span
    @bug(library="cpp", reason="APMAPI-737")  # c++ does not set dm tag on first span
    @bug(library="java", reason="APMAPI-737")  # java does not set dm tag on first span
    @bug(library="dotnet", reason="APMAPI-737")  # dotnet does not set dm tag on first span
    @bug(library="golang", reason="APMAPI-737")  # golang sets priority tag 2
    @pytest.mark.parametrize(
        "library_env", [{"DD_TRACE_SAMPLE_RATE": 1, "DD_TRACE_SAMPLING_RULES": json.dumps([{"sample_rate": 0}])}]
    )
    def test_tags_defaults_rate_1_and_rule_0_sst006(self, test_agent, test_library):
        parent_span, child_span, first_span = _get_spans(test_agent, test_library)
        _assert_sampling_tags(
            parent_span,
            child_span,
            first_span,
            "-3",
            -1,
            rule_rate=0,
            description="When DD_TRACE_SAMPLE_RATE=1 is set and DD_TRACE_SAMPLING_RULES contains a single "
            "rule with sample_rate=0, decisionmaker "
            "should be -3, priority should be -1, and the rule sample rate tag should "
            "be set to the given rule rate, which is 0",
        )

    @bug(library="golang", reason="APMAPI-737")  # golang does not set dm tag
    @bug(library="python", reason="APMAPI-737")  # python does not set dm tag
    @bug(library="dotnet", reason="APMAPI-737")  # dotnet does not set dm tag
    @bug(library="nodejs", reason="APMAPI-737")  # nodejs does not set dm tag
    @bug(library="ruby", reason="APMAPI-737")  # ruby does not set dm tag
    @bug(library="php", reason="APMAPI-737")  # php does not set limit_psr
    @bug(library="cpp", reason="APMAPI-737")  # this test times out with the c++ tracer
    @pytest.mark.parametrize("library_env", [{"DD_TRACE_SAMPLE_RATE": 1, "DD_TRACE_RATE_LIMIT": 0}])
    def test_tags_defaults_rate_1_and_rate_limit_0_sst008(self, test_agent, test_library):
        parent_span, child_span, first_span = _get_spans(test_agent, test_library)
        _assert_sampling_tags(
            parent_span,
            child_span,
            first_span,
            "-3",
            2,
            limit_rate=AnyRatio(),
            rule_rate=1,
            description="When DD_TRACE_SAMPLE_RATE=1 is set and DD_TRACE_RATE_LIMIT=0 is set, "
            "decisionmaker should be -3, priority should be 2, the rule sample rate tag should "
            "be set to the given sample rate (1), and the limit sample rate tag should be set ",
        )

    @bug(library="golang", reason="APMAPI-737")  # golang sets priority tag 2
    @bug(library="php", reason="APMAPI-737")  # php does not set dm tag
    @bug(library="python", reason="APMAPI-737")  # python does not set dm tag
    @bug(library="dotnet", reason="APMAPI-737")  # dotnet does not set dm tag
    @bug(library="java", reason="APMAPI-737")  # java does not set dm tag
    @bug(library="nodejs", reason="APMAPI-737")  # nodejs does not set dm tag
    @bug(library="ruby", reason="APMAPI-737")  # ruby does not set dm tag
    @bug(library="cpp", reason="APMAPI-737")  # c++ does not set dm tag
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
        _assert_sampling_tags(
            parent_span,
            child_span,
            first_span,
            "-3",
            -1,
            limit_rate=AnyRatio(),
            rule_rate=0,
            description="When DD_TRACE_SAMPLE_RATE=1 is set and DD_TRACE_RATE_LIMIT=3 is set and "
            "DD_TRACE_SAMPLING_RULES contains a single rule with sample_rate=0, "
            "decisionmaker should be -3, priority should be -1, the rule sample rate tag should "
            "be set to the given sample rate (0), and the limit sample rate tag should be set",
        )

    @bug(library="golang", reason="APMAPI-737")  # golang sets dm tag -1
    @bug(library="php", reason="APMAPI-737")  # php sets dm tag -1
    @bug(library="python", reason="APMAPI-737")  # python does not set dm tag
    @bug(library="dotnet", reason="APMAPI-737")  # dotnet does not set dm tag
    @bug(library="java", reason="APMAPI-737")  # java sets dm tag -1
    @bug(library="nodejs", reason="APMAPI-737")  # nodejs sets dm tag -0
    @bug(library="ruby", reason="APMAPI-737")  # ruby does not set dm tag
    @bug(library="cpp", reason="APMAPI-737")  # c++ sets dm tag -0
    @pytest.mark.parametrize("library_env", [{"DD_TRACE_RATE_LIMIT": 3}])
    def test_tags_defaults_rate_1_and_rate_limit_3_sst010(self, test_agent, test_library):
        parent_span, child_span, first_span = _get_spans(test_agent, test_library)
        _assert_sampling_tags(
            parent_span,
            child_span,
            first_span,
            "-3",
            2,
            limit_rate=AnyRatio(),
            description="When DD_TRACE_RATE_LIMIT=3 is set, "
            "decisionmaker should be -3, priority should be 2, "
            "and the limit sample rate tag should be set",
        )

    @bug(library="golang", reason="APMAPI-737")  # golang sets dm tag -1
    @bug(library="php", reason="APMAPI-737")  # php sets dm tag -1
    @bug(library="python", reason="APMAPI-737")  # python does not set dm tag
    @bug(library="dotnet", reason="APMAPI-737")  # dotnet does not set dm tag
    @bug(library="java", reason="APMAPI-737")  # java sets dm tag -1
    @bug(library="nodejs", reason="APMAPI-737")  # nodejs sets dm tag -0
    @bug(library="ruby", reason="APMAPI-737")  # ruby does not set dm tag
    @bug(library="cpp", reason="APMAPI-737")  # c++ sets dm tag -0
    @pytest.mark.parametrize("library_env", [{"DD_APPSEC_ENABLED": 1}])
    def test_tags_appsec_enabled_sst011(self, test_agent, test_library):
        parent_span, child_span, first_span = _get_spans(test_agent, test_library)
        _assert_sampling_tags(
            parent_span,
            child_span,
            first_span,
            "-5",
            2,
            agent_rate=1,
            description="When DD_APPSEC_ENABLED=1 is set, "
            "decisionmaker should be -5, priority should be 2, "
            "and the agent sample rate tag should be set to the default rate, which is 1",
        )
