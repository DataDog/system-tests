import json

import pytest
import random

from utils.parametric.spec.trace import find_only_span, find_span_in_traces
from utils.parametric.spec.trace import SAMPLING_PRIORITY_KEY, SAMPLING_RULE_PRIORITY_RATE
from utils.parametric.spec.trace import MANUAL_KEEP_KEY
from utils import rfc, scenarios, missing_feature, flaky, features, bug, context


@features.trace_sampling
@features.adaptive_sampling
@scenarios.parametric
@rfc("https://docs.google.com/document/d/1HRbi1DrBjL_KGeONrPgH7lblgqSLGlV5Ox1p4RL97xM/")
class Test_Trace_Sampling_Basic:
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [
                        {"service": "webserver.non-matching", "sample_rate": 0},
                        {"service": "webserver", "sample_rate": 1},
                    ]
                ),
            },
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [{"name": "web.request.non-matching", "sample_rate": 0}, {"name": "web.request", "sample_rate": 1}]
                ),
            },
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [
                        {"service": "webserver.non-matching", "name": "web.request", "sample_rate": 0},
                        {"service": "webserver", "name": "web.request.non-matching", "sample_rate": 0},
                        {"service": "webserver", "name": "web.request", "sample_rate": 1},
                    ]
                ),
            },
        ],
    )
    def test_trace_sampled_by_trace_sampling_rule_exact_match(self, test_agent, test_library):
        """Test that a trace is sampled by the exact matching trace sampling rule"""
        with test_library, test_library.dd_start_span(name="web.request", service="webserver") as span:
            pass
        span = find_only_span(test_agent.wait_for_num_traces(1))

        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == 2
        assert span["metrics"].get(SAMPLING_RULE_PRIORITY_RATE) == 1.0

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TRACE_SAMPLE_RATE": 1,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [{"service": "webserver", "name": "web.request", "sample_rate": 0}]
                ),
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "false",
            }
        ],
    )
    def test_trace_dropped_by_trace_sampling_rule(self, test_agent, test_library):
        """Test that a trace is dropped by the matching defined trace sampling rule"""
        with test_library, test_library.dd_start_span(name="web.request", service="webserver") as span:
            pass
        span = find_only_span(test_agent.wait_for_num_traces(1))

        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == -1
        assert span["metrics"].get(SAMPLING_RULE_PRIORITY_RATE) == 0.0

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TRACE_SAMPLE_RATE": 1,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [{"service": "webserver", "resource": "drop-me", "sample_rate": 0}, {"sample_rate": 1}]
                ),
            }
        ],
    )
    def test_trace_kept_in_spite_trace_sampling_rule(self, test_agent, test_library):
        """Test that a trace is being kept with manual.keep despite of the matching defined trace sampling rule"""
        with test_library, test_library.dd_start_span(name="web.request", service="webserver") as s1:
            s1.set_meta(MANUAL_KEEP_KEY, "1")
            s1.set_meta("resource.name", "drop-me")
        span = find_only_span(test_agent.wait_for_num_traces(1))

        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == 2


