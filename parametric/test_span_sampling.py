import pytest
from parametric.spec.trace import SAMPLING_PRIORITY_KEY
from parametric.spec.trace import SINGLE_SPAN_SAMPLING_MAX_PER_SEC
from parametric.spec.trace import SINGLE_SPAN_SAMPLING_MECHANISM
from parametric.spec.trace import SINGLE_SPAN_SAMPLING_MECHANISM_VALUE
from parametric.spec.trace import SINGLE_SPAN_SAMPLING_RATE
from parametric.spec.trace import MANUAL_DROP_KEY
from parametric.spec.trace import USER_KEEP
from parametric.spec.trace import Span
from parametric.spec.trace import find_span_in_traces
import time
import json


@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.parametrize(
    "library_env",
    [
        {
            "DD_SPAN_SAMPLING_RULES": json.dumps([{"service": "webserver", "name": "web.request"}]),
            "DD_TRACE_SAMPLE_RATE": 0,
        }
    ],
)
def test_single_rule_match_span_sampling_sss001(test_agent, test_library):
    """Test that span sampling tags are added when both:
    1. a span sampling rule matches
    2. tracer is set to drop the trace manually"""
    with test_library:
        with test_library.start_span(name="web.request", service="webserver"):
            pass
    span = find_span_in_traces(test_agent.wait_for_num_traces(1), Span(name="web.request", service="webserver"))

    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) == 1.0
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == SINGLE_SPAN_SAMPLING_MECHANISM_VALUE
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) is None


@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.parametrize(
    "library_env",
    [{"DD_SPAN_SAMPLING_RULES": json.dumps([{"service": "webse*", "name": "web.re?uest"}]), "DD_TRACE_SAMPLE_RATE": 0}],
)
def test_special_glob_characters_span_sampling_sss002(test_agent, test_library):
    """Test span sampling tags are added when a rule with glob patterns with special characters * and ? match"""
    with test_library:
        with test_library.start_span(name="web.request", service="webserver"):
            pass
    span = find_span_in_traces(test_agent.wait_for_num_traces(1), Span(name="web.request", service="webserver"))

    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) == 1.0
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == SINGLE_SPAN_SAMPLING_MECHANISM_VALUE
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) is None


@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.parametrize(
    "library_env",
    [
        {
            "DD_SPAN_SAMPLING_RULES": json.dumps([{"service": "notmatching", "name": "notmatching"}]),
            "DD_TRACE_SAMPLE_RATE": 0,
        }
    ],
)
def test_single_rule_no_match_span_sampling_sss003(test_agent, test_library):
    """Test span sampling tags are not added when both:
    1. a basic span sampling rule does not match
    2. the tracer is set to drop the span manually
    """
    with test_library:
        with test_library.start_span(name="web.request", service="webserver"):
            pass
    span = find_span_in_traces(test_agent.wait_for_num_traces(1), Span(name="web.request", service="webserver"))

    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) is None
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) is None
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) is None


@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.parametrize(
    "library_env", [{"DD_SPAN_SAMPLING_RULES": json.dumps([{"service": "webserver"}]), "DD_TRACE_SAMPLE_RATE": 0}],
)
def test_single_rule_only_service_pattern_match_span_sampling_sss004(test_agent, test_library):
    """Test span sampling tags are added when both:
    1. a span sampling rule that only has a service pattern matches
    2. the tracer is set to drop the span manually
    """
    with test_library:
        with test_library.start_span(name="web.request", service="webserver"):
            pass
    span = find_span_in_traces(test_agent.wait_for_num_traces(1), Span(name="web.request", service="webserver"))
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) == 1.0
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == SINGLE_SPAN_SAMPLING_MECHANISM_VALUE
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) is None


@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.parametrize(
    "library_env", [{"DD_SPAN_SAMPLING_RULES": json.dumps([{"name": "no_match"}]), "DD_TRACE_SAMPLE_RATE": 0}]
)
def test_single_rule_only_name_pattern_no_match_span_sampling_sss005(test_agent, test_library):
    """Test span sampling tags are not added when:
    1. a span sampling rule that only has a name pattern does not match
    2. the tracer is set to drop the span manually
    """
    with test_library:
        with test_library.start_span(name="web.request", service="webserver"):
            pass
    span = find_span_in_traces(test_agent.wait_for_num_traces(1), Span(name="web.request", service="webserver"))
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) is None
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) is None
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) is None


@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
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
        }
    ],
)
def test_multi_rule_keep_drop_span_sampling_sss006(test_agent, test_library):
    """Test span sampling tags are added when the following are true:
    1. the first span sampling rule matches and keeps
    2. the second rule matches and drops due to sample rate
    3. the tracer is set to drop the span manually

    We're essentially testing that:
    1. rules are assessed in order of their listing
    2. that once a rule is matched, we do not try to match against further rules. We do this by assuming that the "sample_rate": 0 of the second rule, if matched against would cause the span to not have span sampling tags.
    """
    with test_library:
        with test_library.start_span(name="web.request", service="webserver"):
            pass
    span = find_span_in_traces(test_agent.wait_for_num_traces(1), Span(name="web.request", service="webserver"))
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) == 1.0
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == SINGLE_SPAN_SAMPLING_MECHANISM_VALUE
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) is None


