# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Compliance tests: a probe with a broken ``when`` condition must not produce probe data."""

import time

import tests.debugger.utils as debugger
from utils import context, features, scenarios


class _ConditionTestBase(debugger.BaseDebuggerTest):
    """Shared base for the condition-error compliance tests."""

    def _convert_to_line_probe_if_needed(self, probe: dict) -> None:
        """In-place: rewrite a LogProbe method probe to a line probe for tracers that need it."""
        if context.library.name != "nodejs":
            return
        where = probe["where"]
        where.pop("methodName", None)
        where["typeName"] = None
        where["sourceFile"] = "ACTUAL_SOURCE_FILE"
        where["lines"] = self.method_and_language_to_line_number("LogProbe", "nodejs")


@features.debugger_expression_language
@scenarios.debugger_probes_snapshot
class Test_Debugger_Invalid_Condition_DSL(_ConditionTestBase):
    """Compliance: a probe whose ``when`` condition cannot be parsed must be rejected with an ERROR diagnostic."""

    def setup_invalid_condition_dsl_probe_rejected(self) -> None:
        self.initialize_weblog_remote_config()

        probes = debugger.read_probes("probe_invalid_condition_dsl")
        for probe in probes:
            probe["id"] = debugger.generate_probe_id("log")
            self._convert_to_line_probe_if_needed(probe)

        self.set_probes(probes)
        self.send_rc_probes()
        # Wait until each probe reaches a terminal state. ERROR is the conforming
        # target (the tracer rejected the broken DSL); INSTALLED catches non-conforming
        # tracers that wrongly install the probe -- returning on INSTALLED keeps those
        # bug paths fast. The 15s timeout fires only for tracers that emit no diagnostic
        # at all; those fail the diagnostic-presence assertion below.
        self.wait_for_all_probes(statuses=["INSTALLED", "ERROR"], timeout=15)
        # Trigger the instrumented method so any lazy-compilation paths have a chance to
        # surface the failure. A conforming tracer must not emit a snapshot here.
        self.send_weblog_request("/debugger/log")
        # Drains any (non-conforming) snapshot the tracer may have emitted so the
        # snapshot assertion below sees it. Returns immediately if none arrives.
        self.wait_for_all_snapshots(timeout=5)

    def test_invalid_condition_dsl_probe_rejected(self) -> None:
        """A probe whose ``when`` condition cannot be parsed must be rejected by the tracer.

        Concretely: the tracer must emit a status=ERROR diagnostic (so the developer who
        configured the broken probe knows it was rejected) and must not produce any probe
        result (snapshot).
        """
        self.collect()
        self.assert_setup_ok()

        # ``self.probe_diagnostics[probe_id]["status"]`` is the framework-aggregated
        # "most-advanced" status; ERROR is only stored if it's reached from RECEIVED.
        # An INSTALLED -> ERROR transition would be hidden (test would see INSTALLED).
        for probe_id in self.probe_ids:
            diag = self.probe_diagnostics.get(probe_id)
            assert diag is not None, (
                "The probe did not receive any diagnostic; the tracer must emit a "
                "status=ERROR diagnostic so the developer knows the probe was rejected."
            )
            status = diag["status"]
            assert status == "ERROR", (
                f"Probe reached status {status!r}; a probe with invalid DSL must reach "
                f"status=ERROR so the developer knows it was rejected."
            )
            snapshots = self.probe_snapshots.get(probe_id, [])
            assert not snapshots, (
                f"Probe emitted {len(snapshots)} snapshot(s); a probe with invalid DSL "
                f"must not produce any probe result."
            )