@features.trace_sampling
@features.adaptive_sampling
@scenarios.parametric
@rfc("https://docs.google.com/document/d/1S9pufnJjrsxH6pRbpigdYFwA5JjSdZ6iLZ-9E7PoAic/")
class Test_Trace_Sampling_Globs:
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [{"service": "web.non-matching*", "sample_rate": 0}, {"service": "web*", "sample_rate": 1}]
                ),
            },
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [{"name": "web.non-matching*", "sample_rate": 0}, {"name": "web.*", "sample_rate": 1}]
                ),
            },
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [
                        {"service": "webserv?r.non-matching", "name": "web.req*", "sample_rate": 0},
                        {"service": "webserv?r", "name": "web.req*.non-matching", "sample_rate": 0},
                        {"service": "webserv?r", "name": "web.req*", "sample_rate": 1},
                    ]
                ),
            },
        ],
    )
    def test_trace_sampled_by_trace_sampling_rule_glob_match(self, test_agent, test_library):
        """Test that a trace is sampled by the glob matching trace sampling rule"""
        with test_library, test_library.dd_start_span(name="web.request", service="webserver") as span:
            pass
        span = find_only_span(test_agent.wait_for_num_traces(1))

        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == 2
        assert span["metrics"].get(SAMPLING_RULE_PRIORITY_RATE) == 1.0

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [
                        {"name": "wEb.rEquEst", "sample_rate": 1},
                    ]
                ),
            },
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps([{"service": "wEbSerVer", "sample_rate": 1}]),
            },
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps([{"resource": "/rAnDom", "sample_rate": 1}]),
            },
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps([{"tags": {"key": "vAlUe"}, "sample_rate": 1}]),
            },
        ],
    )
    @bug(library="cpp", reason="APMAPI-908")
    @missing_feature(context.library < "nodejs@5.38.0", reason="Implemented in 5.38.0")
    def test_field_case_insensitivity(self, test_agent, test_library):
        """Tests that sampling rule field values are case insensitive"""
        with (
            test_library,
            test_library.dd_start_span(
                name="web.request", service="webserver", resource="/random", tags=[("key", "value")]
            ) as span,
        ):
            pass

        span = find_only_span(test_agent.wait_for_num_traces(1))

        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == 2
        assert span["metrics"].get(SAMPLING_RULE_PRIORITY_RATE) == 1.0

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TRACE_SAMPLE_RATE": 1,
                "DD_TRACE_SAMPLING_RULES": json.dumps([{"service": "w?bs?rv?r", "name": "web.*", "sample_rate": 0}]),
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "false",
            }
        ],
    )
    def test_trace_dropped_by_trace_sampling_rule(self, test_agent, test_library):
        """Test that a trace is dropped by the matching defined trace sampling rule"""
        with test_library, test_library.dd_start_span(name="web.request", service="webserver") as span:
            pass
        span = find_only_span(test_agent.wait_for_num_traces(1))

        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == -1
        assert span["metrics"].get(SAMPLING_RULE_PRIORITY_RATE) == 0.0


@features.trace_sampling
@features.adaptive_sampling
@scenarios.parametric
@rfc("https://docs.google.com/document/d/1S9pufnJjrsxH6pRbpigdYFwA5JjSdZ6iLZ-9E7PoAic/")
class Test_Trace_Sampling_Globs_Feb2024_Revision:
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [{"service": "web.non-matching*", "sample_rate": 0}, {"service": "web*", "sample_rate": 1}]
                ),
            },
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [{"name": "web.non-matching*", "sample_rate": 0}, {"name": "wEb.*", "sample_rate": 1}]
                ),
            },
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [
                        {"service": "webserv?r.non-matching", "name": "wEb.req*", "sample_rate": 0},
                        {"service": "webserv?r", "name": "web.req*.non-matching", "sample_rate": 0},
                        {"service": "webserv?r", "name": "web.req*", "sample_rate": 1},
                    ]
                ),
            },
        ],
    )
    def test_trace_sampled_by_trace_sampling_rule_insensitive_glob_match(self, test_agent, test_library):
        """Test that a trace is sampled by the glob matching trace sampling rule"""
        with test_library, test_library.dd_start_span(name="web.request", service="webserver") as span:
            pass
        span = find_only_span(test_agent.wait_for_num_traces(1))

        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == 2
        assert span["metrics"].get(SAMPLING_RULE_PRIORITY_RATE) == 1.0


@features.trace_sampling
@features.adaptive_sampling
@scenarios.parametric
@rfc("https://docs.google.com/document/d/1S9pufnJjrsxH6pRbpigdYFwA5JjSdZ6iLZ-9E7PoAic/")
class Test_Trace_Sampling_Resource:
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [{"resource": "/bar.non-matching", "sample_rate": 0}, {"resource": "/?ar", "sample_rate": 1}]
                ),
            },
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [
                        {"name": "web.request.non-matching", "resource": "/bar", "sample_rate": 0},
                        {"name": "web.request", "resource": "/bar.non-matching", "sample_rate": 0},
                        {"name": "web.request", "resource": "/b*", "sample_rate": 1},
                    ]
                ),
            },
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [
                        {"service": "webserver.non-matching", "resource": "/bar", "sample_rate": 0},
                        {"service": "webserver", "resource": "/bar.non-matching", "sample_rate": 0},
                        {"service": "webserver", "resource": "/bar", "sample_rate": 1},
                    ]
                ),
            },
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [
                        {
                            "service": "webserver.non-matching",
                            "name": "web.request",
                            "resource": "/bar",
                            "sample_rate": 0,
                        },
                        {
                            "service": "webserver",
                            "name": "web.request.non-matching",
                            "resource": "/bar",
                            "sample_rate": 0,
                        },
                        {
                            "service": "webserver",
                            "name": "web.request",
                            "resource": "/bar.non-matching",
                            "sample_rate": 0,
                        },
                        {"service": "webserver", "name": "web.request", "resource": "/b?r", "sample_rate": 1},
                    ]
                ),
            },
        ],
    )
    def test_trace_sampled_by_trace_sampling_rule_exact_match(self, test_agent, test_library):
        """Test that a trace is sampled by the exact matching trace sampling rule"""
        with test_library, test_library.dd_start_span(name="web.request", service="webserver", resource="/bar") as span:
            pass
        span = find_only_span(test_agent.wait_for_num_traces(1))

        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == 2
        assert span["metrics"].get(SAMPLING_RULE_PRIORITY_RATE) == 1.0

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TRACE_SAMPLE_RATE": 1,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [
                        {"service": "non-matching", "sample_rate": 1},
                        {"name": "non-matching", "sample_rate": 1},
                        {"resource": "non-matching", "sample_rate": 1},
                        {"service": "webserver", "name": "web.request", "resource": "/bar", "sample_rate": 0},
                    ]
                ),
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "false",
            }
        ],
    )
    def test_trace_dropped_by_trace_sampling_rule(self, test_agent, test_library):
        """Test that a trace is dropped by the matching trace sampling rule"""
        with test_library, test_library.dd_start_span(name="web.request", service="webserver", resource="/bar") as span:
            pass
        span = find_only_span(test_agent.wait_for_num_traces(1))

        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == -1
        assert span["metrics"].get(SAMPLING_RULE_PRIORITY_RATE) == 0.0


