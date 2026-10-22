# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import tests.debugger.utils as debugger

from utils import context, scenarios, features, rfc, slow

_RFC = "https://docs.google.com/document/d/17BQ1cEcJuumpMWMtBItIx9x_akG99dzjBA1NoaBFuBE/edit?tab=t.4l0zjxovcnz3#heading=h.kejjaf501thi"


class _DebuggerCoordinatedSamplingTest(debugger.BaseDebuggerTest):
    """The sampling decision is made once per trace, so a trace emits its whole probe chain or none of it.

    Correlation rides on the dd.trace_id already in the snapshot envelope. The probes get different
    per-probe rates, so independent per-probe sampling emits partial chains, which is what makes the
    assertion discriminating.
    """

    _INVOCATIONS = 30
    # The leaf is the first probe hit in each request, so it makes the trace's sampling decision, and
    # its rate allows every request to be sampled. A request takes about 800ms, so the probes limited
    # to one snapshot per second are skipped in about every other request unless they follow the
    # trace's decision.
    _SNAPSHOTS_PER_SECOND = {"CorrelationLeaf": 5, "CorrelationMiddle": 1, "Correlation": 1}

    def _prepare_probe(self, probe: dict) -> None:
        pass

    def setup_coordinated_per_trace_sampling(self):
        self.initialize_weblog_remote_config()

        probes = debugger.read_probes("probe_snapshot_log_correlation")
        for probe in probes:
            probe["id"] = debugger.generate_probe_id("log")
            probe["sampling"] = {"snapshotsPerSecond": self._SNAPSHOTS_PER_SECOND[probe["where"]["methodName"]]}
            self._prepare_probe(probe)
        self.set_probes(probes)

        self.send_rc_probes()
        if not self.wait_for_all_probes(statuses=["INSTALLED"], timeout=60):
            self.setup_failures.append("Probes did not reach INSTALLED status")
            return

        # Each request is one trace, so it is one sampling unit.
        for i in range(self._INVOCATIONS):
            self.send_weblog_request("/debugger/correlation", reset=(i == 0))

        self.wait_for_all_probes(statuses=["EMITTING"])
        self.wait_for_all_snapshots()

    def test_coordinated_per_trace_sampling(self):
        """Every trace emits either all of its probes or none of them."""
        self.collect()

        self.assert_setup_ok()
        self.assert_rc_state_not_error()
        self.assert_all_weblog_responses_ok()

        chain = set(self.probe_ids)

        probes_by_trace: dict[str, set[str]] = {}
        for probe_id in self.probe_ids:
            for snapshot in self.probe_snapshots.get(probe_id, []):
                # Tolerate the nested dd object (Python/Node/Ruby nest) and the flat dotted
                # key (Java/.NET/Go/Ruby dotted) for the trace id.
                trace_id = snapshot.get("dd", {}).get("trace_id") or snapshot.get("dd.trace_id")
                assert trace_id, f"snapshot for probe {probe_id} is missing dd.trace_id on the wire"
                probes_by_trace.setdefault(trace_id, set()).add(probe_id)

        full = [trace_id for trace_id, probes in probes_by_trace.items() if probes == chain]
        partial = [trace_id for trace_id, probes in probes_by_trace.items() if probes != chain]

        assert not partial, (
            f"partial probe chains were emitted, the sampling decision is not made once per trace: {partial}"
        )
        assert full, "no trace emitted the full probe chain"


@rfc(_RFC)
@features.debugger_snapshot_correlation
@scenarios.debugger_probes_snapshot
@slow
class Test_Debugger_Coordinated_Sampling(_DebuggerCoordinatedSamplingTest):
    """Probes the methods of the correlation endpoint."""


@rfc(_RFC)
@features.debugger_snapshot_correlation
@scenarios.debugger_probes_snapshot
@slow
class Test_Debugger_Coordinated_Sampling_Line_Probe(_DebuggerCoordinatedSamplingTest):
    """Probes the line each method of the correlation endpoint returns on, for tracers without method probes."""

    def _prepare_probe(self, probe: dict) -> None:
        lines = self.method_and_language_to_line_number(probe["where"]["methodName"], context.library.name)
        self._rewrite_where_for_lines([probe], lines)


# Follow-on work, split out of feature 564 (which is coordinated sampling via trace_id only). There
# is no dashboard feature for these yet, and they are simply not implemented (not blocked on any
# schema negotiation), so they are not reported.
@features.not_reported
@scenarios.debugger_probes_snapshot
@slow
class Test_Debugger_Snapshot_Correlation_Fields(debugger.BaseDebuggerTest):
    """Identity fields that make a snapshot correlatable: the per-process runtime_id in the envelope,
    and a generation token that disambiguates a reused thread id.
    """

    def _setup(self):
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

    def _assert(self):
        self.collect()

        self.assert_setup_ok()
        self.assert_rc_state_not_error()
        self.assert_all_weblog_responses_ok()

    def setup_runtime_id_in_envelope(self):
        self._setup()

    def test_runtime_id_in_envelope(self):
        """Every snapshot carries the same non-empty runtime_id, since all come from one process."""
        self._assert()

        runtime_ids = set()
        for probe_id in self.probe_ids:
            snapshots = self.probe_snapshots.get(probe_id, [])
            assert snapshots, f"no snapshot was received for probe {probe_id}"
            for snapshot in snapshots:
                # The envelope does not carry it today, so tolerate the root or the "dd" object.
                runtime_id = snapshot.get("runtime_id") or snapshot.get("dd", {}).get("runtime_id")
                assert runtime_id, f"snapshot for probe {probe_id} is missing a non-empty runtime_id"
                runtime_ids.add(runtime_id)

        assert len(runtime_ids) == 1, f"expected one runtime_id across the run, got {runtime_ids}"

    def setup_generation_token(self):
        self._setup()

    def test_generation_token(self):
        """Every snapshot carries a generation token alongside thread_id."""
        self._assert()

        for probe_id in self.probe_ids:
            snapshots = self.probe_snapshots.get(probe_id, [])
            assert snapshots, f"no snapshot was received for probe {probe_id}"
            for snapshot in snapshots:
                context = snapshot.get("logger", {})
                assert "thread_id" in context, f"snapshot for probe {probe_id} is missing thread_id"
                assert context.get("generation") not in (None, ""), (
                    f"snapshot for probe {probe_id} is missing the execution-context generation token"
                )
