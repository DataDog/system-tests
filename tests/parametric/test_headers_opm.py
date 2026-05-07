"""Parametric coverage for the Org Propagation Guard (OPG) RFC.

The Org Propagation Marker (OPM) is a stable, ~10-char base64url marker derived
from `Trunc60(SHA-256(org_uuid))`. The trace intake produces it, the agent
surfaces it under `org_prop_marker` in `/info`, and tracers inject/extract it
via:

- `_dd.p.opm=<OPM>` inside `x-datadog-tags` (Datadog style)
- `t.opm=<OPM>` inside the `dd=` segment of `tracestate` (W3C style)

When `DD_TRACE_ORG_GUARD_ENABLED=true`, a tracer that knows its local OPM and
sees a different inbound OPM strips the dd part of the inbound trace context
(sampling, origin, propagated tags) while keeping `trace_id`, `parent_id`, and
baggage intact for cyclic-call resilience.

The local OPM is provided to the tracer via the agent /info endpoint. The
parametric harness pins `ddapm-test-agent` >= v1.54.1, which reads the
`ORG_PROP_MARKER` env var and surfaces its value as `org_prop_marker` in /info.

RFC: https://docs.google.com/document/d/1SzZWivVWT79lJe80ZulEra6AARszjEYVEwWJ7IhJ6Xo/edit?tab=t.0
"""

import pytest

from utils import features, scenarios, rfc
from utils.docker_fixtures import TestAgentAPI

from .conftest import APMLibrary


parametrize = pytest.mark.parametrize


LOCAL_OPM = "AaBbCcDdEeFf"
FOREIGN_OPM = "Zz1122334455"
TRUSTED_OPM = "Tt9988776655"

INBOUND_TRACE_ID = 123456789
INBOUND_PARENT_ID = 987654321
INBOUND_TID = "1111111111111111"  # _dd.p.tid value (128-bit trace ID high bits)


def _local_opm_agent_env() -> pytest.MarkDecorator:
    # ddapm-test-agent v1.54.1+ reads ORG_PROP_MARKER and surfaces it
    # as `org_prop_marker` in /info.
    return parametrize("agent_env", [{"ORG_PROP_MARKER": LOCAL_OPM}])


def _enable_guard(extra: dict[str, str] | None = None) -> pytest.MarkDecorator:
    env: dict[str, str] = {"DD_TRACE_ORG_GUARD_ENABLED": "true"}
    if extra:
        env.update(extra)
    return parametrize("library_env", [env])


def _both_styles() -> pytest.MarkDecorator:
    return parametrize(
        "library_env",
        [
            {
                "DD_TRACE_PROPAGATION_STYLE_INJECT": "datadog,tracecontext",
                "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "datadog,tracecontext",
            }
        ],
    )


def _inbound(*extra: tuple[str, str]) -> list[tuple[str, str]]:
    """Datadog-style inbound headers with the standard trace/parent ids and an
    explicit USER_KEEP sampling priority. Pass extras to add `_dd.p.opm`,
    `_dd.p.dm`, origin, baggage, etc.
    """
    return [
        ("x-datadog-trace-id", str(INBOUND_TRACE_ID)),
        ("x-datadog-parent-id", str(INBOUND_PARENT_ID)),
        ("x-datadog-sampling-priority", "2"),
        *extra,
    ]


def _x_dd_tags(headers: dict[str, str]) -> str:
    return headers.get("x-datadog-tags", "")


def _tracestate(headers: dict[str, str]) -> str:
    return headers.get("tracestate", "")


def _dd_segment(tracestate: str) -> str | None:
    """Return the `dd=...` member of a tracestate, or None if absent."""
    for raw_member in tracestate.split(","):
        member = raw_member.strip()
        if member.startswith("dd="):
            return member[len("dd=") :]
    return None


