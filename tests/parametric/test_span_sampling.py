import time
import json
import pytest
from utils.parametric.spec.trace import SAMPLING_PRIORITY_KEY
from utils.parametric.spec.trace import SINGLE_SPAN_SAMPLING_MAX_PER_SEC
from utils.parametric.spec.trace import SINGLE_SPAN_SAMPLING_MECHANISM
from utils.parametric.spec.trace import SINGLE_SPAN_SAMPLING_MECHANISM_VALUE
from utils.parametric.spec.trace import SINGLE_SPAN_SAMPLING_RATE
from utils.parametric.spec.trace import MANUAL_DROP_KEY
from utils.parametric.spec.trace import USER_KEEP
from utils.parametric.spec.trace import find_span_in_traces, find_trace, find_span, find_first_span_in_trace_payload
from utils import missing_feature, context, scenarios, features, flaky, bug


@features.single_span_sampling
@scenarios.parametric
class Test_Span_Sampling:
    @missing_feature(context.library == "ruby", reason="Issue: _dd.span_sampling.max_per_second is always set in Ruby")
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_SPAN_SAMPLING_RULES": json.dumps([{"service": "webserver", "name": "web.request"}]),
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": '[{"sample_rate":0}]',
            }
        ],
    )
    def test_single_rule_match_span_sampling_sss001(self, test_agent, test_library):
        """Test that span sampling tags are added when both:
        1. a span sampling rule matches
        2. tracer is set to drop the trace manually
        """
        with test_library, test_library.dd_start_span(name="web.request", service="webserver") as span:
            pass
        span = find_span_in_traces(test_agent.wait_for_num_traces(1), span.trace_id, span.span_id)

        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) == 1.0
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == SINGLE_SPAN_SAMPLING_MECHANISM_VALUE
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) is None

    @missing_feature(context.library == "ruby", reason="Issue: _dd.span_sampling.max_per_second is always set in Ruby")
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_SPAN_SAMPLING_RULES": json.dumps([{"service": "webse*", "name": "web.re?uest"}]),
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": '[{"sample_rate":0}]',
            }
        ],
    )
    def test_special_glob_characters_span_sampling_sss002(self, test_agent, test_library):
        """Test span sampling tags are added when a rule with glob patterns with special characters * and ? match"""
        with test_library, test_library.dd_start_span(name="web.request", service="webserver") as span:
            pass

        span = find_span_in_traces(test_agent.wait_for_num_traces(1), span.trace_id, span.span_id)
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) == 1.0
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == SINGLE_SPAN_SAMPLING_MECHANISM_VALUE
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) is None

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_SPAN_SAMPLING_RULES": json.dumps([{"service": "notmatching", "name": "notmatching"}]),
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": '[{"sample_rate":0}]',
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "false",
            }
        ],
    )
    def test_single_rule_no_match_span_sampling_sss003(self, test_agent, test_library):
        """Test span sampling tags are not added when both:
        1. a basic span sampling rule does not match
        2. the tracer is set to drop the span manually
        """
        with test_library, test_library.dd_start_span(name="web.request", service="webserver") as span:
            pass
        span = find_span_in_traces(test_agent.wait_for_num_traces(1), span.trace_id, span.span_id)

        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) is None
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) is None
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) is None

    @missing_feature(context.library == "ruby", reason="Issue: _dd.span_sampling.max_per_second is always set in Ruby")
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_SPAN_SAMPLING_RULES": json.dumps([{"service": "webserver"}]),
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": '[{"sample_rate":0}]',
            }
        ],
    )
    def test_single_rule_only_service_pattern_match_span_sampling_sss004(self, test_agent, test_library):
        """Test span sampling tags are added when both:
        1. a span sampling rule that only has a service pattern matches
        2. the tracer is set to drop the span manually
        """
        with test_library, test_library.dd_start_span(name="web.request", service="webserver") as span:
            pass
        span = find_span_in_traces(test_agent.wait_for_num_traces(1), span.trace_id, span.span_id)
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) == 1.0
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == SINGLE_SPAN_SAMPLING_MECHANISM_VALUE
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) is None

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_SPAN_SAMPLING_RULES": json.dumps([{"name": "no_match"}]),
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": '[{"sample_rate":0}]',
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "false",
            }
        ],
    )
    def test_single_rule_only_name_pattern_no_match_span_sampling_sss005(self, test_agent, test_library):
        """Test span sampling tags are not added when:
        1. a span sampling rule that only has a name pattern does not match
        2. the tracer is set to drop the span manually
        """
        with test_library, test_library.dd_start_span(name="web.request", service="webserver") as span:
            pass
        span = find_span_in_traces(test_agent.wait_for_num_traces(1), span.trace_id, span.span_id)
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) is None
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) is None
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) is None

    @missing_feature(context.library == "ruby", reason="Issue: _dd.span_sampling.max_per_second is always set in Ruby")
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_SPAN_SAMPLING_RULES": json.dumps(
                    [
                        {"service": "webserver", "name": "web.request"},
                        {"service": "webserver", "name": "web.request", "sample_rate": 0},
                    ]
                ),
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": '[{"sample_rate":0}]',
            }
        ],
    )
    def test_multi_rule_keep_drop_span_sampling_sss006(self, test_agent, test_library):
        """Test span sampling tags are added when the following are true:
        1. the first span sampling rule matches and keeps
        2. the second rule matches and drops due to sample rate
        3. the tracer is set to drop the span manually

        We're essentially testing that:
        1. rules are assessed in order of their listing
        2. that once a rule is matched, we do not try to match against further rules. We do this by assuming that the "sample_rate": 0 of the second rule, if matched against would cause the span to not have span sampling tags.
        """
        with test_library, test_library.dd_start_span(name="web.request", service="webserver") as span:
            pass
        span = find_span_in_traces(test_agent.wait_for_num_traces(1), span.trace_id, span.span_id)
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) == 1.0
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == SINGLE_SPAN_SAMPLING_MECHANISM_VALUE
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) is None

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_SPAN_SAMPLING_RULES": json.dumps(
                    [
                        {"service": "webserver", "name": "web.request", "sample_rate": 0},
                        {"service": "webserver", "name": "web.request"},
                    ]
                ),
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": '[{"sample_rate":0}]',
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "false",
            }
        ],
    )
    def test_multi_rule_drop_keep_span_sampling_sss007(self, test_agent, test_library):
        """Test span sampling tags are not added when both:
        1. the first span sampling rule matches and drops due to sample rate
        2. the second rule matches and keeps
        3. the tracer is set to drop the span manually

        We're essentially testing that:
        1. rules are assessed in order of their listing
        2. that once a rule is matched, we do not try to match against further rules. We do this by assuming that the "sample_rate": 0 of the first rule, will cause the span to not have span sampling tags.
        """
        with test_library, test_library.dd_start_span(name="web.request", service="webserver") as span:
            pass
        span = find_span_in_traces(test_agent.wait_for_num_traces(1), span.trace_id, span.span_id)
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) is None
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) is None
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) is None

    @missing_feature(
        context.library == "php",
        reason="PHP uses a float to represent the allowance in tokens and thus accepts one more request (given the time elapsed between individual requests)",
    )
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_SPAN_SAMPLING_RULES": json.dumps(
                    [{"service": "webserver", "name": "web.request", "max_per_second": 2}]
                ),
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": '[{"sample_rate":0}]',
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "false",
            }
        ],
    )
    @flaky(library="java", reason="APMAPI-978")
    @bug(library="cpp", reason="APMAPI-1052")
    def test_single_rule_rate_limiter_span_sampling_sss008(self, test_agent, test_library):
        """Test span sampling tags are added until rate limit hit, then need to wait for tokens to reset"""
        # generate three traces before requesting them to avoid timing issues
        trace_span_ids = []
        with test_library:
            for _ in range(6):
                with test_library.dd_start_span(name="web.request", service="webserver") as s1:
                    pass
                trace_span_ids.append((s1.trace_id, s1.span_id))

        traces = test_agent.wait_for_num_traces(6, clear=True)

        # expect first and second traces sampled
        span = find_span_in_traces(traces[:1], trace_span_ids[0][0], trace_span_ids[0][1])
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) == 1.0
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == 8
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) == 2

        span = find_span_in_traces(traces[1:2], trace_span_ids[1][0], trace_span_ids[1][1])
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == 8
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) == 2
        # Some issues related with timming. It's difficult to be so accurate and it can cause flakiness
        # For example code in the Java tracer starts the clock as soon as the limiter is created.
        # This means that even though all traces happen within ~59 ms, they could straddle two token buckets and hence all be allowed to pass
        # Given 6 traces, at least the last two traces are unsampled because of rate limiters
        span = find_span_in_traces(traces[5:6], trace_span_ids[5][0], trace_span_ids[5][1])
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) is None
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) is None
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) is None

        # wait a second for rate limiter tokens to replenish
        time.sleep(2)
        # now span should be kept by rule
        with test_library, test_library.dd_start_span(name="web.request", service="webserver") as s2:
            pass
        span = find_span_in_traces(test_agent.wait_for_num_traces(1, clear=True), s2.trace_id, s2.span_id)
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) == 1.0
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == 8
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) == 2

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_SPAN_SAMPLING_RULES": json.dumps(
                    [{"service": "webserver", "name": "web.request", "sample_rate": 0.5}]
                ),
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": '[{"sample_rate":0}]',
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "false",
            }
        ],
    )
    def test_sampling_rate_not_absolute_value_sss009(self, test_agent, test_library):
        """Test sample rate comes close to expected number of spans sampled. We do this by setting the
        sample_rate to 0.5, and then making sure that about half of the spans have span sampling tags and
        half do not.
        """
        # make 100 new traces, each with one span
        for _ in range(100):
            with test_library, test_library.dd_start_span(name="web.request", service="webserver"):
                pass
        traces = test_agent.wait_for_num_traces(num=100)
        assert len(traces) == 100
        sampled = []
        unsampled = []

        for trace in traces:
            span = find_first_span_in_trace_payload(trace)
            if span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == SINGLE_SPAN_SAMPLING_MECHANISM_VALUE:
                sampled.append(trace)
            else:
                unsampled.append(trace)

        assert len(sampled) in range(30, 70)
        assert len(unsampled) in range(30, 70)

    @missing_feature(context.library == "cpp", reason="cpp has not implemented stats computation yet")
    @missing_feature(
        context.library == "*",
        reason="this has to be implemented by a lot of the tracers and we need to do a bit of work on the assert",
    )
    @missing_feature(
        library="golang",
        reason="this has to be implemented by a lot of the tracers and we need to do a bit of work on the assert",
    )
    @missing_feature(
        library="nodejs",
        reason="this has to be implemented by a lot of the tracers and we need to do a bit of work on the assert",
    )
    @missing_feature(
        library="python",
        reason="this has to be implemented by a lot of the tracers and we need to do a bit of work on the assert",
    )
    @missing_feature(
        library="php",
        reason="this has to be implemented by a lot of the tracers and we need to do a bit of work on the assert",
    )
    @missing_feature(
        library="ruby",
        reason="this has to be implemented by a lot of the tracers and we need to do a bit of work on the assert",
    )
    @missing_feature(
        library="java",
        reason="this has to be implemented by a lot of the tracers and we need to do a bit of work on the assert",
    )
    @missing_feature(
        library="dotnet",
        reason="this has to be implemented by a lot of the tracers and we need to do a bit of work on the assert",
    )
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_SPAN_SAMPLING_RULES": json.dumps([{"service": "webserver", "name": "web.request"}]),
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": '[{"sample_rate":0}]',
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "True",
            }
        ],
    )
    def test_keep_span_with_stats_computation_sss010(self, test_agent, test_library):
        """Test when stats computation is enabled and span sampling applied, spans have manual_keep and still sent."""
        with test_library, test_library.dd_start_span(name="web.request", service="webserver") as s1:
            pass
        span = find_span_in_traces(test_agent.wait_for_num_traces(1), s1.trace_id, s1.span_id)
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) == 1.0
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == SINGLE_SPAN_SAMPLING_MECHANISM_VALUE
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) is None
        # We should be setting sampling priority to manual keep so the agent sampler won't be affected
        # TODO: we need a way to check that the chunk that contains the span was associated with USER_KEEP priority,
        # the below does not apply to all agent APIs
        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == USER_KEEP

    @missing_feature(context.library == "cpp", reason="manual.drop span tag is not applied")
    @missing_feature(
        context.library == "golang", reason="The Go tracer does not have a way to modulate trace sampling once started"
    )
    @missing_feature(context.library == "ruby", reason="Issue: does not respect manual.drop or manual.keep span tags")
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_SPAN_SAMPLING_RULES": json.dumps(
                    [{"service": "webserver", "name": "web.request", "sample_rate": 1.0}]
                ),
                "DD_TRACE_SAMPLE_RATE": 1.0,
                "DD_TRACE_SAMPLING_RULES": '[{"sample_rate":1.0}]',
            }
        ],
    )
    def test_single_rule_always_keep_span_sampling_sss011(self, test_agent, test_library):
        """Test that spans are always kept when the sampling rule matches and has sample_rate:1.0 regardless of tracer decision.

        Basically, if we have a rule for spans with sample_rate:1.0 we should always keep those spans, either due to trace sampling or span sampling
        """
        # This span is set to be dropped by the tracer/user, however it is kept by span sampling
        with test_library, test_library.dd_start_span(name="web.request", service="webserver") as s1:
            s1.set_meta(MANUAL_DROP_KEY, "1")
        span = find_span_in_traces(test_agent.wait_for_num_traces(1, clear=True), s1.trace_id, s1.span_id)
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) == 1.0
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == SINGLE_SPAN_SAMPLING_MECHANISM_VALUE
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) is None

        # This span is sampled by the tracer, not span sampling.
        # Therefore it won't have the span sampling tags, but rather the trace sampling tags.
        with test_library, test_library.dd_start_span(name="web.request", service="webserver") as s2:
            pass
        span = find_span_in_traces(test_agent.wait_for_num_traces(1, clear=True), s2.trace_id, s2.span_id)

        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) is None
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) is None
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) is None
        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) > 0

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_SPAN_SAMPLING_RULES": json.dumps(
                    [{"service": "webserver", "name": "web.request", "sample_rate": 0}]
                ),
                "DD_TRACE_SAMPLE_RATE": 1.0,
                "DD_TRACE_SAMPLING_RULES": '[{"sample_rate":1.0}]',
            }
        ],
    )
    def test_single_rule_tracer_always_keep_span_sampling_sss012(self, test_agent, test_library):
        """Test spans are always kept when tracer keeps, regardless of span sampling rule set to drop.

        We're essentially testing to make sure that the span sampling rule cannot control the fate of the span if the span is already being kept by trace sampling.
        """
        # This span is sampled by the tracer, not span sampling, which would try to drop the span, so it's still kept because "_sampling_priority_v1" > 0
        # When the trace is kept by trace sampling, span rules are not applied
        with test_library, test_library.dd_start_span(name="web.request", service="webserver") as s1:
            pass
        span = find_span_in_traces(test_agent.wait_for_num_traces(1), s1.trace_id, s1.span_id)

        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) is None
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) is None
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) is None
        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) > 0

    @missing_feature(
        context.library == "php",
        reason="PHP uses a float to represent the allowance in tokens and thus accepts one more request (given the time elapsed between individual requests)",
    )
    @flaky(library="cpp", reason="APMAPI-933")
    @flaky(library="java", reason="APMAPI-978")
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_SPAN_SAMPLING_RULES": json.dumps(
                    [
                        {"service": "webserver", "name": "web.request", "max_per_second": 1},
                        {"service": "webserver2", "name": "web.request2", "max_per_second": 2},
                    ]
                ),
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": '[{"sample_rate":0}]',
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "false",
            }
        ],
    )
    def test_multi_rule_independent_rate_limiters_sss013(self, test_agent, test_library):
        """Span rule rate limiters are per-rule.  So, spans that match different rules don't share a limiter, but
        multiple traces whose spans match the same rule do share a limiter.
        """
        # generate spans before requesting them to avoid timing issues
        trace_and_span_ids = []
        with test_library:
            for _ in range(4):
                with test_library.dd_start_span(name="web.request", service="webserver") as s1:
                    pass
                trace_and_span_ids.append((s1.trace_id, s1.span_id))
            for _ in range(6):
                with test_library.dd_start_span(name="web.request2", service="webserver2") as s2:
                    pass
                trace_and_span_ids.append((s2.trace_id, s2.span_id))

        traces = test_agent.wait_for_num_traces(10, clear=True)
        # Some issues related with timing. It's difficult to be so accurate and it can cause flakiness
        # We check at least last trace is unsampled
        span = find_span_in_traces(traces[:1], trace_and_span_ids[0][0], trace_and_span_ids[0][1])
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) == 1.0
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == SINGLE_SPAN_SAMPLING_MECHANISM_VALUE
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) == 1

        span = find_span_in_traces(traces[3:4], trace_and_span_ids[3][0], trace_and_span_ids[3][1])
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) is None
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) is None
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) is None

        # for trace in traces[4:10]:
        span = find_span_in_traces(traces[4:5], trace_and_span_ids[4][0], trace_and_span_ids[4][1])
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) == 1.0
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == SINGLE_SPAN_SAMPLING_MECHANISM_VALUE
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) == 2

        span = find_span_in_traces(traces[5:6], trace_and_span_ids[5][0], trace_and_span_ids[5][1])
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) == 1.0
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == SINGLE_SPAN_SAMPLING_MECHANISM_VALUE
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) == 2

        span = find_span_in_traces(traces[8:9], trace_and_span_ids[8][0], trace_and_span_ids[8][1])
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) is None
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) is None
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) is None

        # wait a couple of seconds for rate limiter tokens
        time.sleep(2)
        # Now span should be kept by first rule
        with test_library, test_library.dd_start_span(name="web.request", service="webserver") as s3:
            pass
        span = find_span_in_traces(test_agent.wait_for_num_traces(1), s3.trace_id, s3.span_id)
        assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) == 1

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_SPAN_SAMPLING_RULES": json.dumps(
                    [{"service": "webserver", "name": "parent", "sample_rate": 1.0, "max_per_second": 50}]
                ),
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": '[{"sample_rate":0}]',
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "false",
            }
        ],
    )
    def test_root_span_selected_by_sss014(self, test_agent, test_library):
        """Single spans selected by SSS must be kept and shouldn't affect child span sampling priority.

        We're essentially testing to make sure that the span sampling rule keeps selected spans regardless of the trace sampling decision
        and doesn't affect child spans that are dropped by the tracer sampling mechanism.
        """
        with (
            test_library,
            test_library.dd_start_span(name="parent", service="webserver") as ps,
            test_library.dd_start_span(name="child", service="webserver", parent_id=ps.span_id) as cs,
        ):
            pass

        traces = test_agent.wait_for_num_spans(2, clear=True)

        parent_span = find_span_in_traces(traces, ps.trace_id, ps.span_id)
        child_span = find_span_in_traces(traces, cs.trace_id, cs.span_id)

        # the trace should be dropped, so the parent span priority is set to -1
        assert parent_span["metrics"].get(SAMPLING_PRIORITY_KEY) == -1
        assert parent_span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) == 1.0
        assert parent_span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == SINGLE_SPAN_SAMPLING_MECHANISM_VALUE
        assert parent_span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) == 50

        # child span should be dropped by defined trace sampling rules
        if "metrics" in child_span:
            assert child_span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) is None
            assert child_span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) is None
            assert child_span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) is None

        if "meta" in child_span:
            assert child_span["meta"].get("_dd.p.dm") is None

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_SPAN_SAMPLING_RULES": json.dumps(
                    [{"service": "webserver", "name": "child", "sample_rate": 1.0, "max_per_second": 50}]
                ),
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": '[{"sample_rate":0}]',
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "false",
            }
        ],
    )
    def test_child_span_selected_by_sss015(self, test_agent, test_library):
        """Single spans selected by SSS must be kept even if its parent has been dropped.

        We're essentially testing to make sure that the span sampling rule keeps selected spans despite of the trace sampling decision
        and doesn't affect parent spans that are dropped by the tracer sampling mechanism.
        """
        with (
            test_library,
            test_library.dd_start_span(name="parent", service="webserver") as ps,
            test_library.dd_start_span(name="child", service="webserver", parent_id=ps.span_id) as cs,
        ):
            pass

        traces = test_agent.wait_for_num_spans(2, clear=True)

        parent_span = find_span_in_traces(traces, ps.trace_id, ps.span_id)
        child_span = find_span_in_traces(traces, cs.trace_id, cs.span_id)

        # root span should be dropped by defined trace sampling rules
        assert parent_span["metrics"].get(SAMPLING_PRIORITY_KEY) == -1
        assert parent_span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) is None
        assert parent_span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) is None
        assert parent_span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) is None

        # child span should be kept by defined the SSS rules
        assert child_span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) == 1.0
        assert child_span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == SINGLE_SPAN_SAMPLING_MECHANISM_VALUE
        assert child_span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) == 50

    @missing_feature(context.library == "cpp", reason="span dropping policy not implemented")
    @missing_feature(context.library == "dotnet", reason="The .NET tracer sends the full trace to the agent anyways.")
    @missing_feature(context.library == "nodejs", reason="Not implemented")
    @missing_feature(context.library == "php", reason="The PHP tracer always sends the full trace to the agent.")
    @missing_feature(context.library == "python", reason="RPC issue causing test to hang")
    @missing_feature(
        context.library == "ruby", reason="Issue: sending the complete trace when only the root span is expected"
    )
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_SPAN_SAMPLING_RULES": json.dumps(
                    [{"service": "webserver", "name": "parent", "sample_rate": 1.0, "max_per_second": 50}]
                ),
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": '[{"sample_rate":0}]',
                "DD_TRACE_TRACER_METRICS_ENABLED": "true",  # This activates dropping policy for Java Tracer
                "DD_TRACE_FEATURES": "discovery",  # This activates dropping policy for Go Tracer
            }
        ],
    )
    def test_root_span_selected_and_child_dropped_by_sss_when_dropping_policy_is_active016(
        self, test_agent, test_library
    ):
        """Single spans selected by SSS must be kept and other spans expected to be dropped on the tracer side when
        dropping policy is active when tracer metrics enabled.

        We're essentially testing to make sure that the child unsampled span is dropped on the tracer side because of
        the activate dropping policy.
        """
        assert test_agent.info()["client_drop_p0s"] is True, "Client drop p0s expected to be enabled"

        with test_library, test_library.dd_start_span(name="parent", service="webserver"):
            pass

        # expect the first trace kept by the tracer despite of the active dropping policy because of SSS
        test_agent.wait_for_num_traces(1, clear=True)

        # the second similar trace is expected to be sampled by SSS and the child span is expected to be dropped on the Tracer side
        with (
            test_library,
            test_library.dd_start_span(name="parent", service="webserver") as s2,
            test_library.dd_start_span(name="child", service="webserver", parent_id=s2.span_id),
        ):
            pass

        traces = test_agent.wait_for_num_traces(1, clear=True, sort_by_start=False)
        trace2 = find_trace(traces, s2.trace_id)
        assert len(trace2) == 1, "only the root span is expected to be sent to the test agent"

        chunk_root = trace2[0]
        # the trace should be dropped, so the parent span priority is set to -1
        assert chunk_root["name"] == "parent"
        assert chunk_root["metrics"].get(SAMPLING_PRIORITY_KEY) == -1
        assert chunk_root["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) == 1.0
        assert chunk_root["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == SINGLE_SPAN_SAMPLING_MECHANISM_VALUE
        assert chunk_root["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) == 50

    @missing_feature(context.library == "cpp", reason="span dropping policy not implemented")
    @missing_feature(context.library == "dotnet", reason="The .NET tracer sends the full trace to the agent anyways.")
    @missing_feature(context.library == "nodejs", reason="Not implemented")
    @missing_feature(context.library == "php", reason="The PHP tracer always sends the full trace to the agent.")
    @missing_feature(context.library == "python", reason="RPC issue causing test to hang")
    @missing_feature(
        context.library == "ruby", reason="Issue: sending the complete trace when only the root span is expected"
    )
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_SPAN_SAMPLING_RULES": json.dumps(
                    [{"service": "webserver", "name": "child", "sample_rate": 1.0, "max_per_second": 50}]
                ),
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": '[{"sample_rate":0}]',
                "DD_TRACE_TRACER_METRICS_ENABLED": "true",  # This activates dropping policy for Java Tracer
                "DD_TRACE_FEATURES": "discovery",  # This activates dropping policy for Go Tracer
            }
        ],
    )
    def test_child_span_selected_and_root_dropped_by_sss_when_dropping_policy_is_active017(
        self, test_agent, test_library
    ):
        """Single spans selected by SSS must be kept and other spans expected to be dropped on the tracer side when
        dropping policy is active when tracer metrics enabled.

        We're essentially testing to make sure that the root unsampled span is dropped on the tracer side because of
        the activate dropping policy.
        """
        assert test_agent.info()["client_drop_p0s"] is True, "Client drop p0s expected to be enabled"

        with (
            test_library,
            test_library.dd_start_span(name="parent", service="webserver") as ps1,
            test_library.dd_start_span(name="child", service="webserver", parent_id=ps1.span_id),
        ):
            pass

        # expect the first trace kept by the tracer despite of the active dropping policy because of SSS
        test_agent.wait_for_num_traces(1, clear=True)

        # the second similar trace is expected to be sampled by SSS and the child span is expected to be dropped on the Tracer side
        with (
            test_library,
            test_library.dd_start_span(name="parent", service="webserver") as ps2,
            test_library.dd_start_span(name="child", service="webserver", parent_id=ps2.span_id) as cs2,
        ):
            pass

        traces = test_agent.wait_for_num_traces(1, clear=True)
        trace = find_trace(traces, ps2.trace_id)
        assert len(trace) == 1, "only the child span is expected to be sent to the test agent"

        child_span = find_span(trace, cs2.span_id)
        # the trace should be dropped, so the parent span priority is set to -1
        assert child_span["name"] == "child"
        assert child_span["metrics"].get(SAMPLING_PRIORITY_KEY) == -1
        assert child_span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) == 1.0
        assert child_span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == SINGLE_SPAN_SAMPLING_MECHANISM_VALUE
        assert child_span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) == 50

    @missing_feature(context.library == "cpp", reason="span dropping policy not implemented")
    @missing_feature(context.library == "dotnet", reason="The .NET tracer sends the full trace to the agent anyways.")
    @missing_feature(context.library == "nodejs", reason="Not implemented")
    @missing_feature(context.library == "php", reason="The PHP tracer always sends the full trace to the agent.")
    @missing_feature(context.library == "python", reason="RPC issue causing test to hang")
    @missing_feature(
        context.library == "ruby", reason="Issue: sending the complete trace when only the root span is expected"
    )
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": '[{"sample_rate":0}]',
                "DD_TRACE_TRACER_METRICS_ENABLED": "true",  # This activates dropping policy for Java Tracer
                "DD_TRACE_FEATURES": "discovery",  # This activates dropping policy for Go Tracer
            }
        ],
    )
    def test_entire_trace_dropped_when_dropping_policy_is_active018(self, test_agent, test_library):
        """The entire dropped span expected to be dropped on the tracer side when
        dropping policy is active, which is the case when tracer metrics enabled.

        We're essentially testing to make sure that the entire unsampled trace is dropped on the tracer side because of
        the activate dropping policy.
        """
        assert test_agent.info()["client_drop_p0s"] is True, "Client drop p0s expected to be enabled"

        with test_library, test_library.dd_start_span(name="parent", service="webserver"):
            pass

        if test_library.lang == "java":
            # Java Tracer is expected to keep the first trace despite of the active dropping policy because
            # its resource/operation/error combination hasn't been seen before
            test_agent.wait_for_num_traces(1, clear=True)
        elif test_library.lang == "golang":
            # Go Tracer is expected to drop the very fist p0s
            test_agent.wait_for_num_traces(0, clear=True)

        # the second similar trace is expected to be dropped on the Tracer side
        with (
            test_library,
            test_library.dd_start_span(name="parent", service="webserver") as ps,
            test_library.dd_start_span(name="child", service="webserver", parent_id=ps.span_id),
        ):
            pass

        traces = test_agent.wait_for_num_traces(0, clear=True)

        assert len(traces) == 0

    @bug(context.library == "cpp", reason="APMAPI-1545")
    @bug(context.library == "golang", reason="APMAPI-1545")
    @bug(context.library == "php", reason="APMAPI-1545")
    @bug(context.library == "ruby", reason="APMAPI-1545")
    @bug(context.library == "python", reason="APMAPI-1545")
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TRACE_PROPAGATION_STYLE": "datadog",
                "DD_SPAN_SAMPLING_RULES": json.dumps([{"name": "web.request", "sample_rate": 1.0}]),
                "DD_TRACE_SAMPLING_RULES": json.dumps([{"name": "web.request", "sample_rate": 1.0}]),
            }
        ],
    )
    def test_single_rule_with_head_and_rule_trace_sampling_keep_019(self, test_agent, test_library):
        """Test that head sampling, single span rules and trace rules work well together when the rules are to keep.

        Test that:
        1. Single span should not apply when the trace is kept by the head sampling.
        2. Trace sampling rule is not applied when there is a head sampling decision.
        3. Spans are flagged with the correct tags and sampling mechanism.
        """

        with test_library.dd_extract_headers_and_make_child_span(
            "web.request",
            [
                ["x-datadog-trace-id", "12345678901"],
                ["x-datadog-parent-id", "98765432101"],
                ["x-datadog-sampling-priority", "1"],
                ["x-datadog-origin", "rum"],
            ],
        ) as s1:
            pass

        with test_library.dd_extract_headers_and_make_child_span(
            "web.request",
            [
                ["x-datadog-trace-id", "12345678902"],
                ["x-datadog-parent-id", "98765432102"],
                ["x-datadog-sampling-priority", "0"],
                ["x-datadog-origin", "rum"],
            ],
        ) as s2:
            pass

        traces = test_agent.wait_for_num_traces(2)

        case1 = find_span_in_traces(traces, s1.trace_id, s1.span_id)
        # Assert the RUM origin is set
        assert case1["meta"]["_dd.origin"] == "rum"
        # Assert the propagated sampling priority is unaffected
        assert case1["metrics"].get(SAMPLING_PRIORITY_KEY) == 1
        # Assert that there is no trace sampling happening
        assert "_dd.p.dm" not in case1["meta"]
        assert "_dd.rule_psr" not in case1["meta"]
        # Assert that there is no single span sampling happening
        assert SINGLE_SPAN_SAMPLING_MECHANISM not in case1["metrics"]
        assert SINGLE_SPAN_SAMPLING_RATE not in case1["metrics"]
        assert SINGLE_SPAN_SAMPLING_MAX_PER_SEC not in case1["metrics"]

        case2 = find_span_in_traces(traces, s2.trace_id, s2.span_id)
        # Assert the RUM origin is set
        assert case2["meta"]["_dd.origin"] == "rum"
        # Assert the propagated sampling priority is unaffected
        assert case2["metrics"].get(SAMPLING_PRIORITY_KEY) == 0
        # Assert that there is no trace sampling happening
        assert "_dd.p.dm" not in case2["meta"]
        assert "_dd.rule_psr" not in case2["meta"]
        # Assert single span sampling applied
        assert case2["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == 8
        assert case2["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) == 1

    @bug(context.library == "cpp", reason="APMAPI-1545")
    @bug(context.library == "golang", reason="APMAPI-1545")
    @bug(context.library == "php", reason="APMAPI-1545")
    @bug(context.library == "python", reason="APMAPI-1545")
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TRACE_PROPAGATION_STYLE": "datadog",
                "DD_SPAN_SAMPLING_RULES": json.dumps([{"name": "web.request", "sample_rate": 0.0}]),
                "DD_TRACE_SAMPLING_RULES": json.dumps([{"name": "web.request", "sample_rate": 0.0}]),
            }
        ],
    )
    def test_single_rule_with_head_and_rule_trace_sampling_drop_020(self, test_agent, test_library):
        """Test that head sampling, single span rules and trace rules work well together when the rules are to drop.

        Test that:
        1. Single span should not drop spans kept by head sampling.
        2. Trace sampling rule is not applied when there is a head sampling decision.
        3. Spans are flagged with the correct tags and sampling mechanism.
        """

        with test_library.dd_extract_headers_and_make_child_span(
            "web.request",
            [
                ["x-datadog-trace-id", "12345678901"],
                ["x-datadog-parent-id", "98765432101"],
                ["x-datadog-sampling-priority", "1"],
                ["x-datadog-origin", "rum"],
            ],
        ) as s1:
            pass

        with test_library.dd_extract_headers_and_make_child_span(
            "web.request",
            [
                ["x-datadog-trace-id", "12345678902"],
                ["x-datadog-parent-id", "98765432102"],
                ["x-datadog-sampling-priority", "0"],
                ["x-datadog-origin", "rum"],
            ],
        ) as s2:
            pass

        traces = test_agent.wait_for_num_traces(2)

        case1 = find_span_in_traces(traces, s1.trace_id, s1.span_id)
        # Assert the RUM origin is set
        assert case1["meta"]["_dd.origin"] == "rum"
        # Assert the propagated sampling priority is unaffected
        assert case1["metrics"].get(SAMPLING_PRIORITY_KEY) == 1
        # Assert that there is no trace sampling happening
        assert "_dd.p.dm" not in case1["meta"]
        assert "_dd.rule_psr" not in case1["meta"]
        # Assert that there is no single span sampling happening
        assert SINGLE_SPAN_SAMPLING_MECHANISM not in case1["metrics"]
        assert SINGLE_SPAN_SAMPLING_RATE not in case1["metrics"]
        assert SINGLE_SPAN_SAMPLING_MAX_PER_SEC not in case1["metrics"]

        case2 = find_span_in_traces(traces, s2.trace_id, s2.span_id)
        # Assert the RUM origin is set
        assert case2["meta"]["_dd.origin"] == "rum"
        # Assert the propagated sampling priority is unaffected
        assert case2["metrics"].get(SAMPLING_PRIORITY_KEY) == 0
        # Assert that there is no trace sampling happening
        assert "_dd.p.dm" not in case2["meta"]
        assert "_dd.rule_psr" not in case2["meta"]
        # Assert that there is no single span sampling happening
        assert SINGLE_SPAN_SAMPLING_MECHANISM not in case1["metrics"]
        assert SINGLE_SPAN_SAMPLING_RATE not in case1["metrics"]
        assert SINGLE_SPAN_SAMPLING_MAX_PER_SEC not in case1["metrics"]