@features.debugger_expression_language
@scenarios.debugger_probes_snapshot
class Test_Debugger_Runtime_Condition_Error(_ConditionTestBase):
    """Compliance: a probe whose ``when`` raises at eval time must surface the error without leaking probe data."""

    def _setup_runtime_condition_error(self, request_count: int = 1, spacing_s: float = 0.0) -> None:
        self.initialize_weblog_remote_config()

        probes = debugger.read_probes("probe_runtime_condition_error")
        for probe in probes:
            probe["id"] = debugger.generate_probe_id("log")
            self._convert_to_line_probe_if_needed(probe)

        self.set_probes(probes)
        self.send_rc_probes()
        if not self.wait_for_all_probes(statuses=["INSTALLED"], timeout=30):
            self.setup_failures.append("Probes did not reach INSTALLED status within 30s")

        for i in range(request_count):
            self.send_weblog_request("/debugger/log", reset=(i == 0))
            if spacing_s > 0 and i < request_count - 1:
                time.sleep(spacing_s)

        if spacing_s > 0:
            # In the multi-hit case we deliberately do NOT use wait_for_all_snapshots:
            # a non-conforming tracer emits one eval-error snapshot per hit (so two
            # in total here). wait_for_all_snapshots returns the moment the first
            # snapshot is on disk, which would leave the second snapshot still in
            # flight when collect() reads disk -- a false pass. A fixed sleep gives
            # the second snapshot enough time to land.
            time.sleep(5)
        else:
            # Returns as soon as the snapshot arrives, or after the timeout for tracers
            # that emit nothing.
            self.wait_for_all_snapshots(timeout=5)

    def setup_runtime_condition_error_probe_installs(self) -> None:
        self._setup_runtime_condition_error()

    def test_runtime_condition_error_probe_installs(self) -> None:
        """A probe whose ``when`` is structurally valid must install successfully."""
        self.collect()
        self.assert_setup_ok()
        self.assert_rc_state_not_error()

        for probe_id in self.probe_ids:
            assert probe_id in self.probe_diagnostics, "Expected a diagnostic for the probe, but none was received."
            status = self.probe_diagnostics[probe_id]["status"]
            assert status in ("INSTALLED", "EMITTING"), (
                f"Expected the probe to reach INSTALLED/EMITTING status, got {status!r}."
            )

    def setup_runtime_condition_error_emits_error_only_snapshot(self) -> None:
        self._setup_runtime_condition_error()

    def test_runtime_condition_error_emits_error_only_snapshot(self) -> None:
        """When the ``when`` raises at eval time, the tracer must emit a probe result that:

        * carries a non-empty ``evaluationErrors[]`` array (so the developer is informed
          that their condition is broken), AND
        * does NOT include captured probe data (the condition was not successfully
          evaluated, so the probe did not effectively fire from the user-data perspective).
        """
        self.collect()
        self.assert_setup_ok()

        for probe_id in self.probe_ids:
            snapshots = self.probe_snapshots.get(probe_id, [])
            assert snapshots, (
                "The probe emitted no snapshot at all; a probe whose condition errors "
                "at runtime must surface the error to the user via a probe result with "
                "evaluationErrors[]."
            )

            envelope = snapshots[0]
            snap = envelope.get("debugger", {}).get("snapshot") or envelope.get("debugger.snapshot") or {}

            evaluation_errors = snap.get("evaluationErrors") or []
            assert evaluation_errors, (
                "The probe emitted a snapshot without a populated evaluationErrors[] "
                "array; the developer must be told what failed."
            )

            # The condition in probe_runtime_condition_error.json references the unbound
            # variable `definitelyDoesNotExist`. At least one evaluation-error entry should
            # mention that variable name (in `expr` or `message`) so the developer can pin
            # down which part of the condition failed.
            mentions_var = any(
                "definitelyDoesNotExist" in str(entry.get("expr", ""))
                or "definitelyDoesNotExist" in str(entry.get("message", ""))
                for entry in evaluation_errors
            )
            assert mentions_var, (
                f"The probe emitted an eval-error snapshot whose evaluationErrors[] does "
                f"not mention the failing variable name 'definitelyDoesNotExist' "
                f"(entries: {evaluation_errors!r}); the developer must be able to pin "
                f"down which part of the condition failed."
            )

            captures = snap.get("captures")
            assert not debugger.captures_contain_data(captures), (
                f"The probe emitted a snapshot whose ``captures`` field contains captured "
                f"data ({captures!r}); an eval-error snapshot must have empty captures "
                f"because the condition was not successfully evaluated."
            )

    def setup_runtime_condition_error_rate_limited(self) -> None:
        # Fire two hits >1s apart so each hit clears any general 1/s snapshot sampler;
        # anything dropping the second snapshot must be the eval-error rate limiter.
        self._setup_runtime_condition_error(request_count=2, spacing_s=1.5)

    def test_runtime_condition_error_rate_limited(self) -> None:
        """At most 1 eval-error snapshot per probe per 5 minutes."""
        self.collect()
        self.assert_setup_ok()

        for probe_id in self.probe_ids:
            snapshots = self.probe_snapshots.get(probe_id, [])
            assert len(snapshots) <= 1, (
                f"The probe emitted {len(snapshots)} eval-error snapshots for two hits "
                f"spaced >1s apart. A conforming tracer must rate-limit to at most 1 "
                f"eval-error snapshot per probe per 5 minutes."
            )