@rfc("https://docs.google.com/document/d/1SzZWivVWT79lJe80ZulEra6AARszjEYVEwWJ7IhJ6Xo/edit?tab=t.0")
@features.org_propagation_guard
@scenarios.parametric
class Test_HeadersOPM_Injection:
    """OPM injection behavior depending on whether the tracer knows a local OPM."""

    def test_no_local_opm_no_inbound_opm_does_not_inject(self, test_library: APMLibrary) -> None:
        """No local OPM, no inbound OPM -> outbound headers carry no _dd.p.opm / t.opm."""
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(_inbound())

        assert "_dd.p.opm=" not in _x_dd_tags(headers)
        assert "t.opm:" not in _tracestate(headers)

    def test_no_local_opm_propagates_inbound_opm(self, test_library: APMLibrary) -> None:
        """No local OPM but inbound OPM present -> propagate inbound OPM as-is (passthrough rule)."""
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                _inbound(("x-datadog-tags", f"_dd.p.opm={FOREIGN_OPM}"))
            )

        assert f"_dd.p.opm={FOREIGN_OPM}" in _x_dd_tags(headers)

    @_local_opm_agent_env()
    def test_local_opm_overrides_inbound_opm(self, test_library: APMLibrary) -> None:
        """Local OPM known -> inject local OPM regardless of any inbound OPM."""
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                _inbound(("x-datadog-tags", f"_dd.p.opm={FOREIGN_OPM}"))
            )

        x_dd_tags = _x_dd_tags(headers)
        assert f"_dd.p.opm={LOCAL_OPM}" in x_dd_tags
        assert f"_dd.p.opm={FOREIGN_OPM}" not in x_dd_tags

    @_local_opm_agent_env()
    @_both_styles()
    def test_opm_injected_in_both_styles(self, test_library: APMLibrary) -> None:
        """When both datadog & tracecontext styles inject, OPM appears in both header families."""
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(_inbound())

        assert f"_dd.p.opm={LOCAL_OPM}" in _x_dd_tags(headers)
        dd_member = _dd_segment(_tracestate(headers))
        assert dd_member is not None
        assert f"t.opm:{LOCAL_OPM}" in dd_member


