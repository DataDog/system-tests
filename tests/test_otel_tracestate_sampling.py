# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Cross-tracer conformance for OpenTelemetry consistent probability sampling (ot.th / ot.rv) on the wire.

See APMAPI-2171. Landed disabled for every tracer (manifests/*.yml); each tracer enables these as it ships.
"""

import json

from utils import HttpResponse, features, interfaces, scenarios, weblog
from utils.dd_constants import SamplingPriority
from utils.docker_fixtures.spec.tracecontext import Tracestate, get_tracestate

# ---------------------------------------------------------------------------
# Expected ot.rv / ot.th values for known trace IDs and known sample rates
#
# DD's sampling decision is h = (trace_id_low64 * 1111111111111111111) mod 2**64, keep if h <= rate * (2**64 - 1)
# (dd-trace-go/ddtrace/tracer/sampler.go:114-122). The OTel-compatible pair is:
#   rv = (~h & (2**64 - 1)) >> 8      (56-bit, 14 hex digits) -- depends only on trace_id, not on rate
#   th = int((1 - rate) * (2**56))   (56-bit, trailing zero nibbles trimmed when formatted) -- depends only on rate
#
# Trace IDs are the ones already used (and verified) in tests/fixtures/sampling_rates.csv, crossed with
# 5 rates. Expected values below were computed with the formula above and cross-checked: at rate 0.5 they
# reproduce the exact same keep/drop decisions as that CSV for all 23 trace IDs.
# ---------------------------------------------------------------------------

TH_BY_RATE = {
    0.01: "fd70a3d70a3d7",
    0.1: "e6666666666668",
    0.2: "ccccccccccccd",
    0.5: "8",
    0.99: "028f5c28f5c29",
}

SAMPLING_RATE_0_01 = [
    # (trace_id, expected_rv_hex, expected_sampled)
    (1, "f0948a54d43b8e", False),
    (10, "65cd67504a538e", False),
    (100, "fa060922e7438e", False),
    (1000, "c43c5b5d08a38e", False),
    (18444899399302180860, "1d6aabcffddf37", False),
    (18444899399302180861, "0dff3624d21ac5", False),
    (18444899399302180862, "fe93c079a65653", True),
    (18444899399302180863, "ef284ace7a91e1", False),
    (18446744073709551615, "0f6b75ab2bc471", False),
    (9223372036854775809, "70948a54d43b8e", False),
    (9223372036854775807, "8f6b75ab2bc471", False),
    (4611686018427387905, "30948a54d43b8e", False),
    (4611686018427387903, "4f6b75ab2bc471", False),
    (646771306295669658, "899fbcfd433be9", False),
    (1882305164521835798, "9d38be3d27241d", False),
    (5198373796167680436, "7188fdce730439", False),
    (6272545487220484606, "bea00261cb73bd", False),
    (8696342848850656916, "ca47c7b1ab2e46", False),
    (10197320802478874805, "d29c6d21f144ee", False),
    (10350218024687037124, "d6dc160c1c68fd", False),
    (12078589664685934330, "3a7d76f3c5a379", False),
    (13794769880582338323, "a6c17470cee7cd", False),
    (14629469446186818297, "295fd564326a5f", False),
    (83, "0028d980cf4f1c", False),
]

SAMPLING_RATE_0_1 = [
    # (trace_id, expected_rv_hex, expected_sampled)
    (1, "f0948a54d43b8e", True),
    (10, "65cd67504a538e", False),
    (100, "fa060922e7438e", True),
    (1000, "c43c5b5d08a38e", False),
    (18444899399302180860, "1d6aabcffddf37", False),
    (18444899399302180861, "0dff3624d21ac5", False),
    (18444899399302180862, "fe93c079a65653", True),
    (18444899399302180863, "ef284ace7a91e1", True),
    (18446744073709551615, "0f6b75ab2bc471", False),
    (9223372036854775809, "70948a54d43b8e", False),
    (9223372036854775807, "8f6b75ab2bc471", False),
    (4611686018427387905, "30948a54d43b8e", False),
    (4611686018427387903, "4f6b75ab2bc471", False),
    (646771306295669658, "899fbcfd433be9", False),
    (1882305164521835798, "9d38be3d27241d", False),
    (5198373796167680436, "7188fdce730439", False),
    (6272545487220484606, "bea00261cb73bd", False),
    (8696342848850656916, "ca47c7b1ab2e46", False),
    (10197320802478874805, "d29c6d21f144ee", False),
    (10350218024687037124, "d6dc160c1c68fd", False),
    (12078589664685934330, "3a7d76f3c5a379", False),
    (13794769880582338323, "a6c17470cee7cd", False),
    (14629469446186818297, "295fd564326a5f", False),
    (83, "0028d980cf4f1c", False),
]

SAMPLING_RATE_0_2 = [
    # (trace_id, expected_rv_hex, expected_sampled)
    (1, "f0948a54d43b8e", True),
    (10, "65cd67504a538e", False),
    (100, "fa060922e7438e", True),
    (1000, "c43c5b5d08a38e", False),
    (18444899399302180860, "1d6aabcffddf37", False),
    (18444899399302180861, "0dff3624d21ac5", False),
    (18444899399302180862, "fe93c079a65653", True),
    (18444899399302180863, "ef284ace7a91e1", True),
    (18446744073709551615, "0f6b75ab2bc471", False),
    (9223372036854775809, "70948a54d43b8e", False),
    (9223372036854775807, "8f6b75ab2bc471", False),
    (4611686018427387905, "30948a54d43b8e", False),
    (4611686018427387903, "4f6b75ab2bc471", False),
    (646771306295669658, "899fbcfd433be9", False),
    (1882305164521835798, "9d38be3d27241d", False),
    (5198373796167680436, "7188fdce730439", False),
    (6272545487220484606, "bea00261cb73bd", False),
    (8696342848850656916, "ca47c7b1ab2e46", False),
    (10197320802478874805, "d29c6d21f144ee", True),
    (10350218024687037124, "d6dc160c1c68fd", True),
    (12078589664685934330, "3a7d76f3c5a379", False),
    (13794769880582338323, "a6c17470cee7cd", False),
    (14629469446186818297, "295fd564326a5f", False),
    (83, "0028d980cf4f1c", False),
]

SAMPLING_RATE_0_5 = [
    # (trace_id, expected_rv_hex, expected_sampled)
    (1, "f0948a54d43b8e", True),
    (10, "65cd67504a538e", False),
    (100, "fa060922e7438e", True),
    (1000, "c43c5b5d08a38e", True),
    (18444899399302180860, "1d6aabcffddf37", False),
    (18444899399302180861, "0dff3624d21ac5", False),
    (18444899399302180862, "fe93c079a65653", True),
    (18444899399302180863, "ef284ace7a91e1", True),
    (18446744073709551615, "0f6b75ab2bc471", False),
    (9223372036854775809, "70948a54d43b8e", False),
    (9223372036854775807, "8f6b75ab2bc471", True),
    (4611686018427387905, "30948a54d43b8e", False),
    (4611686018427387903, "4f6b75ab2bc471", False),
    (646771306295669658, "899fbcfd433be9", True),
    (1882305164521835798, "9d38be3d27241d", True),
    (5198373796167680436, "7188fdce730439", False),
    (6272545487220484606, "bea00261cb73bd", True),
    (8696342848850656916, "ca47c7b1ab2e46", True),
    (10197320802478874805, "d29c6d21f144ee", True),
    (10350218024687037124, "d6dc160c1c68fd", True),
    (12078589664685934330, "3a7d76f3c5a379", False),
    (13794769880582338323, "a6c17470cee7cd", True),
    (14629469446186818297, "295fd564326a5f", False),
    (83, "0028d980cf4f1c", False),
]

SAMPLING_RATE_0_99 = [
    # (trace_id, expected_rv_hex, expected_sampled)
    (1, "f0948a54d43b8e", True),
    (10, "65cd67504a538e", True),
    (100, "fa060922e7438e", True),
    (1000, "c43c5b5d08a38e", True),
    (18444899399302180860, "1d6aabcffddf37", True),
    (18444899399302180861, "0dff3624d21ac5", True),
    (18444899399302180862, "fe93c079a65653", True),
    (18444899399302180863, "ef284ace7a91e1", True),
    (18446744073709551615, "0f6b75ab2bc471", True),
    (9223372036854775809, "70948a54d43b8e", True),
    (9223372036854775807, "8f6b75ab2bc471", True),
    (4611686018427387905, "30948a54d43b8e", True),
    (4611686018427387903, "4f6b75ab2bc471", True),
    (646771306295669658, "899fbcfd433be9", True),
    (1882305164521835798, "9d38be3d27241d", True),
    (5198373796167680436, "7188fdce730439", True),
    (6272545487220484606, "bea00261cb73bd", True),
    (8696342848850656916, "ca47c7b1ab2e46", True),
    (10197320802478874805, "d29c6d21f144ee", True),
    (10350218024687037124, "d6dc160c1c68fd", True),
    (12078589664685934330, "3a7d76f3c5a379", True),
    (13794769880582338323, "a6c17470cee7cd", True),
    (14629469446186818297, "295fd564326a5f", True),
    (83, "0028d980cf4f1c", False),
]


def _traceparent(trace_id: int, *, sampled: bool) -> str:
    return f"00-{trace_id:032x}-0000000000000001-{'01' if sampled else '00'}"


def _outbound_tracestate(request: HttpResponse) -> Tracestate:
    """Parse the tracestate the weblog injected into its own downstream call (see /make_distant_call)."""
    data = json.loads(request.text)
    return get_tracestate(data["request_headers"])


def _parse_ot(tracestate: Tracestate) -> dict[str, str]:
    """Split the ot= list-member into its rv/th sub-keys. Sub-key order isn't guaranteed by spec."""
    if "ot" not in tracestate:
        return {}

    parsed = {}
    for item in tracestate["ot"].split(";"):
        if ":" not in item:
            continue
        key, _, value = item.partition(":")
        parsed[key] = value
    return parsed


def _priority_should_be_kept(sampling_priority: int) -> bool:
    return sampling_priority in (SamplingPriority.AUTO_KEEP, SamplingPriority.USER_KEEP)


class _EmitOtOnProbabilityDecisionBase:
    """A1: a probability sampling decision produces ot=rv:...;th:... consistent with the decision.

    Subclasses fix a scenario (hence a configured sample rate) and its matching trace IDs / expected values.
    """

    RATE: float
    TRACE_IDS: list[tuple[int, str, bool]]

    def setup_emit_ot_on_probability_decision(self):
        expected_th = TH_BY_RATE[self.RATE]
        self.requests = [
            (
                weblog.get(
                    "/make_distant_call",
                    params={"url": "http://weblog:7777"},
                    headers={"x-datadog-trace-id": str(trace_id), "x-datadog-parent-id": str(trace_id)},
                ),
                trace_id,
                expected_rv,
                expected_th,
                expected_sampled,
            )
            for trace_id, expected_rv, expected_sampled in self.TRACE_IDS
        ]

    def test_emit_ot_on_probability_decision(self):
        for req, trace_id, expected_rv, expected_th, expected_sampled in self.requests:
            assert req.status_code == 200, f"trace_id={trace_id}: /make_distant_call failed"

            tracestate = _outbound_tracestate(req)
            assert "ot" in tracestate, f"trace_id={trace_id}: no ot= tracestate member emitted on a probability decision"
            ot = _parse_ot(tracestate)

            assert ot.get("rv") == expected_rv, f"trace_id={trace_id}: rv={ot.get('rv')!r}, expected {expected_rv!r}"
            assert ot.get("th") == expected_th, f"trace_id={trace_id}: th={ot.get('th')!r}, expected {expected_th!r}"

            # the configured sample rate must be recoverable from th alone: rate = 1 - th / 2**56
            recovered_rate = 1 - int(ot["th"], 16) / (1 << 56)
            assert abs(recovered_rate - self.RATE) < 1e-6, (
                f"trace_id={trace_id}: rate recomputed from th ({recovered_rate}) "
                f"doesn't match the configured rate ({self.RATE})"
            )

            for _, _, span in interfaces.library.get_spans(request=req):
                sampling_priority = span.get_sampling_priority()
                assert sampling_priority is not None, f"trace_id={trace_id}: no sampling priority on span"
                assert _priority_should_be_kept(sampling_priority) is expected_sampled, (
                    f"trace_id={trace_id}: sampling priority {sampling_priority} disagrees with the ot.rv/ot.th decision"
                )
                break


@scenarios.otel_sampling_rate_0_01
@features.w3c_headers_injection_and_extraction
class Test_EmitOtOnProbabilityDecision_Rate0_01(_EmitOtOnProbabilityDecisionBase):
    RATE = 0.01
    TRACE_IDS = SAMPLING_RATE_0_01


@scenarios.otel_sampling_rate_0_1
@features.w3c_headers_injection_and_extraction
class Test_EmitOtOnProbabilityDecision_Rate0_1(_EmitOtOnProbabilityDecisionBase):
    RATE = 0.1
    TRACE_IDS = SAMPLING_RATE_0_1


@scenarios.otel_sampling_rate_0_2
@features.w3c_headers_injection_and_extraction
class Test_EmitOtOnProbabilityDecision_Rate0_2(_EmitOtOnProbabilityDecisionBase):
    RATE = 0.2
    TRACE_IDS = SAMPLING_RATE_0_2


@scenarios.sampling
@features.w3c_headers_injection_and_extraction
class Test_EmitOtOnProbabilityDecision_Rate0_5(_EmitOtOnProbabilityDecisionBase):
    RATE = 0.5
    TRACE_IDS = SAMPLING_RATE_0_5


@scenarios.otel_sampling_rate_0_99
@features.w3c_headers_injection_and_extraction
class Test_EmitOtOnProbabilityDecision_Rate0_99(_EmitOtOnProbabilityDecisionBase):
    RATE = 0.99
    TRACE_IDS = SAMPLING_RATE_0_99


# Trace ID and rv/th below match the RFC's own verified worked example (rate 0.1, trace ID 0xfff972474538efff).
FORWARD_TRACE_ID = 18444899399302180863
FORWARD_RV = "ef284ace7a91e1"
FORWARD_TH = "e6666666666668"


@scenarios.default
@features.w3c_headers_injection_and_extraction
class Test_ForwardInboundOtUnchanged:
    """A2: DD honors an already-decided upstream trace; ot=rv:...;th:... is forwarded unchanged, never re-derived."""

    def setup_forward_inbound_ot_unchanged(self):
        self.r = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777"},
            headers={
                "traceparent": _traceparent(FORWARD_TRACE_ID, sampled=True),
                "tracestate": f"dd=s:2;t.dm:-3,ot=rv:{FORWARD_RV};th:{FORWARD_TH}",
            },
        )

    def test_forward_inbound_ot_unchanged(self):
        assert self.r.status_code == 200

        ot = _parse_ot(_outbound_tracestate(self.r))
        assert ot.get("rv") == FORWARD_RV, "inbound rv was altered instead of being forwarded unchanged"
        assert ot.get("th") == FORWARD_TH, "inbound th was altered instead of being forwarded unchanged"


@scenarios.default
@features.w3c_headers_injection_and_extraction
class Test_PreserveDdAndOtherVendors:
    """A3: ot= handling must not disturb dd= or an unrelated vendor tracestate member."""

    OTHER_VENDOR_VALUE = "t61rcWkgMzE"

    def setup_preserve_dd_and_other_vendors(self):
        self.r = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777"},
            headers={
                "traceparent": _traceparent(FORWARD_TRACE_ID, sampled=True),
                "tracestate": f"dd=s:2;t.dm:-3,ot=rv:{FORWARD_RV};th:{FORWARD_TH},congo={self.OTHER_VENDOR_VALUE}",
            },
        )

    def test_preserve_dd_and_other_vendors(self):
        assert self.r.status_code == 200
        tracestate = _outbound_tracestate(self.r)

        # an unrelated vendor member is opaque to DD: it must be forwarded byte-for-byte
        assert "congo" in tracestate, "unrelated vendor tracestate member was dropped"
        assert tracestate["congo"] == self.OTHER_VENDOR_VALUE, "unrelated vendor tracestate member was rewritten"

        assert "dd" in tracestate, "dd= tracestate member was dropped"
        assert "s:2" in tracestate["dd"].split(";"), "dd= sampling priority was lost while handling ot="

        ot = _parse_ot(tracestate)
        assert ot.get("rv") == FORWARD_RV
        assert ot.get("th") == FORWARD_TH


@scenarios.default
@features.w3c_headers_injection_and_extraction
class Test_ForceKeepClearsTh:
    """A4: a non-probability (force-keep) decision erases th but still forwards an inherited rv.

    Modeled on the only existing e2e lever for a local, non-probability keep decision: an ASM /waf attack
    detection (tests/appsec/test_traces.py::Test_RetainTraces). There is no dedicated manual-keep/drop
    weblog endpoint today (tracked as a follow-up).
    """

    INHERITED_RV = "1234567890abcd"

    # a full upstream probability decision that dropped the trace (SAMPLING_RATE_0_1's row for trace_id=10, at
    # rate 0.1: sampled=False), so DD's local force-keep has a real inherited decision to override, not just rv.
    DROPPED_TRACE_ID = 10
    DROPPED_RV = "65cd67504a538e"
    DROPPED_TH = TH_BY_RATE[0.1]

    def setup_force_keep_with_no_inbound_ot(self):
        self.no_ot_request = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777"},
            headers={"User-Agent": "Arachni/v1"},
        )

    def test_force_keep_with_no_inbound_ot(self):
        """Nothing was inherited to forward: a local force-keep must not fabricate an ot= from nothing."""
        assert self.no_ot_request.status_code == 200
        tracestate = _outbound_tracestate(self.no_ot_request)
        assert "ot" not in tracestate, "th/rv were fabricated for a non-probability decision with no inherited rv"

        for _, _, span in interfaces.library.get_spans(request=self.no_ot_request):
            assert span.get_sampling_priority() == SamplingPriority.USER_KEEP
            break

    def setup_force_keep_forwards_inherited_rv(self):
        self.rv_only_request = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777"},
            headers={
                "traceparent": _traceparent(FORWARD_TRACE_ID, sampled=False),
                "tracestate": f"ot=rv:{self.INHERITED_RV}",
                "User-Agent": "Arachni/v1",
            },
        )

    def test_force_keep_forwards_inherited_rv(self):
        """An inherited rv (no th, so no upstream probability decision) is still forwarded on a local force-keep."""
        assert self.rv_only_request.status_code == 200
        ot = _parse_ot(_outbound_tracestate(self.rv_only_request))

        assert ot.get("rv") == self.INHERITED_RV, "inherited rv was not forwarded on a force-keep decision"
        assert "th" not in ot, "th should be erased on a non-probability (force-keep) decision"

        for _, _, span in interfaces.library.get_spans(request=self.rv_only_request):
            assert span.get_sampling_priority() == SamplingPriority.USER_KEEP
            break

    def setup_force_keep_overrides_inherited_drop_decision(self):
        self.dropped_request = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777"},
            headers={
                "traceparent": _traceparent(self.DROPPED_TRACE_ID, sampled=False),
                "tracestate": f"ot=rv:{self.DROPPED_RV};th:{self.DROPPED_TH}",
                "User-Agent": "Arachni/v1",
            },
        )

    def test_force_keep_overrides_inherited_drop_decision(self):
        """Upstream already decided to drop (a full th/rv pair); the local force-keep still clears th but forwards the inherited rv unchanged."""
        assert self.dropped_request.status_code == 200
        ot = _parse_ot(_outbound_tracestate(self.dropped_request))

        assert ot.get("rv") == self.DROPPED_RV, "inherited rv was not forwarded when overriding an inherited drop"
        assert "th" not in ot, "th should be erased when a force-keep overrides an inherited drop decision"

        spans = list(interfaces.library.get_spans(request=self.dropped_request))
        assert spans, "no span found for this request: can't verify the sampling priority"
        _, _, span = spans[0]
        assert span.get_sampling_priority() == SamplingPriority.USER_KEEP


@scenarios.default
@features.w3c_headers_injection_and_extraction
class Test_SampledWithoutOtNotFabricated:
    """A5: an inbound trace already sampled (W3C flag) but with no ot= is honored; th/rv are never fabricated."""

    def setup_sampled_without_ot_not_fabricated(self):
        self.r = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777"},
            headers={
                "traceparent": _traceparent(FORWARD_TRACE_ID, sampled=True),
                "tracestate": "dd=s:1",
            },
        )

    def test_sampled_without_ot_not_fabricated(self):
        assert self.r.status_code == 200
        tracestate = _outbound_tracestate(self.r)
        assert "ot" not in tracestate, "th/rv were fabricated for an inherited sampling decision with no inbound ot="


@scenarios.otel_sampling_rate_0_1
@features.w3c_headers_injection_and_extraction
class Test_MalformedOtHandling:
    """A6: a malformed ot.th/ot.rv is treated as absent; dd= and other vendors survive, the trace is never rejected."""

    # matches SAMPLING_RATE_0_1's row for this trace ID: DD's own decision at rate 0.1
    TRACE_ID = FORWARD_TRACE_ID
    EXPECTED_RV = FORWARD_RV
    EXPECTED_TH = FORWARD_TH
    OTHER_VENDOR_VALUE = "xyz123"

    def setup_malformed_rv_and_th_treated_as_absent(self):
        # dd=s:1 (AUTO_KEEP) and the fresh decision DD is expected to derive (EXPECTED_RV/TH's row) both keep
        # this trace, so the traceparent flag must say sampled=True to match: nothing here should conflict.
        self.malformed_both_request = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777"},
            headers={
                "traceparent": _traceparent(self.TRACE_ID, sampled=True),
                "tracestate": f"dd=s:1,ot=rv:not-hex-garbage;th:not-hex-either,congo={self.OTHER_VENDOR_VALUE}",
            },
        )

    def test_malformed_rv_and_th_treated_as_absent(self):
        """Both fields malformed: treated as no inbound decision, so DD makes its own probability decision."""
        req = self.malformed_both_request
        assert req.status_code == 200, "a malformed ot= must not cause the trace to be rejected"

        tracestate = _outbound_tracestate(req)
        assert "congo" in tracestate, "an unrelated vendor member was dropped while handling a malformed ot="
        assert tracestate["congo"] == self.OTHER_VENDOR_VALUE, "an unrelated vendor member was rewritten"
        assert "dd" in tracestate, "dd= tracestate member was dropped while handling a malformed ot="

        ot = _parse_ot(tracestate)
        assert ot.get("rv") == self.EXPECTED_RV, "malformed inbound rv was not replaced by a freshly-derived one"
        assert ot.get("th") == self.EXPECTED_TH, "malformed inbound th was not replaced by a freshly-derived one"

    def setup_malformed_th_only_treated_as_absent(self):
        # same reasoning as above: traceparent must agree with the keep decision EXPECTED_RV/TH encodes.
        self.malformed_th_request = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777"},
            headers={
                "traceparent": _traceparent(self.TRACE_ID, sampled=True),
                "tracestate": "ot=rv:1234567890abcd;th:not-hex-either",
            },
        )

    def test_malformed_th_only_treated_as_absent(self):
        """Th malformed, rv otherwise well-formed: th/rv are always paired, so the malformed-adjacent rv isn't reused."""
        req = self.malformed_th_request
        assert req.status_code == 200, "a malformed ot.th must not cause the trace to be rejected"

        ot = _parse_ot(_outbound_tracestate(req))
        assert ot.get("rv") == self.EXPECTED_RV, "a fresh rv/th pair should be derived, not the malformed-adjacent inbound rv"
        assert ot.get("th") == self.EXPECTED_TH
