import ddtrace
from ddtrace import Span
from ddtrace.context import Context
import pytest
from apm_client.trace import SINGLE_SPAN_SAMPLING_MAX_PER_SEC
from apm_client.trace import SINGLE_SPAN_SAMPLING_MECHANISM
from apm_client.trace import SINGLE_SPAN_SAMPLING_MECHANISM_VALUE
from apm_client.trace import SINGLE_SPAN_SAMPLING_RATE
from apm_client.trace import SAMPLING_PRIORITY_KEY
from apm_client.trace import MANUAL_DROP_KEY
from apm_client.trace import MANUAL_KEEP_KEY
from apm_client.trace import USER_KEEP
import time
from .conftest import _TestTracer
import os
import json


@pytest.mark.parametrize(
    "apm_test_server_env", [{"DD_SPAN_SAMPLING_RULES": json.dumps([{"service": "webserver", "name": "web.request"}])}]
)
def test_single_rule_match_span_sampling_sss001(test_agent, test_client: _TestTracer):
    """Test span sampling tags are added when a span sampling rule matches and the tracer is set to drop the span manually"""
    generate_span(test_client)
    span = get_span(test_agent)

    assert_sampling_decision_tags(span)


@pytest.mark.parametrize(
    "apm_test_server_env", [{"DD_SPAN_SAMPLING_RULES": json.dumps([{"service": "webse*", "name": "web.re?uest"}])}]
)
def test_special_glob_characters_span_sampling_sss002(test_agent, test_client: _TestTracer):
    """Test span sampling tags are added when a rule glob pattern with special characters * and ? match"""
    generate_span(test_client)
    span = get_span(test_agent)

    assert_sampling_decision_tags(span)


@pytest.mark.parametrize(
    "apm_test_server_env", [{"DD_SPAN_SAMPLING_RULES": json.dumps([{"service": "notmatching", "name": "notmatching"}])}]
)
def test_single_rule_no_match_span_sampling_sss003(test_agent, test_client: _TestTracer):
    """Test span sampling tags are not added when a basic span sampling rule matches, and the tracer is set to drop the span manually"""
    generate_span(test_client)
    span = get_span(test_agent)

    assert_sampling_decision_tags(span, sample_rate=None, mechanism=None)


@pytest.mark.parametrize("apm_test_server_env", [{"DD_SPAN_SAMPLING_RULES": json.dumps([{"service": "webserver"}])}])
def test_single_rule_only_service_pattern_match_span_sampling_sss004(test_agent, test_client: _TestTracer):
    """Test span sampling tags are added when a span sampling rule that only has a service pattern matches,
    and the tracer is set to drop the span manually
    """
    generate_span(test_client)
    span = get_span(test_agent)

    assert_sampling_decision_tags(span)


@pytest.mark.parametrize("apm_test_server_env", [{"DD_SPAN_SAMPLING_RULES": json.dumps([{"name": "no_match"}])}])
def test_single_rule_only_name_pattern_no_match_span_sampling_sss005(test_agent, test_client: _TestTracer):
    """Test span sampling tags are not added when a span sampling rule that only has a name pattern does not match,
    and the tracer is set to drop the span manually
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
    """Test span sampling tags are added when a the first span sampling rule matches and keeps,
    and the second rule matches and drops due to sample rate, and the tracer is set to drop the span manually
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
    """Test span sampling tags are not added when the first span sampling rule matches and drops due to sample rate,
    and the second rule matches and keeps, and the tracer is set to drop the span manually
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
    limit_hit = False
    while limit_hit is not True:
        generate_span(test_client)
        span = get_span(test_agent)
        # If we don't have the span sampling limit tag on the span,
        # we hit the limit and this span will be dropped due to the rate limiter
        if span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE, None) == None:
            limit_hit = True

    # We test that after making another span matching that matches the rule,
    # it has none of the span sampling tags because we hit the rate limit
    generate_span(test_client)
    span = get_span(test_agent)
    assert_sampling_decision_tags(span, sample_rate=None, mechanism=None)

    # wait a couple of seconds for rate limiter tokens
    time.sleep(2)
    # Now span should be kept by rule
    generate_span(test_client)
    span = get_span(test_agent)
    assert_sampling_decision_tags(span, limit=2)


@pytest.mark.parametrize(
    "apm_test_server_env",
    [{"DD_SPAN_SAMPLING_RULES": json.dumps([{"service": "webserver", "name": "web.request", "sample_rate": 0.5}])}],
)
def test_sampling_rate_not_absolute_value_sss009(test_agent, test_client: _TestTracer):
    """Test sample rate comes close to expected number of spans sampled"""
    for i in range(100):
        generate_span(test_client)
    traces = test_agent.traces()
    assert len(traces) == 100
    sampled = []
    unsampled = []
    for span in traces:
        if span[0]["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM, None) == SINGLE_SPAN_SAMPLING_MECHANISM_VALUE:
            sampled.append(span)
        else:
            unsampled.append(span)

    assert len(sampled) in range(40, 60)
    assert len(unsampled) in range(40, 60)

    # assert_sampling_decision_tags(span)


@pytest.mark.skip(
    reason="stats computation not implemented in all tracers and this will fail for Python tracer due to current architecture"
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
    assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == USER_KEEP


@pytest.mark.parametrize(
    "apm_test_server_env",
    [{"DD_SPAN_SAMPLING_RULES": json.dumps([{"service": "webserver", "name": "web.request", "sample_rate": 1.0}])}],
)
def test_single_rule_always_keep_span_sampling_sss011(test_agent, test_client: _TestTracer):
    """Test spans are always kept when sampling rule matches and has sample_rate:1.0, regardless of tracer decision"""
    generate_span(test_client)
    span = get_span(test_agent)

    assert_sampling_decision_tags(span)

    # This span is sampled by the tracer, not span sampling, so it's still kept, but because of "_sampling_priority_v1" > 0
    # Not the tracer
    generate_span(test_client, trace_sampling=True)
    span = get_span(test_agent)
    assert_sampling_decision_tags(span, sample_rate=None, mechanism=None, trace_sampling=True)


@pytest.mark.parametrize(
    "apm_test_server_env",
    [{"DD_SPAN_SAMPLING_RULES": json.dumps([{"service": "webserver", "name": "web.request", "sample_rate": 0}])}],
)
def test_single_rule_tracer_always_keep_span_sampling_sss012(test_agent, test_client: _TestTracer):
    """Test spans are always kept when tracer keeps, regardless of span sampling rule set to drop"""
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
    limit_hit = False
    while limit_hit is not True:
        generate_span(test_client)
        span = get_span(test_agent)
        # If we don't have the span sampling limit tag on the span, we hit the limit and this span will be dropped due to the rate limiter
        if span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE, None) == None:
            limit_hit = True

    generate_span(test_client)
    span = get_span(test_agent)
    # We test that after making another span matching the first rule, it has none of the span sampling tags because we hit the rate limiter
    assert_sampling_decision_tags(span, sample_rate=None, mechanism=None)

    # This span is kept and has span sampling tags because it has its own rate limiter
    generate_span(test_client, service="webserver2", name="web.request2")
    span = get_span(test_agent)
    assert_sampling_decision_tags(span, limit=5)

    # We test that after making another span that should still be at the rate limit,
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

    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_RATE, None) == sample_rate
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MECHANISM, None) == mechanism
    assert span["metrics"].get(SINGLE_SPAN_SAMPLING_MAX_PER_SEC, None) == limit

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