@rfc("https://docs.google.com/document/d/1SzZWivVWT79lJe80ZulEra6AARszjEYVEwWJ7IhJ6Xo/edit?tab=t.0")
@features.org_propagation_guard
@scenarios.parametric
class Test_HeadersOPM_ExtractDefault:
    """Guard disabled (default): an inbound `_dd.p.opm` tag must not break extraction."""

    def test_mismatch_does_not_enforce(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with (
            test_library,
            test_library.dd_extract_headers_and_make_child_span(
                "guard_disabled_mismatch",
                _inbound(
                    ("x-datadog-origin", "rum"),
                    ("x-datadog-tags", f"_dd.p.dm=-4,_dd.p.opm={FOREIGN_OPM}"),
                ),
            ),
        ):
            pass

        traces = test_agent.wait_for_num_traces(1)
        assert len(traces) == 1
        span = traces[0][0]
        assert span.get("trace_id") == INBOUND_TRACE_ID
        assert span.get("parent_id") == INBOUND_PARENT_ID
        assert span["meta"].get("_dd.p.dm") == "-4"
        assert span["meta"].get("_dd.origin") == "rum"


@rfc("https://docs.google.com/document/d/1SzZWivVWT79lJe80ZulEra6AARszjEYVEwWJ7IhJ6Xo/edit?tab=t.0")
@features.org_propagation_guard
@scenarios.parametric
class Test_HeadersOPM_ExtractEnabled:
    """Guard enabled: matching OPM continues, mismatching OPM enforces."""

    @_local_opm_agent_env()
    @_enable_guard()
    def test_match_continues_trace(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Inbound OPM == local OPM -> sampling / origin / propagated tags preserved."""
        with (
            test_library,
            test_library.dd_extract_headers_and_make_child_span(
                "guard_match",
                _inbound(
                    ("x-datadog-origin", "rum"),
                    ("x-datadog-tags", f"_dd.p.tid={INBOUND_TID},_dd.p.dm=-4,_dd.p.opm={LOCAL_OPM}"),
                ),
            ),
        ):
            pass

        span = test_agent.wait_for_num_traces(1)[0][0]
        assert span.get("trace_id") == INBOUND_TRACE_ID
        assert span.get("parent_id") == INBOUND_PARENT_ID
        # Propagated tags survive on match: dm, tid, origin.
        assert span["meta"].get("_dd.p.dm") == "-4"
        assert span["meta"].get("_dd.p.tid") == INBOUND_TID
        assert span["meta"].get("_dd.origin") == "rum"

    @_local_opm_agent_env()
    @_enable_guard()
    def test_match_continues_trace_w3c(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Same match-path semantics when OPM arrives only via the W3C carrier."""
        with (
            test_library,
            test_library.dd_extract_headers_and_make_child_span(
                "guard_match_w3c",
                [
                    ("traceparent", "00-11111111111111110000000000000001-0000000000000001-01"),
                    ("tracestate", f"dd=s:2;t.dm:-4;t.opm:{LOCAL_OPM},foo=1"),
                ],
            ),
        ):
            pass

        span = test_agent.wait_for_num_traces(1)[0][0]
        # Inbound dm survives (would be stripped on mismatch).
        assert span["meta"].get("_dd.p.dm") == "-4"

    @_local_opm_agent_env()
    @_enable_guard()
    def test_mismatch_strips_dd_state(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Inbound OPM != local OPM -> drop sampling, origin, propagated _dd.p.* tags."""
        with (
            test_library,
            test_library.dd_extract_headers_and_make_child_span(
                "guard_mismatch",
                _inbound(
                    ("x-datadog-origin", "rum"),
                    ("x-datadog-tags", f"_dd.p.tid={INBOUND_TID},_dd.p.dm=-4,_dd.p.opm={FOREIGN_OPM}"),
                ),
            ),
        ):
            pass

        span = test_agent.wait_for_num_traces(1)[0][0]
        # Parent linkage is preserved (cyclic-call guarantee from RFC).
        assert span.get("trace_id") == INBOUND_TRACE_ID
        assert span.get("parent_id") == INBOUND_PARENT_ID
        # dd-controlled *decisions* are dropped:
        # `_dd.p.dm` is propagation-only on the wire but the local sampler
        # restamps it on the new child span, so we only assert the inbound
        # value didn't survive (rather than is None).
        assert span["meta"].get("_dd.p.dm") != "-4"
        assert span["meta"].get("_dd.origin") is None
        # Trace identity is preserved (cyclic-call guarantee). `_dd.p.tid`
        # carries the high 64 bits of the 128-bit trace_id, so dropping it
        # would corrupt trace_id — it must survive enforcement.
        assert span["meta"].get("_dd.p.tid") == INBOUND_TID

    @_local_opm_agent_env()
    @_enable_guard()
    def test_mismatch_strips_dd_tracestate_member(self, test_library: APMLibrary) -> None:
        """On mismatch, outbound tracestate must not carry the inbound dd state, but foreign vendors survive."""
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", "00-11111111111111110000000000000001-0000000000000001-01"),
                    ("tracestate", f"dd=s:2;t.dm:-4;t.opm:{FOREIGN_OPM},foo=1"),
                ]
            )

        ts = _tracestate(headers)
        # The outbound tracestate may contain a *new* dd= segment created locally,
        # but it must not carry the inbound foreign OPM, dm, or sampling decision.
        assert f"t.opm:{FOREIGN_OPM}" not in ts
        assert "t.dm:-4" not in ts
        assert "foo=1" in ts

    @_local_opm_agent_env()
    @_enable_guard({"DD_TRACE_PROPAGATION_STYLE": "datadog,tracecontext,baggage"})
    def test_mismatch_preserves_baggage(self, test_library: APMLibrary) -> None:
        """Baggage is general and must survive enforcement untouched.

        `baggage` is included explicitly in DD_TRACE_PROPAGATION_STYLE so the
        propagator actually injects it; otherwise the assertion would conflate
        "guard dropped baggage" with "baggage was never an active propagator".
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                _inbound(
                    ("x-datadog-tags", f"_dd.p.opm={FOREIGN_OPM}"),
                    ("baggage", "key1=value1"),
                )
            )

        assert "key1=value1" in headers.get("baggage", "")

    @_local_opm_agent_env()
    @_enable_guard()
    def test_missing_inbound_opm_does_not_enforce(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Non-strict default: missing inbound OPM does not trigger enforcement.

        Two sides of the same real-world scenario (a request from outside the org):
        - Extraction: the inbound trace continues, propagated tags survive.
        - Injection: the outbound carries the local OPM so the next hop sees it.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(_inbound(("x-datadog-tags", "_dd.p.dm=-4")))

        # Extraction side: trace continued, propagated tags preserved
        span = test_agent.wait_for_num_traces(1)[0][0]
        assert span.get("trace_id") == INBOUND_TRACE_ID
        assert span["meta"].get("_dd.p.dm") == "-4"

        # Injection side: outbound carries the local OPM
        assert f"_dd.p.opm={LOCAL_OPM}" in _x_dd_tags(headers)


@rfc("https://docs.google.com/document/d/1SzZWivVWT79lJe80ZulEra6AARszjEYVEwWJ7IhJ6Xo/edit?tab=t.0")
@features.org_propagation_guard
@scenarios.parametric
class Test_HeadersOPM_TrustedOpms:
    """`DD_TRACE_ORG_GUARD_TRUSTED_OPMS` allowlist bypasses enforcement."""

    @_local_opm_agent_env()
    @_enable_guard({"DD_TRACE_ORG_GUARD_TRUSTED_OPMS": f"{TRUSTED_OPM},{FOREIGN_OPM}"})
    def test_trusted_inbound_opm_passes_through(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with (
            test_library,
            test_library.dd_extract_headers_and_make_child_span(
                "guard_trusted",
                _inbound(("x-datadog-tags", f"_dd.p.dm=-4,_dd.p.opm={TRUSTED_OPM}")),
            ),
        ):
            pass

        span = test_agent.wait_for_num_traces(1)[0][0]
        assert span["meta"].get("_dd.p.dm") == "-4"

    @_local_opm_agent_env()
    @_enable_guard({"DD_TRACE_ORG_GUARD_TRUSTED_OPMS": TRUSTED_OPM})
    def test_untrusted_inbound_opm_is_enforced(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with (
            test_library,
            test_library.dd_extract_headers_and_make_child_span(
                "guard_untrusted",
                _inbound(("x-datadog-tags", f"_dd.p.dm=-4,_dd.p.opm={FOREIGN_OPM}")),
            ),
        ):
            pass

        span = test_agent.wait_for_num_traces(1)[0][0]
        assert span.get("parent_id") == INBOUND_PARENT_ID
        assert span["meta"].get("_dd.p.dm") != "-4"


@rfc("https://docs.google.com/document/d/1SzZWivVWT79lJe80ZulEra6AARszjEYVEwWJ7IhJ6Xo/edit?tab=t.0")
@features.org_propagation_guard
@scenarios.parametric
class Test_HeadersOPM_Strict:
    """Strict mode enforces even when the inbound OPM is missing."""

    @_local_opm_agent_env()
    @_enable_guard({"DD_TRACE_ORG_GUARD_STRICT": "true"})
    def test_strict_missing_inbound_enforces(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with (
            test_library,
            test_library.dd_extract_headers_and_make_child_span(
                "guard_strict_missing",
                _inbound(
                    ("x-datadog-origin", "rum"),
                    ("x-datadog-tags", "_dd.p.dm=-4"),
                ),
            ),
        ):
            pass

        span = test_agent.wait_for_num_traces(1)[0][0]
        assert span.get("parent_id") == INBOUND_PARENT_ID
        assert span["meta"].get("_dd.p.dm") != "-4"
        assert span["meta"].get("_dd.origin") is None

    @_local_opm_agent_env()
    @_enable_guard({"DD_TRACE_ORG_GUARD_STRICT": "true"})
    def test_strict_match_continues(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with (
            test_library,
            test_library.dd_extract_headers_and_make_child_span(
                "guard_strict_match",
                _inbound(("x-datadog-tags", f"_dd.p.dm=-4,_dd.p.opm={LOCAL_OPM}")),
            ),
        ):
            pass

        span = test_agent.wait_for_num_traces(1)[0][0]
        assert span["meta"].get("_dd.p.dm") == "-4"


@rfc("https://docs.google.com/document/d/1SzZWivVWT79lJe80ZulEra6AARszjEYVEwWJ7IhJ6Xo/edit?tab=t.0")
@features.org_propagation_guard
@scenarios.parametric
class Test_HeadersOPM_AgentInfo:
    """Agent /info exposes `org_prop_marker`, and the tracer consumes it."""

    @_local_opm_agent_env()
    def test_info_endpoint_exposes_opm(self, test_agent: TestAgentAPI) -> None:
        info = test_agent.info()
        assert info.get("org_prop_marker") == LOCAL_OPM

    @_local_opm_agent_env()
    def test_tracer_consumes_info_opm(self, test_library: APMLibrary) -> None:
        """Once the tracer has fetched /info, outbound headers carry the local OPM."""
        with test_library:
            # Warm up: a first span so the tracer has time to poll /info before injecting.
            with test_library.dd_start_span(name="warmup"):
                pass
            headers = test_library.dd_make_child_span_and_get_headers(_inbound())

        assert f"_dd.p.opm={LOCAL_OPM}" in _x_dd_tags(headers)
