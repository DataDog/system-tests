# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import tests.debugger.utils as debugger

from utils import scenarios, features, slow

# Snapshot rate for the correlation probes, set through the tracer's existing per-probe sampling
# config (sampling.snapshotsPerSecond). It is the only sampling lever the DI probe config exposes:
# a per-probe rate limit in snapshots per second, not a probabilistic per-trace rate. Kept below
# 100% so some traces are sampled out.
_SNAPSHOTS_PER_SECOND = 1

# Envelope field carrying the tracer per-process runtime id. The snapshot envelope does not carry
# it today; the lookup tolerates the envelope root or the "dd" object.
_RUNTIME_ID_FIELD = "runtime_id"

# Snapshot field carrying the execution-context generation token alongside thread_id.
_GENERATION_TOKEN_FIELD = "generation"


def _trace_id(snapshot: dict) -> str | None:
    return snapshot.get("dd", {}).get("trace_id")


def _runtime_id(snapshot: dict) -> str | None:
    return snapshot.get(_RUNTIME_ID_FIELD) or snapshot.get("dd", {}).get(_RUNTIME_ID_FIELD)


@features.debugger_snapshot_correlation
@scenarios.debugger_probes_snapshot
@slow
class Test_Debugger_Coordinated_Sampling(debugger.BaseDebuggerTest):
    """Tier 1: the sampling decision is made once per trace and applies to every probe that
    fires in that trace. This needs no change to the snapshot payload: correlation rides on the
    dd.trace_id already present in the snapshot envelope, so the test just groups snapshots by
    that trace_id.

    The call-chain endpoint spaces its probed call sites in time (real work between them), so the
    probes in one trace are hit seconds apart rather than in lockstep. Under independent per-probe
    sampling (the time-based per-probe rate limiter tracers have today) those spaced hits fall in
    different rate windows, so a trace emits some probes and drops others: a partial chain. A
    single per-trace decision instead keeps every probe in a trace together. So the discriminator
    is: with spaced hits, only coordinated sampling yields zero partial chains.

    Assertions: zero partial chains, at least one fully emitted trace, at least one fully dropped
    trace. There is no numeric emitted-fraction band because the only sampling lever the DI probe
    config exposes is the time-based sampling.snapshotsPerSecond rate limit; a probabilistic
    per-trace rate is not expressible, so a specific emitted fraction cannot be asserted.

    No current tracer makes a per-trace decision, so this is expected to xfail (gated
    missing_feature for every language) until coordinated sampling ships. The spacing is what
    keeps the xfail honest: without it, independent per-probe sampling could pass by lockstep
    coincidence.

    Out of scope for this gate (not cleanly observable end to end through the weblog and
    remote-config harness): Tier 2 task-context correlation when no distributed trace exists.
    """

    _INVOCATIONS = 30

    def setup_coordinated_per_trace_sampling(self):
        self.initialize_weblog_remote_config()

        probes = debugger.read_probes("probe_snapshot_log_correlation")
        for probe in probes:
            probe["id"] = debugger.generate_probe_id("log")
            # Use the tracer's existing per-probe sampling config to sample below 100%.
            probe["sampling"] = {"snapshotsPerSecond": _SNAPSHOTS_PER_SECOND}
        self.set_probes(probes)

        self.send_rc_apm_tracing_and_probes(dynamic_instrumentation_enabled=True, dynamic_sampling_enabled=True)
        if not self.wait_for_all_probes(statuses=["INSTALLED"], timeout=60):
            self.setup_failures.append("Probes did not reach INSTALLED status")
            return

        # Each request is one trace, so it is one sampling unit; the endpoint spaces the probe
        # hits within the trace.
        for i in range(self._INVOCATIONS):
            self.send_weblog_request("/debugger/correlation", reset=(i == 0))

        self.wait_for_all_probes(statuses=["EMITTING"])
        self.wait_for_all_snapshots()

    def test_coordinated_per_trace_sampling(self):
        self.collect()

        self.assert_setup_ok()
        self.assert_rc_state_not_error()
        self.assert_all_weblog_responses_ok()

        chain = set(self.probe_ids)

        # Group the probes seen per trace using the existing dd.trace_id. A coordinated decision
        # means every trace that emitted anything emitted the whole chain.
        probes_by_trace: dict[str, set[str]] = {}
        for probe_id in self.probe_ids:
            for snapshot in self.probe_snapshots.get(probe_id, []):
                trace_id = _trace_id(snapshot)
                assert trace_id, f"snapshot for probe {probe_id} is missing dd.trace_id on the wire"
                probes_by_trace.setdefault(trace_id, set()).add(probe_id)

        full = [trace_id for trace_id, probes in probes_by_trace.items() if probes == chain]
        partial = [trace_id for trace_id, probes in probes_by_trace.items() if probes != chain]
        # Fully dropped traces emit nothing and so never appear above. Every request is a distinct
        # trace, so the emitted-trace count is the number of traces that produced any snapshot.
        emitted = len(probes_by_trace)
        dropped = self._INVOCATIONS - emitted

        assert not partial, (
            f"partial probe chains were emitted, the sampling decision is not made once per trace: {partial}"
        )
        assert full, "no trace emitted the full probe chain"
        assert dropped >= 1, "no trace was fully dropped; nothing was sampled out"