@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
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
        }
    ],
)
def test_multi_rule_drop_keep_span_sampling_sss007(test_agent, test_library):
    """Test span sampling tags are not added when both:
    1. the first span sampling rule matches and drops due to sample rate
    2. the second rule matches and keeps
    3. the tracer is set to drop the span manually

    We're essentially testing that:
    1. rules are assessed in order of their listing
    2. that once a rule is matched, we do not try to match against further rules. We do this by assuming that the "sample_rate": 0 of the first rule, will cause the span to not have span sampling tags.
    """
    with test_library:
        with test_library.start_span(name="web.request", service="webserver"):
            pass
    span = find_span_in_traces(test_agent.wait_for_num_traces(1), Span(name="web.request", service="webserver"))
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) is None
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) is None
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) is None


@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.parametrize(
    "library_env",
    [
        {
            "DD_SPAN_SAMPLING_RULES": json.dumps(
                [{"service": "webserver", "name": "web.request", "max_per_second": 2}]
            ),
            "DD_TRACE_SAMPLE_RATE": 0,
        }
    ],
)
def test_single_rule_rate_limiter_span_sampling_sss008(test_agent, test_library):
    """Test span sampling tags are added until rate limit hit, then need to wait for tokens to reset"""
    # generate spans until we hit the rate limit
    while True:
        with test_library:
            with test_library.start_span(name="web.request", service="webserver"):
                pass
        span = find_span_in_traces(
            test_agent.wait_for_num_traces(1, clear=True), Span(name="web.request", service="webserver")
        )
        # if we don't have the span sampling mechanism tag on the span
        # it means we hit the limit and this span will be dropped due to the rate limiter
        if span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) is None:
            break

    # we test that after making another span that matches the rule,
    # it has none of the span sampling tags because we hit the rate limit
    with test_library:
        with test_library.start_span(name="web.request", service="webserver"):
            pass
    span = find_span_in_traces(
        test_agent.wait_for_num_traces(1, clear=True), Span(name="web.request", service="webserver")
    )
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) is None
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) is None
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) is None

    # wait a second for rate limiter tokens to replenish
    time.sleep(2)
    # now span should be kept by rule
    with test_library:
        with test_library.start_span(name="web.request", service="webserver"):
            pass
    span = find_span_in_traces(test_agent.wait_for_num_traces(1), Span(name="web.request", service="webserver"))
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) == 1.0
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == 8
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) == 2


@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.parametrize(
    "library_env",
    [
        {
            "DD_SPAN_SAMPLING_RULES": json.dumps([{"service": "webserver", "name": "web.request", "sample_rate": 0.5}]),
            "DD_TRACE_SAMPLE_RATE": 0,
        }
    ],
)
def test_sampling_rate_not_absolute_value_sss009(test_agent, test_library):
    """Test sample rate comes close to expected number of spans sampled. We do this by setting the
    sample_rate to 0.5, and then making sure that about half of the spans have span sampling tags and
    half do not.
    """
    # make 100 new traces, each with one span
    for i in range(100):
        with test_library:
            with test_library.start_span(name="web.request", service="webserver"):
                pass
    traces = test_agent.wait_for_num_traces(num=100)
    assert len(traces) == 100
    sampled = []
    unsampled = []

    for trace in traces:
        if trace[0]["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == SINGLE_SPAN_SAMPLING_MECHANISM_VALUE:
            sampled.append(trace)
        else:
            unsampled.append(trace)

    assert len(sampled) in range(30, 70)
    assert len(unsampled) in range(30, 70)


@pytest.mark.skip(
    reason="this has to be implemented by a lot of the tracers and we need to do a bit of work on the assert"
)
@pytest.mark.parametrize(
    "library_env",
    [
        {
            "DD_SPAN_SAMPLING_RULES": json.dumps([{"service": "webserver", "name": "web.request"}]),
            "DD_TRACE_SAMPLE_RATE": 0,
            "DD_TRACE_STATS_COMPUTATION_ENABLED": "True",
        }
    ],
)
def test_keep_span_with_stats_computation_sss010(test_agent, test_library):
    """Test when stats computation is enabled and span sampling applied, spans have manual_keep and still sent."""
    with test_library:
        with test_library.start_span(name="web.request", service="webserver"):
            pass
    span = find_span_in_traces(test_agent.wait_for_num_traces(1), Span(name="web.request", service="webserver"))
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) == 1.0
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == SINGLE_SPAN_SAMPLING_MECHANISM_VALUE
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) is None
    # We should be setting sampling priority to manual keep so the agent sampler won't be affected
    # TODO: we need a way to check that the chunk that contains the span was associated with USER_KEEP priority,
    # the below does not apply to all agent APIs
    assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == USER_KEEP