@features.trace_sampling
@features.adaptive_sampling
@scenarios.parametric
@rfc("https://docs.google.com/document/d/1S9pufnJjrsxH6pRbpigdYFwA5JjSdZ6iLZ-9E7PoAic/")
class Test_Trace_Sampling_Tags:
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [{"tags": {"tag1": "non-matching"}, "sample_rate": 0}, {"tags": {"tag1": "val1"}, "sample_rate": 1}]
                ),
            },
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [
                        {"tags": {"tag1": "non-matching"}, "sample_rate": 0},
                        {"tags": {"tag2": "non-matching"}, "sample_rate": 0},
                        {"tags": {"tag1": "non-matching", "tag2": "val2"}, "sample_rate": 0},
                        {"tags": {"tag1": "val1", "tag2": "non-matching"}, "sample_rate": 0},
                        {"tags": {"tag1": "val1", "tag2": "val2"}, "sample_rate": 1},
                    ]
                ),
            },
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [{"tags": {"tag1": "v?r*"}, "sample_rate": 0}, {"tags": {"tag1": "val?"}, "sample_rate": 1}]
                ),
            },
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [
                        {"service": "webs?rver.non-matching", "sample_rate": 0},
                        {"name": "web.request.non-matching", "sample_rate": 0},
                        {"resource": "/ba*.non-matching", "sample_rate": 0},
                        {"tags": {"tag1": "v?l1", "tag2": "va*.non-matching"}, "sample_rate": 0},
                        {
                            "service": "webs?rver",
                            "name": "web.request",
                            "resource": "/ba*",
                            "tags": {"tag1": "v?l1", "tag2": "val*"},
                            "sample_rate": 1,
                        },
                    ]
                ),
            },
        ],
    )
    def test_trace_sampled_by_trace_sampling_rule_tags(self, test_agent, test_library):
        """Test that a trace is sampled by the matching trace sampling rule"""
        with test_library, test_library.dd_start_span(name="web.request", service="webserver", resource="/bar") as span:
            span.set_meta("tag1", "val1")
            span.set_meta("tag2", "val2")
        span = find_only_span(test_agent.wait_for_num_traces(1))

        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == 2
        assert span["metrics"].get(SAMPLING_RULE_PRIORITY_RATE) == 1.0

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TRACE_SAMPLE_RATE": 1,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [
                        {"tags": {"tag1": "v?l1", "tag2": "non-matching"}, "sample_rate": 1},
                        {"tags": {"tag1": "v?l1", "tag2": "val*"}, "sample_rate": 0},
                    ]
                ),
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "false",
            },
        ],
    )
    def test_trace_dropped_by_trace_sampling_rule_tags(self, test_agent, test_library):
        """Test that a trace is dropped by the matching trace sampling rule"""
        with test_library, test_library.dd_start_span(name="web.request", service="webserver", resource="/bar") as span:
            span.set_meta("tag1", "val1")
            span.set_meta("tag2", "val2")
        span = find_only_span(test_agent.wait_for_num_traces(1))

        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == -1
        assert span["metrics"].get(SAMPLING_RULE_PRIORITY_RATE) == 0.0


