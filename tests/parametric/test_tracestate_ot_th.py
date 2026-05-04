# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2025 Datadog, Inc.

"""System test for W3C TraceState ot.th injection (Phase 3).

When propagating a sampled trace with tracecontext style the tracer must add an
ot=th:<hex> entry to the outgoing tracestate so that downstream collectors can
extrapolate aggregate metrics from sampled data.
"""

import pytest

from utils import features, scenarios
from utils.docker_fixtures.spec.tracecontext import get_tracecontext

from .conftest import APMLibrary

parametrize = pytest.mark.parametrize


def _tracecontext_inject_env() -> pytest.MarkDecorator:
    return parametrize("library_env", [{"DD_TRACE_PROPAGATION_STYLE_INJECT": "tracecontext"}])


@features.w3c_tracestate_ot_probability_threshold
@scenarios.parametric
class Test_Tracestate_OT_Probability_Threshold:
    """Outgoing tracestate must carry ot=th:<hex> when the span is sampled."""

    @_tracecontext_inject_env()
    def test_ot_th_injected_on_sampled_span(self, test_library: APMLibrary) -> None:
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [("traceparent", "00-12345678901234567890123456789012-1234567890123456-01")]
            )

        _, tracestate = get_tracecontext(headers)

        assert "ot" in tracestate, f"Expected 'ot' vendor entry in tracestate, got: {tracestate}"
        ot_value = tracestate["ot"]
        assert ot_value.startswith("th:"), f"Expected ot value to start with 'th:', got: {ot_value!r}"
