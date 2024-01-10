"""sampling delegation

These tests verify the behavior of [sampling delegation][1] for APM tracing
libraries.

[1]: https://github.com/DataDog/architecture/tree/master/rfcs/apm/integrations/sampling-delegation
"""

import pytest
from utils import scenarios


@scenarios.parametric
class Test_Sampling_Delegation:

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                # Extract in the Datadog style, so that a sampling decision is
                # conveyed by the X-Datadog-Sampling-Priority and X-Datadog-Tags
                # headers.
                "DD_TRACE_PROPAGATION_STYLE": "Datadog",
                # When the tracer makes its own sampling decision, let it always
                # be "keep." We can detect whether the tracer made the decision
                # itself by seeing whether the resulting sampling mechanism is
                # "trace sampling rule" (3).
                # Sampling mechanism values are defined [here][1].
                #
                # [1]: https://docs.google.com/document/d/1zeO6LGnvxk5XweObHAwJbK3SfK23z7jQzp7ozWJTa2A/edit#heading=h.2nfwolfi3o1j
                "DD_TRACE_SAMPLE_RATE": "1.0",
            }
        ],
    )
    def test_sampling_delegation_extract_neither_decision_nor_delegation(
            self, test_agent, test_library):
        """Make your own sampling decision when the client doesn't send one.

        The behavior tested here is not specified in the sampling delegation
        RFC. However, the behavior is helpful to Real User Monitoring (RUM) as
        we transition to full support for sampling delegation.

        When trace context is extracted from an incoming request, the context
        might include a sampling decision for the trace, and it might not. If it
        doesn't include a sampling decision for the trace, then context
        extraction should still succeed, and the tracer should make its own
        sampling decision.

        This is relevant to RUM. See this [doc][1] for an explanation of why.

        [1]: https://docs.google.com/document/d/1w7qe6Jp9vF6HmRA5bNjzZI9JxmXq8cwscqpUPpF686Y
        """
        trace_id = 1212121212121212121
        span_args = {
            "name": "name",
            "service": "service",
            "resource": "resource",
            "http_headers": [
                ["x-datadog-trace-id", str(trace_id)],
                # Specifying an origin allows for parent ID to be omitted.
                ["x-datadog-origin", "rum"],
            ]
        }
        with test_library:
            with test_library.start_span(**span_args):
                pass

        trace, = test_agent.wait_for_num_traces(1)
        assert len(trace) == 1
        span, = trace
        # Extraction succeeded if the span produced by the tracer has the same
        # trace ID mentioned in the headers.
        assert span["trace_id"] == trace_id
        # If the tracer made its own sampling decision, then the decision will
        # be associated with mechanism 3 ("trace sampling rule"), because we set
        # DD_TRACE_SAMPLE_RATE. If, on the other hand, the tracer inferred a
        # decision from the extracted context, then the mechanism would probably
        # have some other value.
        assert "_dd.p.dm" in span["meta"]
        # The "-" is a separating hyphen, not a minus sign.
        assert span["meta"]["_dd.p.dm"] == "-3"
        # DD_TRACE_SAMPLE_RATE is 1.0 (100%), so the sampling priority should be
        # 2 ("user/manual keep").
        assert "_sampling_priority_v1" in span["metrics"]
        assert span["metrics"]["_sampling_priority_v1"] == 2
