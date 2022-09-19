import pytest
from parametric.spec.trace import SINGLE_SPAN_SAMPLING_MAX_PER_SEC
from parametric.spec.trace import SINGLE_SPAN_SAMPLING_MECHANISM
from parametric.spec.trace import SINGLE_SPAN_SAMPLING_MECHANISM_VALUE
from parametric.spec.trace import SINGLE_SPAN_SAMPLING_RATE
from parametric.spec.trace import SAMPLING_PRIORITY_KEY
from parametric.spec.trace import MANUAL_DROP_KEY
from parametric.spec.trace import MANUAL_KEEP_KEY
from parametric.spec.trace import USER_KEEP
import time
from .conftest import _TestTracer
import json


@pytest.mark.parametrize(
    "apm_test_server_env", [{"DD_SPAN_SAMPLING_RULES": json.dumps([{"service": "webserver", "name": "web.request"}])}]
)
def test_single_rule_match_span_sampling_sss001(test_agent, test_client: _TestTracer):
    """Test that span sampling tags are added when both:
    1. a span sampling rule matches
    2. tracer is set to drop the trace manually"""
    generate_span(test_client)
    span = get_span(test_agent)

    assert_sampling_decision_tags(span)


@pytest.mark.parametrize(
    "apm_test_server_env", [{"DD_SPAN_SAMPLING_RULES": json.dumps([{"service": "webse*", "name": "web.re?uest"}])}]
)
def test_special_glob_characters_span_sampling_sss002(test_agent, test_client: _TestTracer):
    """Test span sampling tags are added when a rule with glob patterns with special characters * and ? match"""
    generate_span(test_client)
    span = get_span(test_agent)

    assert_sampling_decision_tags(span)


@pytest.mark.parametrize(
    "apm_test_server_env", [{"DD_SPAN_SAMPLING_RULES": json.dumps([{"service": "notmatching", "name": "notmatching"}])}]
)
def test_single_rule_no_match_span_sampling_sss003(test_agent, test_client: _TestTracer):
    """Test span sampling tags are not added when both:
    1. a basic span sampling rule does not match
    2. the tracer is set to drop the span manually
    """
    generate_span(test_client)
    span = get_span(test_agent)

    assert_sampling_decision_tags(span, sample_rate=None, mechanism=None)


@pytest.mark.parametrize("apm_test_server_env", [{"DD_SPAN_SAMPLING_RULES": json.dumps([{"service": "webserver"}])}])
def test_single_rule_only_service_pattern_match_span_sampling_sss004(test_agent, test_client: _TestTracer):
    """Test span sampling tags are added when both:
    1. a span sampling rule that only has a service pattern matches
    2. the tracer is set to drop the span manually
    """
    generate_span(test_client)
    span = get_span(test_agent)

    assert_sampling_decision_tags(span)


@pytest.mark.parametrize("apm_test_server_env", [{"DD_SPAN_SAMPLING_RULES": json.dumps([{"name": "no_match"}])}])
def test_single_rule_only_name_pattern_no_match_span_sampling_sss005(test_agent, test_client: _TestTracer):
    """Test span sampling tags are not added when:
    1. a span sampling rule that only has a name pattern does not match
    2. the tracer is set to drop the span manually
    """
    generate_span(test_client)
    span = get_span(test_agent)

    assert_sampling_decision_tags(span, sample_rate=None, mechanism=None)


@pytest.mark.parametrize(
    "apm_test_server_env",
    [
        {
            "DD_SPAN_SAMPLING_RULES": json.dumps(
                [
                    {"service": "webserver", "name": "web.request"},
                    {"service": "webserver", "name": "web.request", "sample_rate": 0},
                ]
            )
        }
    ],
)
def test_multi_rule_keep_drop_span_sampling_sss006(test_agent, test_client: _TestTracer):
    """Test span sampling tags are added when the following are true:
    1. the first span sampling rule matches and keeps
    2. the second rule matches and drops due to sample rate
    3. the tracer is set to drop the span manually

    We're essentially testing that:
    1. rules are assessed in order of their listing
    2. that once a rule is matched, we do not try to match against further rules. We do this by assuming that the "sample_rate": 0 of the second rule, if matched against would cause the span to not have span sampling tags.
    """
    generate_span(test_client)
    span = get_span(test_agent)

    assert_sampling_decision_tags(span)