@features.debugger_probe_budgets
@scenarios.debugger_probes_snapshot
@slow
class Test_Debugger_Per_Span_Budget(debugger.BaseDebuggerTest):
    """Each probe emits at most one snapshot per span execution. A probe inside a
    high-iteration loop emits exactly one snapshot for the span and does not starve a
    sibling probe on the same span, which still emits its one snapshot.

    This is stricter than the time-based budget in test_debugger_probe_budgets.py (which
    tolerates 1 to 20 snapshots); the loop below runs long enough that a time-based budget
    would emit more than one, so exactly one proves the cap is span scoped.
    """

    # The loop sleeps one second per iteration so the span lasts a few seconds: long enough
    # that a time-based (per-second) budget would emit more than one snapshot, while a
    # span-scoped budget emits exactly one. Kept below the weblog request timeout.
    _LOOPS = 3

    def setup_per_span_budget(self):
        self.initialize_weblog_remote_config()

        language = self.get_tracer()["language"]
        loop_lines = self.method_and_language_to_line_number("CorrelationLoopBody", language)
        sibling_lines = self.method_and_language_to_line_number("CorrelationLoopSibling", language)

        template = debugger.read_probes("probe_snapshot_log_correlation_loop")[0]
        probes = []
        for lines in (loop_lines, sibling_lines):
            probe = {**template, "where": {**template["where"], "lines": [str(n) for n in lines]}}
            probe["id"] = debugger.generate_probe_id("log")
            probes.append(probe)
        self.set_probes(probes)

        self.send_rc_probes()
        if not self.wait_for_all_probes(statuses=["INSTALLED"], timeout=60):
            self.setup_failures.append("Probes did not reach INSTALLED status")
            return

        self.send_weblog_request(f"/debugger/correlation/loop/{self._LOOPS}")
        self.wait_for_all_probes(statuses=["EMITTING"])
        self.wait_for_all_snapshots()

    def test_per_span_budget(self):
        self.collect()

        self.assert_setup_ok()
        self.assert_rc_state_not_error()
        self.assert_all_weblog_responses_ok()

        # A single request is a single span, so every probe must have emitted exactly once.
        for probe_id in self.probe_ids:
            snapshots = [s for s in self.probe_snapshots.get(probe_id, []) if s.get("debugger", {}).get("snapshot")]
            assert len(snapshots) == 1, (
                f"probe {probe_id} emitted {len(snapshots)} snapshots for one span, expected exactly 1"
            )


# Follow-on work, split out of feature 564 (which is coordinated sampling via trace_id only).
# There is no dashboard feature for this yet, and it is simply not implemented (not blocked on
# any schema negotiation), so it is not reported.
@features.not_reported
@scenarios.debugger_probes_snapshot
@slow
class Test_Debugger_Runtime_Id_In_Envelope(debugger.BaseDebuggerTest):
    """Every snapshot envelope carries the tracer per-process runtime_id: present, non-empty, and
    identical across all snapshots emitted by the same process.
    """

    def setup_runtime_id_in_envelope(self):
        self.initialize_weblog_remote_config()

        probes = debugger.read_probes("probe_snapshot_log_correlation")
        for probe in probes:
            probe["id"] = debugger.generate_probe_id("log")
        self.set_probes(probes)

        self.send_rc_probes()
        if not self.wait_for_all_probes(statuses=["INSTALLED"], timeout=60):
            self.setup_failures.append("Probes did not reach INSTALLED status")
            return

        self.send_weblog_request("/debugger/correlation")
        self.wait_for_all_probes(statuses=["EMITTING"])
        self.wait_for_all_snapshots()

    def test_runtime_id_in_envelope(self):
        self.collect()

        self.assert_setup_ok()
        self.assert_rc_state_not_error()
        self.assert_all_weblog_responses_ok()

        runtime_ids = set()
        for probe_id in self.probe_ids:
            snapshots = self.probe_snapshots.get(probe_id, [])
            assert snapshots, f"no snapshot was received for probe {probe_id}"
            for snapshot in snapshots:
                runtime_id = _runtime_id(snapshot)
                assert runtime_id, f"snapshot for probe {probe_id} is missing a non-empty runtime_id"
                runtime_ids.add(runtime_id)

        assert len(runtime_ids) == 1, f"expected one runtime_id across the run, got {runtime_ids}"


# Follow-on work, split out of feature 564 (which is coordinated sampling via trace_id only).
# There is no dashboard feature for this yet, and it is simply not implemented (not blocked on
# any schema negotiation), so it is not reported.
@features.not_reported
@scenarios.debugger_probes_snapshot
@slow
class Test_Debugger_Generation_Token(debugger.BaseDebuggerTest):
    """Snapshots carry an execution-context generation token alongside thread_id so a reused
    thread id can be disambiguated. Assert the token is present and non-empty.
    """

    def setup_generation_token(self):
        self.initialize_weblog_remote_config()

        probes = debugger.read_probes("probe_snapshot_log_correlation")
        for probe in probes:
            probe["id"] = debugger.generate_probe_id("log")
        self.set_probes(probes)

        self.send_rc_probes()
        if not self.wait_for_all_probes(statuses=["INSTALLED"], timeout=60):
            self.setup_failures.append("Probes did not reach INSTALLED status")
            return

        self.send_weblog_request("/debugger/correlation")
        self.wait_for_all_probes(statuses=["EMITTING"])
        self.wait_for_all_snapshots()

    def test_generation_token(self):
        self.collect()

        self.assert_setup_ok()
        self.assert_rc_state_not_error()
        self.assert_all_weblog_responses_ok()

        for probe_id in self.probe_ids:
            snapshots = self.probe_snapshots.get(probe_id, [])
            assert snapshots, f"no snapshot was received for probe {probe_id}"
            for snapshot in snapshots:
                context = snapshot.get("logger", {})
                assert "thread_id" in context, f"snapshot for probe {probe_id} is missing thread_id"
                token = context.get(_GENERATION_TOKEN_FIELD)
                assert token is not None, (
                    f"snapshot for probe {probe_id} is missing the execution-context generation token"
                )
                assert token != "", f"snapshot for probe {probe_id} has an empty execution-context generation token"
