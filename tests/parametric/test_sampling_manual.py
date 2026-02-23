"""manual keep sampling

This test verifies the behavior manual keep sampling for APM tracing
libraries.

Manual keep sampling should take precedence over any other sampling decision.
"""

import pytest
from utils import features, rfc, scenarios
from utils.dd_constants import SamplingMechanism
from utils.dd_constants import SamplingPriority
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.spec.trace import Span
from utils.docker_fixtures.spec.trace import SAMPLING_PRIORITY_KEY
from utils.docker_fixtures.spec.trace import SAMPLING_DECISION_MAKER_KEY
from .conftest import APMLibrary


@features.ensure_that_sampling_is_consistent_across_languages
@scenarios.parametric
@rfc("https://docs.google.com/document/d/1HRbi1DrBjL_KGeONrPgH7lblgqSLGlV5Ox1p4RL97xM/")
class Test_Manual_Sampling:
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TRACE_PROPAGATION_STYLE": "Datadog",
                "DD_TRACE_SAMPLE_RATE": "0",  # Disable automatic sampling
                # Ensure no rule-based sampling
                "DD_TRACE_SAMPLING_RULES": '[{"sample_rate":0}]',
                # Force dropped traces to be sent to the agent in the cases
                # where the tracer does not override the sampling decision
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "false",
            }
        ],
    )
    def test_sampling_manual_keep(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Test that the manual keep sampling takes precedence over a
        transmitted sampling decision

        The upstream drop decision should be replaced by a user keep decision.

        _sampling_priority_v1: 4 (user keep)
        _dd.p.dm: -4 (manual)
        """
        kept_trace_id = 1212121212121212121
        kept_parent_id = 34343434
        test_library.dd_extract_headers(
            [
                ("x-datadog-trace-id", str(kept_trace_id)),
                ("x-datadog-parent-id", str(kept_parent_id)),
                # Drop decision from upstream
                ("x-datadog-sampling-priority", "0"),
            ]
        )

        with (
            test_library,
            test_library.dd_start_span(
                name="name", service="service", resource="resource", parent_id=kept_parent_id
            ) as span,
        ):
            span.manual_keep()

        (trace,) = test_agent.wait_for_num_traces(1)
        assert len(trace) == 1
        kept_span: Span
        (kept_span,) = trace

        # Verify trace context inheritance
        assert kept_span["trace_id"] == kept_trace_id
        assert kept_span["parent_id"] == kept_parent_id

        # Verify manual keep overrode the extracted drop decision
        assert SAMPLING_PRIORITY_KEY in kept_span["metrics"]
        assert kept_span["metrics"][SAMPLING_PRIORITY_KEY] == SamplingPriority.USER_KEEP

        # Verify decision maker shows manual decision (mechanism 4)
        assert SAMPLING_DECISION_MAKER_KEY in kept_span["meta"]
        assert kept_span["meta"][SAMPLING_DECISION_MAKER_KEY] == "-" + str(SamplingMechanism.MANUAL)