@pytest.mark.parametrize(
    "apm_test_server_env",
    [
        {
            "DD_SPAN_SAMPLING_RULES": json.dumps(
                [
                    {"service": "webserver", "name": "web.request", "sample_rate": 0},
                    {"service": "webserver", "name": "web.request"},
                ]
            )
        }
    ],
)
def test_multi_rule_drop_keep_span_sampling_sss007(test_agent, test_client: _TestTracer):
    """Test span sampling tags are not added when both:
    1. the first span sampling rule matches and drops due to sample rate
    2. the second rule matches and keeps
    3. the tracer is set to drop the span manually

    We're essentially testing that:
    1. rules are assessed in order of their listing
    2. that once a rule is matched, we do not try to match against further rules. We do this by assuming that the "sample_rate": 0 of the first rule, will cause the span to not have span sampling tags.
    """
    generate_span(test_client)
    span = get_span(test_agent)

    assert_sampling_decision_tags(span, sample_rate=None, mechanism=None)


@pytest.mark.parametrize(
    "apm_test_server_env",
    [{"DD_SPAN_SAMPLING_RULES": json.dumps([{"service": "webserver", "name": "web.request", "max_per_second": 2}])}],
)
def test_single_rule_rate_limiter_span_sampling_sss08(test_agent, test_client: _TestTracer):
    """Test span sampling tags are added until rate limit hit, then need to wait for tokens to reset"""
    # generate spans until we hit the rate limit
    while True:
        generate_span(test_client)
        span = get_span(test_agent)
        # if we don't have the span sampling mechanism tag on the span
        # it means we hit the limit and this span will be dropped due to the rate limiter
        if span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == None:
            break

    # we test that after making another span that matches the rule,
    # it has none of the span sampling tags because we hit the rate limit
    generate_span(test_client)
    traces = test_agent.traces()
    span = traces[0][0]
    assert_sampling_decision_tags(span, sample_rate=None, mechanism=None)

    # wait a second for rate limiter tokens to replenish
    time.sleep(1)
    # now span should be kept by rule
    generate_span(test_client)
    span = get_span(test_agent)
    assert_sampling_decision_tags(span, limit=2)


