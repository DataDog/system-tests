# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Cross-tracer conformance for OpenTelemetry consistent probability sampling (ot.th / ot.rv) on the wire.

See APMAPI-2171. Landed disabled for every tracer (manifests/*.yml); each tracer enables these as it ships.
"""

import json

from tests.otel.utils import (
    FORWARD_RV,
    FORWARD_TH,
    FORWARD_TRACE_ID,
    SAMPLING_RATE_0_5,
    TH_BY_RATE,
)
from utils import HttpResponse, features, interfaces, scenarios, weblog
from utils.dd_constants import SamplingPriority
from utils.docker_fixtures.spec.tracecontext import Tracestate, get_tracestate


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
            assert "ot" in tracestate, (
                f"trace_id={trace_id}: no ot= tracestate member emitted on a probability decision"
            )
            ot = _parse_ot(tracestate)

            assert ot.get("rv") == expected_rv, f"trace_id={trace_id}: rv={ot.get('rv')!r}, expected {expected_rv!r}"
            assert ot.get("th") == expected_th, f"trace_id={trace_id}: th={ot.get('th')!r}, expected {expected_th!r}"

            for _, _, span in interfaces.library.get_spans(request=req):
                sampling_priority = span.get_sampling_priority()
                assert sampling_priority is not None, f"trace_id={trace_id}: no sampling priority on span"
                assert _priority_should_be_kept(sampling_priority) is expected_sampled, (
                    f"trace_id={trace_id}: sampling priority {sampling_priority} disagrees with the ot.rv/ot.th decision"
                )
                break


@scenarios.sampling
@features.w3c_headers_injection_and_extraction
class Test_EmitOtOnProbabilityDecision_Rate0_5(_EmitOtOnProbabilityDecisionBase):
    RATE = 0.5
    TRACE_IDS = SAMPLING_RATE_0_5


# Trace ID and rv/th below match the RFC's own verified worked example (rate 0.1, trace ID 0xfff972474538efff).
@scenarios.sampling
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

    def setup_forward_inbound_ot_unknown_subkey(self):
        # OTEP 235 defines only rv/th today but reserves room for more ot= sub-keys. An unknown sub-key
        # inherited from upstream must be forwarded verbatim, never dropped from an inherited decision.
        self.unknown_subkey_request = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777"},
            headers={
                "traceparent": _traceparent(FORWARD_TRACE_ID, sampled=True),
                "tracestate": f"dd=s:2;t.dm:-3,ot=rv:{FORWARD_RV};th:{FORWARD_TH};foo:bar",
            },
        )
        # Unknown-only variant: an ot= with no rv/th carries no sampling decision, so its sub-key must
        # still be forwarded verbatim and DD must not mistake it for a decision by fabricating rv/th.
        self.unknown_only_request = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777"},
            headers={
                "traceparent": _traceparent(FORWARD_TRACE_ID, sampled=True),
                "tracestate": "dd=s:2;t.dm:-3,ot=foo:bar",
            },
        )

    def test_forward_inbound_ot_unknown_subkey(self):
        assert self.unknown_subkey_request.status_code == 200

        ot = _parse_ot(_outbound_tracestate(self.unknown_subkey_request))
        assert ot.get("rv") == FORWARD_RV, "inbound rv was altered instead of being forwarded unchanged"
        assert ot.get("th") == FORWARD_TH, "inbound th was altered instead of being forwarded unchanged"
        assert ot.get("foo") == "bar", (
            "an unknown inbound ot= sub-key was dropped instead of forwarded verbatim "
            "(OTEP 235 reserves room for future sub-keys; tracers must be transparent to them)"
        )

        assert self.unknown_only_request.status_code == 200
        ot_only = _parse_ot(_outbound_tracestate(self.unknown_only_request))
        assert ot_only.get("foo") == "bar", (
            "an unknown-only inbound ot= sub-key was dropped instead of forwarded verbatim"
        )
        assert "rv" not in ot_only, "rv was fabricated for an ot= that carried no sampling decision"
        assert "th" not in ot_only, "th was fabricated for an ot= that carried no sampling decision"


@scenarios.sampling
@features.w3c_headers_injection_and_extraction
class Test_ThOnlyDoesNotFabricateRv:
    """A2b: th alone is a valid OTel default-sampling decision (rv is only carried when the decision deviates
    from that default); DD must forward th unchanged and never fabricate a matching rv.
    """

    def setup_th_only_does_not_fabricate_rv(self):
        self.r = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777"},
            headers={
                "traceparent": _traceparent(FORWARD_TRACE_ID, sampled=True),
                "tracestate": f"ot=th:{FORWARD_TH}",
            },
        )

    def test_th_only_does_not_fabricate_rv(self):
        assert self.r.status_code == 200

        ot = _parse_ot(_outbound_tracestate(self.r))
        assert ot.get("th") == FORWARD_TH, "inbound th was altered instead of being forwarded unchanged"
        assert "rv" not in ot, "an rv was fabricated for a th-only (OTel default-sampling) decision"


@scenarios.sampling
@features.w3c_headers_injection_and_extraction
class Test_ForwardInboundOtUnchangedWhenDropped:
    """A2c: A2's forward-unchanged rule holds for a dropped decision too, not just a kept one."""

    def setup_forward_inbound_ot_unchanged_when_dropped(self):
        self.r = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777"},
            headers={
                "traceparent": _traceparent(FORWARD_TRACE_ID, sampled=False),
                "tracestate": f"dd=s:0,ot=rv:{FORWARD_RV};th:{FORWARD_TH}",
            },
        )

    def test_forward_inbound_ot_unchanged_when_dropped(self):
        assert self.r.status_code == 200

        ot = _parse_ot(_outbound_tracestate(self.r))
        assert ot.get("rv") == FORWARD_RV, "inbound rv was altered instead of being forwarded unchanged"
        assert ot.get("th") == FORWARD_TH, "inbound th was altered instead of being forwarded unchanged"


@scenarios.sampling
@features.w3c_headers_injection_and_extraction
class Test_ThOnlyDoesNotFabricateRvWhenDropped:
    """A2d: A2b's no-fabrication rule holds for a dropped decision too, not just a kept one."""

    def setup_th_only_does_not_fabricate_rv_when_dropped(self):
        self.r = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777"},
            headers={
                "traceparent": _traceparent(FORWARD_TRACE_ID, sampled=False),
                "tracestate": f"ot=th:{FORWARD_TH}",
            },
        )

    def test_th_only_does_not_fabricate_rv_when_dropped(self):
        assert self.r.status_code == 200

        ot = _parse_ot(_outbound_tracestate(self.r))
        assert ot.get("th") == FORWARD_TH, "inbound th was altered instead of being forwarded unchanged"
        assert "rv" not in ot, "an rv was fabricated for a th-only (OTel default-sampling) decision"


@scenarios.sampling
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


@scenarios.sampling
@features.w3c_headers_injection_and_extraction
class Test_PreserveTracestateMemberOrder:
    def setup_preserve_tracestate_member_order(self):
        self.r = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777"},
            headers={
                "traceparent": _traceparent(FORWARD_TRACE_ID, sampled=True),
                "tracestate": "dd=s:1,foo=bar,ot=rv:6e6d1a75832a2f,something=else",
            },
        )

    def test_preserve_tracestate_member_order(self):
        assert self.r.status_code == 200

        request_headers = json.loads(self.r.text)["request_headers"]
        raw_tracestate = next(
            (value for key, value in request_headers.items() if key.lower() == "tracestate"),
            None,
        )
        assert raw_tracestate is not None, "tracestate header was dropped"

        dd_member, separator, unmodified_members = raw_tracestate.partition(",")
        assert separator, "tracestate did not preserve the unmodified members"
        assert dd_member.startswith("dd="), "dd= must remain the leading tracestate member"
        assert unmodified_members == "foo=bar,ot=rv:6e6d1a75832a2f,something=else"


@scenarios.sampling
@features.w3c_headers_injection_and_extraction
class Test_ForceKeepClearsTh:
    """A4: a non-probability (force-keep) decision erases th but still forwards an inherited rv.

    The manual-keep endpoint applies the decision before making its downstream request, whose propagated
    headers are returned in the response.
    """

    INHERITED_RV = "1234567890abcd"

    # a full upstream probability decision that dropped the trace (SAMPLING_RATE_0_1's row for trace_id=10, at
    # rate 0.1: sampled=False), so DD's local force-keep has a real inherited decision to override, not just rv.
    DROPPED_TRACE_ID = 10
    DROPPED_RV = "65cd67504a538e"
    DROPPED_TH = TH_BY_RATE[0.1]

    def setup_force_keep_with_no_inbound_ot(self):
        self.no_ot_request = weblog.get(
            "/trace/manual_keep_drop",
            params={"decision": "keep"},
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
            "/trace/manual_keep_drop",
            params={"decision": "keep"},
            headers={
                "traceparent": _traceparent(FORWARD_TRACE_ID, sampled=False),
                "tracestate": f"ot=rv:{self.INHERITED_RV}",
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
            "/trace/manual_keep_drop",
            params={"decision": "keep"},
            headers={
                "traceparent": _traceparent(self.DROPPED_TRACE_ID, sampled=False),
                "tracestate": f"ot=rv:{self.DROPPED_RV};th:{self.DROPPED_TH}",
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


@scenarios.sampling
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


@scenarios.sampling
@features.w3c_headers_injection_and_extraction
class Test_MalformedOtHandling:
    """A6: a malformed ot.th/ot.rv field is cleared, never re-derived; the actual sampling decision is already

    settled by traceparent/dd=, so DD must not fabricate a fresh probability decision to replace it.
    dd= and other vendors survive, and the trace is never rejected.
    """

    TRACE_ID = FORWARD_TRACE_ID
    MALFORMED_TH_RV = "1234567890abcd"
    OTHER_VENDOR_VALUE = "xyz123"

    def setup_malformed_rv_and_th_treated_as_absent(self):
        # dd=s:1 (AUTO_KEEP) is the actual decision here, so the traceparent flag must agree (sampled=True).
        self.malformed_both_request = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777"},
            headers={
                "traceparent": _traceparent(self.TRACE_ID, sampled=True),
                "tracestate": f"dd=s:1,ot=rv:not-hex-garbage;th:not-hex-either,congo={self.OTHER_VENDOR_VALUE}",
            },
        )

    def test_malformed_rv_and_th_treated_as_absent(self):
        """Both fields malformed: cleared, not replaced by a freshly-derived pair."""
        req = self.malformed_both_request
        assert req.status_code == 200, "a malformed ot= must not cause the trace to be rejected"

        tracestate = _outbound_tracestate(req)
        assert "congo" in tracestate, "an unrelated vendor member was dropped while handling a malformed ot="
        assert tracestate["congo"] == self.OTHER_VENDOR_VALUE, "an unrelated vendor member was rewritten"
        assert "dd" in tracestate, "dd= tracestate member was dropped while handling a malformed ot="
        assert "ot" not in tracestate, "a malformed ot= must be cleared, not replaced by a freshly-derived one"

    def setup_malformed_th_only_treated_as_absent(self):
        self.malformed_th_request = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777"},
            headers={
                "traceparent": _traceparent(self.TRACE_ID, sampled=True),
                "tracestate": f"ot=rv:{self.MALFORMED_TH_RV};th:not-hex-either",
            },
        )

    def test_malformed_th_only_treated_as_absent(self):
        """Th malformed, rv otherwise well-formed: th is cleared, but the well-formed rv is still forwarded."""
        req = self.malformed_th_request
        assert req.status_code == 200, "a malformed ot.th must not cause the trace to be rejected"

        ot = _parse_ot(_outbound_tracestate(req))
        assert ot.get("rv") == self.MALFORMED_TH_RV, "the well-formed inbound rv was not forwarded"
        assert "th" not in ot, "a malformed ot.th must be cleared, not replaced by a freshly-derived one"