def tag_sampling_env(tag_glob_pattern):
    return {
        "DD_TRACE_SAMPLE_RATE": 0,
        "DD_TRACE_SAMPLING_RULES": json.dumps(
            [{"tags": {"tag": tag_glob_pattern}, "sample_rate": 1.0}, {"sample_rate": 0}]
        ),
        "DD_TRACE_STATS_COMPUTATION_ENABLED": "false",
    }


@scenarios.parametric
@rfc("https://docs.google.com/document/d/1S9pufnJjrsxH6pRbpigdYFwA5JjSdZ6iLZ-9E7PoAic/")
@features.trace_sampling
@features.adaptive_sampling
class Test_Trace_Sampling_Tags_Feb2024_Revision:
    def assert_matching_span(self, test_agent, trace_id, span_id, name: str | None = None, service: str | None = None):
        matching_span = find_span_in_traces(test_agent.wait_for_num_traces(1), trace_id, span_id)

        assert matching_span["metrics"].get(SAMPLING_PRIORITY_KEY) == 2
        assert matching_span["metrics"].get(SAMPLING_RULE_PRIORITY_RATE) == 1.0

        if name is not None:
            assert matching_span["name"] == name

        if service is not None:
            assert matching_span["service"] == service

    def assert_mismatching_span(
        self, test_agent, trace_id, span_id, name: str | None = None, service: str | None = None
    ):
        mismatching_span = find_span_in_traces(test_agent.wait_for_num_traces(1), trace_id, span_id)

        assert mismatching_span["metrics"].get(SAMPLING_PRIORITY_KEY) == -1
        assert mismatching_span["metrics"].get(SAMPLING_RULE_PRIORITY_RATE) == 0.0

        if name is not None:
            assert mismatching_span["name"] == name

        if service is not None:
            assert mismatching_span["service"] == service

    @pytest.mark.parametrize(
        "library_env",
        [
            tag_sampling_env("foo"),
            tag_sampling_env("fo*"),
            tag_sampling_env("f??"),
            tag_sampling_env("?o*"),
            tag_sampling_env("???"),
            tag_sampling_env("*"),
            tag_sampling_env("**"),
        ],
    )
    def test_globs_same_casing(self, test_agent, test_library):
        """Test tag matching with string of matching case"""
        with test_library, test_library.dd_start_span(name="matching-span", service="test") as span:
            span.set_meta("tag", "foo")

        self.assert_matching_span(test_agent, span.trace_id, span.span_id, name="matching-span", service="test")

    @pytest.mark.parametrize(
        "library_env",
        [tag_sampling_env("Foo"), tag_sampling_env("Fo*"), tag_sampling_env("F??"), tag_sampling_env("?O*")],
    )
    @missing_feature(context.library < "nodejs@5.38.0", reason="Implemented in 5.38.0")
    def test_globs_different_casing(self, test_agent, test_library):
        """Test tag matching with string of matching case"""
        with test_library, test_library.dd_start_span(name="matching-span", service="test") as span:
            span.set_meta("tag", "foo")

        self.assert_matching_span(test_agent, span.trace_id, span.span_id, name="matching-span", service="test")

    @pytest.mark.parametrize("library_env", [tag_sampling_env("[abc]")])
    def test_no_set_support(self, test_agent, test_library):
        """Test verifying that common glob set extension is NOT supported"""
        with test_library, test_library.dd_start_span(name="matching-span", service="test") as span:
            span.set_meta("tag", "[abc]")

        self.assert_matching_span(test_agent, span.trace_id, span.span_id, name="matching-span", service="test")

    @pytest.mark.parametrize("library_env", [tag_sampling_env("[a-c]")])
    def test_no_range_support(self, test_agent, test_library):
        """Test verifying that common glob range extension is NOT supported"""
        with test_library, test_library.dd_start_span(name="matching-span", service="test") as span:
            span.set_meta("tag", "[a-c]")

        self.assert_matching_span(test_agent, span.trace_id, span.span_id, name="matching-span", service="test")

    @pytest.mark.parametrize("library_env", [tag_sampling_env("^(foo|bar)[]\\$")])
    def test_regex_special_chars(self, test_agent, test_library):
        """Test verifying that regex special chars doesn't break glob matching"""
        with test_library, test_library.dd_start_span(name="matching-span", service="test") as span:
            span.set_meta("tag", "^(foo|bar)[]\\$")

        self.assert_matching_span(test_agent, span.trace_id, span.span_id, name="matching-span", service="test")

    @pytest.mark.parametrize("library_env", [tag_sampling_env("*"), tag_sampling_env("**"), tag_sampling_env("***")])
    def test_meta_existence(self, test_agent, test_library):
        """Tests that any patterns are equivalent to an existence check for meta"""
        with test_library, test_library.dd_start_span(name="matching-span", service="test") as span:
            span.set_meta("tag", random.choice(["foo", "bar", "baz", "quux"]))

        self.assert_matching_span(test_agent, span.trace_id, span.span_id, name="matching-span", service="test")

    @pytest.mark.parametrize("library_env", [tag_sampling_env("*"), tag_sampling_env("**"), tag_sampling_env("***")])
    @pytest.mark.parametrize("tag_value", [-100, -0.5, 0, 5, 1000])
    @missing_feature(library="cpp", reason="No metric interface")
    @flaky(library="golang", reason="APMAPI-932")
    @missing_feature(context.library < "nodejs@5.38.0", reason="Implemented in 5.38.0")
    def test_metric_existence(self, test_agent, test_library, tag_value):
        """Tests that any patterns are equivalent to an existence check for metrics"""

        with test_library, test_library.dd_start_span(name="matching-span", service="test") as span:
            span.set_metric("tag", tag_value)

        self.assert_matching_span(test_agent, span.trace_id, span.span_id, name="matching-span", service="test")

    @pytest.mark.parametrize(
        "library_env", [tag_sampling_env("20"), tag_sampling_env("2*"), tag_sampling_env("2?"), tag_sampling_env("*")]
    )
    @missing_feature(library="cpp", reason="No metric interface")
    @missing_feature(context.library < "nodejs@5.38.0", reason="Implemented in 5.38.0")
    def test_metric_matching(self, test_agent, test_library):
        """Tests that any patterns are equivalent to an existence check for metrics"""
        with test_library, test_library.dd_start_span(name="matching-span", service="test") as span:
            span.set_metric("tag", 20.0)

        self.assert_matching_span(test_agent, span.trace_id, span.span_id, name="matching-span", service="test")

    @pytest.mark.parametrize("library_env", [tag_sampling_env("20"), tag_sampling_env("2*"), tag_sampling_env("2?")])
    def test_metric_mismatch_non_integer(self, test_agent, test_library):
        """Tests that any non-integer metrics mismatch patterns -- other than any patterns"""
        with test_library, test_library.dd_start_span(name="mismatching-span", service="test") as span:
            span.set_metric("tag", 20.1)

        self.assert_mismatching_span(test_agent, span.trace_id, span.span_id, name="mismatching-span", service="test")