@pytest.mark.parametrize(
    "apm_test_server_env",
    [{"DD_SPAN_SAMPLING_RULES": json.dumps([{"service": "webserver", "name": "web.request", "sample_rate": 0.5}])}],
)
def test_sampling_rate_not_absolute_value_sss009(test_agent, test_client: _TestTracer):
    """Test sample rate comes close to expected number of spans sampled. We do this by setting the
    sample_rate to 0.5, and then making sure that about half of the spans have span sampling tags and
    half do not.
    """
    # make 100 new traces, each with one span
    for i in range(100):
        # generate_span always creates a new trace
        generate_span(test_client)
    traces = test_agent.traces()
    assert len(traces) == 100
    sampled = []
    unsampled = []

    for trace in traces:
        if trace[0]["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == SINGLE_SPAN_SAMPLING_MECHANISM_VALUE:
            sampled.append(trace)
        else:
            unsampled.append(trace)

    assert len(sampled) in range(40, 60)
    assert len(unsampled) in range(40, 60)


@pytest.mark.skip(
    reason="this has to be implemented by a lot of the tracers and we need to do a bit of work on the assert"
)
@pytest.mark.parametrize(
    "apm_test_server_env",
    [
        {
            "DD_SPAN_SAMPLING_RULES": json.dumps([{"service": "webserver", "name": "web.request"}]),
            "DD_TRACE_STATS_COMPUTATION_ENABLED": "True",
        }
    ],
)
def test_keep_span_with_stats_computation_sss010(test_agent, test_client: _TestTracer):
    """Test when stats computation is enabled and span sampling applied, spans have manual_keep and still sent."""
    generate_span(test_client)
    span = get_span(test_agent)
    assert_sampling_decision_tags(span)
    # We should be setting sampling priority to manual keep so the agent sampler won't be affected
    # TODO: we need a way to check that the chunk that contains the span was associated with USER_KEEP priority,
    # the below does not apply to all agent APIs
    assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == USER_KEEP


@pytest.mark.parametrize(
    "apm_test_server_env",
    [{"DD_SPAN_SAMPLING_RULES": json.dumps([{"service": "webserver", "name": "web.request", "sample_rate": 1.0}])}],
)
def test_single_rule_always_keep_span_sampling_sss011(test_agent, test_client: _TestTracer):
    """Test that spans are always kept when the sampling rule matches and has sample_rate:1.0 regardless of tracer decision.

    Basically, if we have a rule for spans with sample_rate:1.0 we should always keep those spans, either due to trace sampling or span sampling"""
    generate_span(test_client)
    span = get_span(test_agent)

    assert_sampling_decision_tags(span)

    # This span is sampled by the tracer, not span sampling.
    # Therefore it won't have the span sampling tags, but rather the trace sampling tags.
    generate_span(test_client, trace_sampling=True)
    span = get_span(test_agent)
    assert_sampling_decision_tags(span, sample_rate=None, mechanism=None, trace_sampling=True)


@pytest.mark.parametrize(
    "apm_test_server_env",
    [{"DD_SPAN_SAMPLING_RULES": json.dumps([{"service": "webserver", "name": "web.request", "sample_rate": 0}])}],
)
def test_single_rule_tracer_always_keep_span_sampling_sss012(test_agent, test_client: _TestTracer):
    """Test spans are always kept when tracer keeps, regardless of span sampling rule set to drop.

    We're essentially testing to make sure that the span sampling rule cannot control the fate of the span if the span is already being kept by trace sampling.
    """
    # This span is sampled by the tracer, not span sampling, which would try to drop the span, so it's still kept because "_sampling_priority_v1" > 0
    # When the trace is kept by trace sampling, span rules are not applied
    generate_span(test_client, trace_sampling=True)
    span = get_span(test_agent)
    assert_sampling_decision_tags(span, sample_rate=None, mechanism=None, trace_sampling=True)


@pytest.mark.parametrize(
    "apm_test_server_env",
    [
        {
            "DD_SPAN_SAMPLING_RULES": json.dumps(
                [
                    {"service": "webserver", "name": "web.request", "max_per_second": 1},
                    {"service": "webserver2", "name": "web.request2", "max_per_second": 5},
                ]
            )
        }
    ],
)
def test_multi_rule_independent_rate_limiters_sss013(test_agent, test_client: _TestTracer):
    """Span rule rate limiters are per-rule.  So, spans that match different rules don't share a limiter, but
    multiple traces whose spans match the same rule do share a limiter.
    """
    # generate spans until we hit the first rule's rate limit
    while True:
        generate_span(test_client)
        span = get_span(test_agent)
        # if we don't have the span sampling mechanism tag on the span
        # it means we hit the limit and this span will be dropped due to the rate limiter
        if span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == None:
            break

    generate_span(test_client)
    span = get_span(test_agent)
    # We test that after making another span matching the first rule, it has none of the span sampling tags because we hit the rate limiter
    assert_sampling_decision_tags(span, sample_rate=None, mechanism=None)

    # This span matches the second rule and is kept
    # it has span sampling tags because it has its own rate limiter
    generate_span(test_client, service="webserver2", name="web.request2")
    span = get_span(test_agent)
    assert_sampling_decision_tags(span, limit=5)

    # We create another span that will match the first rule which should still be at the rate limit,
    # it has none of the span sampling tags because we hit the rate limit of the first rule
    generate_span(test_client)
    span = get_span(test_agent)
    assert_sampling_decision_tags(span, sample_rate=None, mechanism=None)

    # wait a couple of seconds for rate limiter tokens
    time.sleep(2)
    # Now span should be kept by first rule
    generate_span(test_client)
    span = get_span(test_agent)
    assert_sampling_decision_tags(span, limit=1)


def assert_sampling_decision_tags(
    span, sample_rate=1.0, mechanism=SINGLE_SPAN_SAMPLING_MECHANISM_VALUE, limit=None, trace_sampling=False
):

    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE) == sample_rate
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM) == mechanism
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC) == limit

    if trace_sampling:
        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) > 0


def generate_span(test_client, name="web.request", service="webserver", trace_sampling=False):
    with test_client.start_span(name=name, service=service) as span:
        if trace_sampling:
            span.set_meta(MANUAL_KEEP_KEY, "1")
        else:
            span.set_meta(MANUAL_DROP_KEY, "1")
    test_client.flush()


def get_span(test_agent):
    traces = test_agent.traces()
    span = traces[0][0]
    return span
