import pytest
from utils.parametric.spec.trace import Span
from utils.parametric.spec.trace import find_span_in_traces
import json
from utils import scenarios


@scenarios.parametric
class Test_Trace_Sampling:
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps([{"service": "webserver", "sample_rate": 1},]),
            },
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps([{"name": "web.request", "sample_rate": 1},]),
            },
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps([{"resource": "/bar", "sample_rate": 1},]),
            },
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [{"service": "webserver", "name": "web.request", "sample_rate": 1},]
                ),
            },
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps([{"name": "web.request", "resource": "/bar", "sample_rate": 1},]),
            },
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [{"service": "webserver", "resource": "/bar", "sample_rate": 1},]
                ),
            },
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [{"service": "webserver", "name": "web.request", "resource": "/bar", "sample_rate": 1},]
                ),
            },
        ],
    )
    def test_trace_sampled_by_defined_trace_sampling_rules_exact_match(self, test_agent, test_library):
        """Test that a trace is sampled by the matching defined trace sampling rules (exact match)"""
        with test_library:
            with test_library.start_span(name="web.request", service="webserver", resource="/bar"):
                pass
        span = find_span_in_traces(
            test_agent.wait_for_num_traces(1), Span(name="web.request", service="webserver", resource="/bar")
        )

        assert span["metrics"].get("_sampling_priority_v1") == 2

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps([{"service": "web*", "sample_rate": 1},]),
            },
            {"DD_TRACE_SAMPLE_RATE": 0, "DD_TRACE_SAMPLING_RULES": json.dumps([{"name": "web.*", "sample_rate": 1},])},
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps([{"resource": "/b*", "sample_rate": 1},]),
            },
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps([{"service": "*", "name": "web.req*", "sample_rate": 1},]),
            },
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps([{"name": "web*", "resource": "/b?r", "sample_rate": 1},]),
            },
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps([{"service": "webser???", "resource": "/b*", "sample_rate": 1},]),
            },
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [{"service": "web*", "name": "web.???????", "resource": "*", "sample_rate": 1},]
                ),
            },
        ],
    )
    def test_trace_sampled_by_defined_trace_sampling_rules_glob_match(self, test_agent, test_library):
        """Test that a trace is sampled by the matching defined trace sampling rules (glob match)"""
        with test_library:
            with test_library.start_span(name="web.request", service="webserver", resource="/bar"):
                pass
        span = find_span_in_traces(
            test_agent.wait_for_num_traces(1), Span(name="web.request", service="webserver", resource="/bar")
        )

        assert span["metrics"].get("_sampling_priority_v1") == 2

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TRACE_SAMPLE_RATE": 1,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [{"service": "webserver", "name": "web.request", "resource": "/bar", "sample_rate": 0},]
                ),
            }
        ],
    )
    def test_trace_dropped_by_defined_trace_sampling_rule(self, test_agent, test_library):
        """Test that a trace is dropped by the matching defined trace sampling rule"""
        with test_library:
            with test_library.start_span(name="web.request", service="webserver", resource="/bar"):
                pass
        span = find_span_in_traces(
            test_agent.wait_for_num_traces(1), Span(name="web.request", service="webserver", resource="/bar")
        )

        assert span["metrics"].get("_sampling_priority_v1") == -1

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [
                        {"service": "webserver", "name": "web.request", "resource": "/bar", "sample_rate": 1},
                        {"service": "webserver", "name": "web.request", "sample_rate": 0},
                    ]
                ),
            },
            {
                "DD_TRACE_SAMPLE_RATE": 0,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [
                        {"service": "webserver", "name": "web.request", "sample_rate": 1},
                        {"service": "webserver", "name": "web.request", "resource": "/bar", "sample_rate": 0},
                    ]
                ),
            },
        ],
    )
    def test_trace_sampled_by_first_matching_trace_sampling_rule(self, test_agent, test_library):
        """Test that a trace is sampled by the first matching trace sampling rules"""
        with test_library:
            with test_library.start_span(name="web.request", service="webserver", resource="/bar"):
                pass
        span = find_span_in_traces(
            test_agent.wait_for_num_traces(1), Span(name="web.request", service="webserver", resource="/bar")
        )

        assert span["metrics"].get("_sampling_priority_v1") == 2

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TRACE_SAMPLE_RATE": 1,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [
                        {"service": "webserver", "name": "web.request", "resource": "/bar", "sample_rate": 0},
                        {"service": "webserver", "name": "web.request", "sample_rate": 1},
                    ]
                ),
            },
            {
                "DD_TRACE_SAMPLE_RATE": 1,
                "DD_TRACE_SAMPLING_RULES": json.dumps(
                    [
                        {"service": "webserver", "name": "web.request", "sample_rate": 0},
                        {"service": "webserver", "name": "web.request", "resource": "/bar", "sample_rate": 1},
                    ]
                ),
            },
        ],
    )
    def test_trace_dropped_by_first_matching_trace_sampling_rule(self, test_agent, test_library):
        """Test that a trace is dropped by the first matching trace sampling rules"""
        with test_library:
            with test_library.start_span(name="web.request", service="webserver", resource="/bar"):
                pass
        span = find_span_in_traces(
            test_agent.wait_for_num_traces(1), Span(name="web.request", service="webserver", resource="/bar")
        )

        assert span["metrics"].get("_sampling_priority_v1") == -1