@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("golang", "The Go tracer does not have a way to modulate trace sampling once started")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.parametrize(
    "library_env",
    [
        {
            "DD_SPAN_SAMPLING_RULES": json.dumps([{"service": "webserver", "name": "web.request", "sample_rate": 1.0}]),
            "DD_TRACE_SAMPLE_RATE": 1.0,
        }
    ],
)
def test_single_rule_always_keep_span_sampling_sss011(test_agent, test_library):
    """Test that spans are always kept when the sampling rule matches and has sample_rate:1.0 regardless of tracer decision.

    Basically, if we have a rule for spans with sample_rate:1.0 we should always keep those spans, either due to trace sampling or span sampling"""
    # This span is set to be dropped by the tracer/user, however it is kept by span sampling
    with test_library:
        with test_library.start_span(name="web.request", service="webserver") as span:
            span.set_meta(MANUAL_DROP_KEY, "1")
    span = find_span_in_traces(test_agent.wait_for_num_traces(1, clear=True), Span(name="web.request", service="webserver"))
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) == 1.0
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == SINGLE_SPAN_SAMPLING_MECHANISM_VALUE
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) is None

    # This span is sampled by the tracer, not span sampling.
    # Therefore it won't have the span sampling tags, but rather the trace sampling tags.
    with test_library:
        with test_library.start_span(name="web.request", service="webserver") as span:
            pass
    span = find_span_in_traces(test_agent.wait_for_num_traces(1), Span(name="web.request", service="webserver"))

    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) is None
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) is None
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) is None
    assert span["metrics"].get(SAMPLING_PRIORITY_KEY) > 0


@pytest.mark.parametrize(
    "library_env",
    [
        {
            "DD_SPAN_SAMPLING_RULES": json.dumps([{"service": "webserver", "name": "web.request", "sample_rate": 0}]),
            "DD_TRACE_SAMPLE_RATE": 1.0,
        }
    ],
)
def test_single_rule_tracer_always_keep_span_sampling_sss012(test_agent, test_library):
    """Test spans are always kept when tracer keeps, regardless of span sampling rule set to drop.

    We're essentially testing to make sure that the span sampling rule cannot control the fate of the span if the span is already being kept by trace sampling.
    """
    # This span is sampled by the tracer, not span sampling, which would try to drop the span, so it's still kept because "_sampling_priority_v1" > 0
    # When the trace is kept by trace sampling, span rules are not applied
    with test_library:
        with test_library.start_span(name="web.request", service="webserver"):
            pass
    span = find_span_in_traces(test_agent.wait_for_num_traces(1), Span(name="web.request", service="webserver"))

    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) is None
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) is None
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) is None
    assert span["metrics"].get(SAMPLING_PRIORITY_KEY) > 0


@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.parametrize(
    "library_env",
    [
        {
            "DD_SPAN_SAMPLING_RULES": json.dumps(
                [
                    {"service": "webserver", "name": "web.request", "max_per_second": 1},
                    {"service": "webserver2", "name": "web.request2", "max_per_second": 5},
                ]
            ),
            "DD_TRACE_SAMPLE_RATE": 0,
        }
    ],
)
def test_multi_rule_independent_rate_limiters_sss013(test_agent, test_library):
    """Span rule rate limiters are per-rule.  So, spans that match different rules don't share a limiter, but
    multiple traces whose spans match the same rule do share a limiter.
    """
    # generate spans until we hit the first rule's rate limit
    while True:
        with test_library:
            with test_library.start_span(name="web.request", service="webserver"):
                pass

        span = find_span_in_traces(
            test_agent.wait_for_num_traces(1, clear=True), Span(name="web.request", service="webserver")
        )
        # if we don't have the span sampling mechanism tag on the span
        # it means we hit the limit and this span will be dropped due to the rate limiter
        if span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == None:
            break

    with test_library:
        with test_library.start_span(name="web.request", service="webserver"):
            pass
    span = find_span_in_traces(
        test_agent.wait_for_num_traces(1, clear=True), Span(name="web.request", service="webserver")
    )
    # We test that after making another span matching the first rule, it has none of the span sampling tags because we
    # hit the rate limiter
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) is None
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) is None
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) is None

    # This span matches the second rule and is kept
    # it has span sampling tags because it has its own rate limiter
    with test_library:
        with test_library.start_span(name="web.request2", service="webserver2"):
            pass
    span = find_span_in_traces(
        test_agent.wait_for_num_traces(1, clear=True), Span(name="web.request2", service="webserver2")
    )
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) == 1.0
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == SINGLE_SPAN_SAMPLING_MECHANISM_VALUE
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) == 5

    # We create another span that will match the first rule which should still be at the rate limit,
    # it has none of the span sampling tags because we hit the rate limit of the first rule
    with test_library:
        with test_library.start_span(name="web.request", service="webserver"):
            pass

    span = find_span_in_traces(test_agent.wait_for_num_traces(1, clear=True), Span(name="web.request"))
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) is None
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) is None
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) is None

    # wait a couple of seconds for rate limiter tokens
    time.sleep(2)
    # Now span should be kept by first rule
    with test_library:
        with test_library.start_span(name="web.request", service="webserver"):
            pass
    span = find_span_in_traces(test_agent.wait_for_num_traces(1), Span(name="web.request"))
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) == 1
