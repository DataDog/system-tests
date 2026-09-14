"""Cross-tracer conformance for OpenTelemetry consistent probability sampling (ot.th / ot.rv) on the wire."""

import json

import pytest

from utils import features, scenarios
from utils.dd_constants import SamplingPriority
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.spec.trace import SAMPLING_PRIORITY_KEY, find_trace
from utils.docker_fixtures.spec.tracecontext import Tracestate, get_tracecontext

from .conftest import APMLibrary
from tests.otel.utils import (
    FORWARD_RV,
    FORWARD_TH,
    FORWARD_TRACE_ID,
    SAMPLING_RATE_0_01,
    SAMPLING_RATE_0_1,
    SAMPLING_RATE_0_2,
    SAMPLING_RATE_0_5,
    SAMPLING_RATE_0_99,
    TH_BY_RATE,
)


def _traceparent(trace_id: int, *, sampled: bool) -> str:
    return f"00-{trace_id:032x}-0000000000000001-{'01' if sampled else '00'}"


def _parse_ot(tracestate: Tracestate | str) -> dict[str, str]:
    """Split the ot= list-member into its rv/th sub-keys. Sub-key order isn't guaranteed by spec."""
    if isinstance(tracestate, str):
        tracestate = Tracestate(tracestate)

    if "ot" not in tracestate:
        return {}

    parsed = {}
    for item in tracestate["ot"].split(";"):
        if ":" not in item:
            continue
        key, _, value = item.partition(":")
        parsed[key] = value
    return parsed


def _library_env(rate: float) -> dict[str, str]:
    return {
        "DD_TRACE_RATE_LIMIT": "10000000",
        "DD_TRACE_SAMPLE_RATE": str(rate),
        "DD_TRACE_SAMPLING_RULES": json.dumps([{"sample_rate": rate}]),
        "DD_TRACE_STATS_COMPUTATION_ENABLED": "false",
    }


def _make_child_headers(test_library: APMLibrary, headers: list[tuple[str, str]]) -> dict[str, str]:
    return test_library.dd_make_child_span_and_get_headers(headers)


def _make_manual_keep_headers(test_library: APMLibrary, headers: list[tuple[str, str]]) -> dict[str, str]:
    with test_library.dd_extract_headers_and_make_child_span("name", headers) as span:
        span.manual_keep()
        return {key.lower(): value for key, value in test_library.dd_inject_headers(span.span_id)}


def _make_root_manual_keep_headers(test_library: APMLibrary) -> dict[str, str]:
    with test_library.dd_start_span("name") as span:
        span.manual_keep()
        return {key.lower(): value for key, value in test_library.dd_inject_headers(span.span_id)}


SAMPLE_RATE_VECTORS = [
    pytest.param(_library_env(0.01), 0.01, SAMPLING_RATE_0_01, id="rate-0.01"),
    pytest.param(_library_env(0.1), 0.1, SAMPLING_RATE_0_1, id="rate-0.1"),
    pytest.param(_library_env(0.2), 0.2, SAMPLING_RATE_0_2, id="rate-0.2"),
    pytest.param(_library_env(0.5), 0.5, SAMPLING_RATE_0_5, id="rate-0.5"),
    pytest.param(_library_env(0.99), 0.99, SAMPLING_RATE_0_99, id="rate-0.99"),
]


