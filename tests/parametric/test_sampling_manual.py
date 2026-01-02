"""manual keep sampling

These tests verify the behavior manual keep sampling for APM tracing
libraries.
"""

import pytest
from utils import features, rfc, scenarios
from utils.parametric.spec.trace import SAMPLING_DECISION_MAKER_KEY
from utils.dd_constants import SAMPLING_PRIORITY_KEY
from utils.dd_constants import SamplingMechanism
from utils.dd_constants import SamplingPriority


@features.ensure_that_sampling_is_consistent_across_languages
@scenarios.parametric
@rfc("https://docs.google.com/document/d/1HRbi1DrBjL_KGeONrPgH7lblgqSLGlV5Ox1p4RL97xM/")
class Test_Manual_Keep_Sampling:
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TRACE_PROPAGATION_STYLE": "Datadog",
                "DD_TRACE_SAMPLE_RATE": "0",  # Disable automatic sampling
                "DD_TRACE_SAMPLING_RULES": '[{"sample_rate":0}]',  # Ensure no rule-based sampling
                # Force dropped traces to be sent to the agent in the cases
                # where the tracer does not override the sampling decision
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "false",
            }
        ],
    )
    def test_sampling_manual_override(self, test_agent, test_library):
        """Test that the manual keep sampling override is respected"""
        trace_id = 1212121212121212121
        parent_id = 34343434
        test_library.dd_extract_headers(
            [
                ["x-datadog-trace-id", str(trace_id)],
                ["x-datadog-parent-id", str(parent_id)],
                ["x-datadog-sampling-priority", "0"],  # Drop decision from upstream
            ]
        )
        span_args = {
            "name": "name",
            "service": "service",
            "resource": "resource",
            "parent_id": parent_id,
        }
        with test_library, test_library.dd_start_span(**span_args) as span:
            span.manual_keep()

        (trace,) = test_agent.wait_for_num_traces(1)
        assert len(trace) == 1
        (span,) = trace

        # Verify trace context inheritance
        assert span["trace_id"] == trace_id
        assert span["parent_id"] == parent_id

        # Verify manual keep overrode the extracted drop decision
        assert SAMPLING_PRIORITY_KEY in span["metrics"]
        assert span["metrics"][SAMPLING_PRIORITY_KEY] == SamplingPriority.USER_KEEP

        # Verify decision maker shows manual decision (mechanism 4)
        assert SAMPLING_DECISION_MAKER_KEY in span["meta"]
        assert span["meta"][SAMPLING_DECISION_MAKER_KEY] == "-" + str(SamplingMechanism.MANUAL)