@scenarios.parametric
@rfc("https://docs.google.com/document/d/1S9pufnJjrsxH6pRbpigdYFwA5JjSdZ6iLZ-9E7PoAic/")
@features.trace_sampling
@features.adaptive_sampling
class Test_Trace_Sampling_With_W3C:
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [
                        {"tags": {"tag2": "val2"}, "sample_rate": 0},
                        {"tags": {"tag1": "val1"}, "sample_rate": 1},
                        {"tags": {"tag0": "val*"}, "sample_rate": 0},
                    ]
                ),
            },
        ],
    )
    def test_trace_sampled_by_trace_sampling_rule_tags(self, test_agent, test_library):
        """Test that a trace is sampled by the rule and the sampling decision is locked"""

        with (
            test_library,
            test_library.dd_start_span(
                name="web.request", service="webserver", resource="/bar", tags=[["tag0", "val0"]]
            ) as span,
        ):
            # based on the Tag("tag0", "val0") start span option, span sampling would be 'drop',

            # setting new tags doesn't trigger re-sampling,
            # but injecting headers does. In such case, headers will reflect the state
            # after new pair of tags was set
            # based on the Tag("tag1", "val1"), span sampling would be 'keep'
            span.set_meta("tag1", "val1")
            headers = {k.lower(): v for k, v in test_library.dd_inject_headers(span.span_id)}

            # based on the Tag("tag2", "val2"), span sampling would be usually 'drop',
            # but since headers were injected already, the sampling priority won't change
            span.set_meta("tag2", "val2")

        span = find_only_span(test_agent.wait_for_num_traces(1))

        # sampling priority in headers reflects the state after new pair of tags was set
        assert headers["x-datadog-sampling-priority"] == "2"
        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == 2
        assert span["metrics"].get(SAMPLING_RULE_PRIORITY_RATE) == 1