@features.w3c_headers_injection_and_extraction
@scenarios.parametric
class Test_OtelTracestateSampling:
    @pytest.mark.parametrize(("library_env", "rate", "vectors"), SAMPLE_RATE_VECTORS)
    def test_emits_probability_sampling_vectors(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        rate: float,
        vectors: list[tuple[int, str, bool]],
    ) -> None:
        """A1: a probability sampling decision produces ot=rv:...;th:... consistent with the decision."""
        with test_library:
            for trace_id, expected_rv, expected_sampled in vectors:
                headers = test_library.dd_make_child_span_and_get_headers(
                    [
                        ("x-datadog-trace-id", str(trace_id)),
                        ("x-datadog-parent-id", str(trace_id)),
                    ]
                )
                traceparent, tracestate = get_tracecontext(headers)
                ot = _parse_ot(tracestate)

                assert ot == {"rv": expected_rv, "th": TH_BY_RATE[rate]}
                assert (traceparent.trace_flags == "01") is expected_sampled

        traces = test_agent.wait_for_num_traces(len(vectors))
        for trace_id, _, expected_sampled in vectors:
            (span,) = find_trace(traces, trace_id)
            sampling_priority = span["metrics"].get(SAMPLING_PRIORITY_KEY)
            assert sampling_priority is not None
            assert (sampling_priority in (SamplingPriority.AUTO_KEEP, SamplingPriority.USER_KEEP)) is expected_sampled

    @pytest.mark.parametrize("library_env", [_library_env(0.1)])
    def test_forwards_inbound_ot(self, test_library: APMLibrary) -> None:
        """A2: DD honors an already-decided upstream trace; ot=rv:...;th:... is forwarded unchanged, never re-derived."""
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", _traceparent(FORWARD_TRACE_ID, sampled=True)),
                    ("tracestate", f"ot=rv:{FORWARD_RV};th:{FORWARD_TH}"),
                ]
            )

        _, tracestate = get_tracecontext(headers)
        assert _parse_ot(tracestate) == {"rv": FORWARD_RV, "th": FORWARD_TH}

    @pytest.mark.parametrize("library_env", [_library_env(0.1)])
    def test_sanitizes_malformed_inbound_ot(self, test_library: APMLibrary) -> None:
        """A6: malformed ot= fields are cleared rather than re-derived."""
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", _traceparent(FORWARD_TRACE_ID, sampled=True)),
                    ("tracestate", "dd=s:1,ot=rv:not-hex;th:not-hex,congo=xyz123"),
                ]
            )

        _, tracestate = get_tracecontext(headers)
        assert "ot" not in tracestate
        assert "dd" in tracestate
        assert tracestate["congo"] == "xyz123"

    @pytest.mark.parametrize("library_env", [_library_env(0.1)])
    def test_forwards_th_only_inbound_ot(self, test_library: APMLibrary) -> None:
        """A2b: an inherited th is forwarded without a fabricated rv."""
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", _traceparent(FORWARD_TRACE_ID, sampled=True)),
                    ("tracestate", f"ot=th:{FORWARD_TH}"),
                ]
            )

        _, tracestate = get_tracecontext(headers)
        assert _parse_ot(tracestate) == {"th": FORWARD_TH}

    @pytest.mark.parametrize("library_env", [_library_env(0.1)])
    def test_preserves_other_tracestate_members(self, test_library: APMLibrary) -> None:
        """A3: ot= handling does not disturb other tracestate members."""
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", _traceparent(FORWARD_TRACE_ID, sampled=True)),
                    ("tracestate", f"dd=s:2;t.dm:-3,ot=rv:{FORWARD_RV};th:{FORWARD_TH},congo=t61rcWkgMzE"),
                ]
            )

        _, tracestate = get_tracecontext(headers)
        assert "s:2" in tracestate["dd"].split(";")
        assert tracestate["congo"] == "t61rcWkgMzE"

    @pytest.mark.parametrize("library_env", [_library_env(0.1)])
    def test_forwards_unknown_inbound_ot_subkeys(self, test_library: APMLibrary) -> None:
        # OTEP 235 defines only rv/th today but reserves room for more ot= sub-keys. An unknown sub-key
        # inherited from upstream must be forwarded verbatim, never dropped from an inherited decision.
        inherited = f"ot=rv:{FORWARD_RV};th:{FORWARD_TH};foo:bar"
        # Unknown-only variant: an ot= with no rv/th carries no sampling decision, so its sub-key must
        # still be forwarded verbatim and DD must not mistake it for a decision by fabricating rv/th.
        unknown_only = "ot=foo:bar"

        with test_library:
            inherited_headers = _make_child_headers(
                test_library,
                [
                    ("traceparent", _traceparent(FORWARD_TRACE_ID, sampled=True)),
                    ("tracestate", inherited),
                ],
            )
            unknown_only_headers = _make_child_headers(
                test_library,
                [
                    ("traceparent", _traceparent(FORWARD_TRACE_ID, sampled=True)),
                    ("tracestate", unknown_only),
                ],
            )

        _, inherited_tracestate = get_tracecontext(inherited_headers)
        assert _parse_ot(inherited_tracestate) == {"rv": FORWARD_RV, "th": FORWARD_TH, "foo": "bar"}

        _, unknown_only_tracestate = get_tracecontext(unknown_only_headers)
        assert _parse_ot(unknown_only_tracestate) == {"foo": "bar"}

    @pytest.mark.parametrize("library_env", [_library_env(0.1)])
    def test_forwards_dropped_inbound_ot(self, test_library: APMLibrary) -> None:
        """A2c: A2's forward-unchanged rule holds for a dropped decision too, not just a kept one."""
        with test_library:
            headers = _make_child_headers(
                test_library,
                [
                    ("traceparent", _traceparent(FORWARD_TRACE_ID, sampled=False)),
                    ("tracestate", f"dd=s:0,ot=rv:{FORWARD_RV};th:{FORWARD_TH}"),
                ],
            )

        traceparent, tracestate = get_tracecontext(headers)
        assert traceparent.trace_flags == "00"
        assert _parse_ot(tracestate) == {"rv": FORWARD_RV, "th": FORWARD_TH}

    @pytest.mark.parametrize("library_env", [_library_env(0.1)])
    def test_dropped_th_only_does_not_fabricate_rv(self, test_library: APMLibrary) -> None:
        """A2d: A2b's no-fabrication rule holds for a dropped decision too, not just a kept one."""
        with test_library:
            headers = _make_child_headers(
                test_library,
                [
                    ("traceparent", _traceparent(FORWARD_TRACE_ID, sampled=False)),
                    ("tracestate", f"ot=th:{FORWARD_TH}"),
                ],
            )

        traceparent, tracestate = get_tracecontext(headers)
        assert traceparent.trace_flags == "00"
        assert _parse_ot(tracestate) == {"th": FORWARD_TH}

    @pytest.mark.parametrize("library_env", [_library_env(0.1)])
    def test_force_keep_does_not_add_ot(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with test_library:
            headers = _make_root_manual_keep_headers(test_library)

        traceparent, tracestate = get_tracecontext(headers)
        assert traceparent.trace_flags == "01"
        assert "ot" not in tracestate

        (trace,) = test_agent.wait_for_num_traces(1)
        (span,) = trace
        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == SamplingPriority.USER_KEEP

    @pytest.mark.parametrize("library_env", [_library_env(0.1)])
    def test_force_keep_forwards_inherited_rv(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with test_library:
            headers = _make_manual_keep_headers(
                test_library,
                [
                    ("traceparent", _traceparent(FORWARD_TRACE_ID, sampled=False)),
                    ("tracestate", "ot=rv:1234567890abcd"),
                ],
            )

        traceparent, tracestate = get_tracecontext(headers)
        assert traceparent.trace_flags == "01"
        assert _parse_ot(tracestate) == {"rv": "1234567890abcd"}

        (trace,) = test_agent.wait_for_num_traces(1)
        (span,) = trace
        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == SamplingPriority.USER_KEEP

    @pytest.mark.parametrize("library_env", [_library_env(0.1)])
    def test_force_keep_clears_inherited_th(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with test_library:
            headers = _make_manual_keep_headers(
                test_library,
                [
                    ("traceparent", _traceparent(10, sampled=False)),
                    ("tracestate", "ot=rv:65cd67504a538e;th:e6666666666668"),
                ],
            )

        traceparent, tracestate = get_tracecontext(headers)
        assert traceparent.trace_flags == "01"
        assert _parse_ot(tracestate) == {"rv": "65cd67504a538e"}

        (trace,) = test_agent.wait_for_num_traces(1)
        (span,) = trace
        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == SamplingPriority.USER_KEEP

    @pytest.mark.parametrize("library_env", [_library_env(0.1)])
    def test_sampled_without_ot_does_not_fabricate_it(self, test_library: APMLibrary) -> None:
        """A5: an inbound trace already sampled (W3C flag) but with no ot= is honored; th/rv are never fabricated."""
        # A parent-based child with an unknown upstream probability cannot create `th` or `rv`.
        with test_library:
            headers = _make_child_headers(
                test_library,
                [
                    ("traceparent", _traceparent(FORWARD_TRACE_ID, sampled=True)),
                    ("tracestate", "dd=s:1"),
                ],
            )

        traceparent, tracestate = get_tracecontext(headers)
        assert traceparent.trace_flags == "01"
        assert "ot" not in tracestate

    @pytest.mark.parametrize("library_env", [_library_env(0.1)])
    def test_malformed_th_preserves_rv(self, test_library: APMLibrary) -> None:
        """Th malformed, rv otherwise well-formed: th is cleared, but the well-formed rv is still forwarded."""
        with test_library:
            headers = _make_child_headers(
                test_library,
                [
                    ("traceparent", _traceparent(FORWARD_TRACE_ID, sampled=True)),
                    ("tracestate", "ot=rv:1234567890abcd;th:not-hex-either"),
                ],
            )

        _, tracestate = get_tracecontext(headers)
        assert _parse_ot(tracestate) == {"rv": "1234567890abcd"}

    @pytest.mark.parametrize(
        ("library_env", "trace_id", "expected_th", "expected_rv", "expected_sampled"),
        [
            # DD keeps (h below threshold) but the naive 56-bit rv falls just short of th; rv is bumped up to th.
            pytest.param(
                _library_env(0.1),
                0x03A93EE8B1999F00,
                "e6666666666668",
                "e6666666666668",
                True,
                id="rate-0.1-kept",
            ),
            # DD drops (h above threshold) but the naive 56-bit rv would read as kept; rv is bumped down to th - 1.
            pytest.param(
                _library_env(0.05),
                5401449561355763072,
                "f333333333333",
                "f333333333332f",
                False,
                id="rate-0.05-dropped",
            ),
        ],
    )
    def test_precision_boundary_decisions(
        self,
        test_library: APMLibrary,
        trace_id: int,
        expected_th: str,
        expected_rv: str,
        *,
        expected_sampled: bool,
    ) -> None:
        """A7: on a boundary trace ID, the 64-bit hash decision and the naive 56-bit (rv, th) pair disagree; DD must
        adjust rv (never th) so that (rv >= th) reproduces its own keep/drop exactly.

        See the RFC's "64-bit to 56-bit precision" section: DD keeps but rv < th -> rv = th;
        DD drops but rv >= th -> rv = th - 1.
        """
        with test_library:
            headers = _make_child_headers(
                test_library,
                [
                    ("x-datadog-trace-id", str(trace_id)),
                    ("x-datadog-parent-id", str(trace_id)),
                ],
            )

        traceparent, tracestate = get_tracecontext(headers)
        assert _parse_ot(tracestate) == {"rv": expected_rv, "th": expected_th}
        assert (traceparent.trace_flags == "01") is expected_sampled
