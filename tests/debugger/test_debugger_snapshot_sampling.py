# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import time

import tests.debugger.utils as debugger

from utils import context, features, scenarios, slow


@features.debugger_probe_budgets
@scenarios.debugger_probes_snapshot
@slow
class Test_Debugger_Sub_Second_Sampling(debugger.BaseDebuggerTest):
    """A snapshot probe honors a sampling.snapshotsPerSecond below 1.

    The probe is hit repeatedly over a few seconds. A tracer that honors the rate emits the first hit
    and skips the others, as its next snapshot is not due for minutes. A tracer that rounds the rate up
    to one per second emits about one snapshot per second of hits, and one that rounds it down to zero
    emits none.

    Each request is its own trace and hits a single capturing probe, so per-trace coordinated sampling,
    which lets the other probes of a kept trace skip their own rate, plays no part.
    """

    _INVOCATIONS = 15
    # Spreads the hits over about four seconds, so a rate rounded up to one per second lets several through.
    _SECONDS_BETWEEN_INVOCATIONS = 0.3

    def _setup(self, snapshots_per_second: float) -> None:
        self.initialize_weblog_remote_config()

        probe = debugger.read_probes("probe_snapshot_log_sampling")[0]
        probe["id"] = debugger.generate_probe_id("log")
        probe["sampling"] = {"snapshotsPerSecond": snapshots_per_second}
        # Tracers without method probes probe the line LogProbe returns on instead.
        lines = self.method_and_language_to_line_number("LogProbe", context.library.name)
        self._rewrite_where_for_lines([probe], lines or None)
        self.set_probes([probe])

        self.send_rc_probes()
        if not self.wait_for_all_probes(statuses=["INSTALLED"], timeout=60):
            self.setup_failures.append("Probe did not reach INSTALLED status")
            return

        start_time = time.time()
        for i in range(self._INVOCATIONS):
            self.send_weblog_request("/debugger/log", reset=(i == 0))
            if i < self._INVOCATIONS - 1:
                time.sleep(self._SECONDS_BETWEEN_INVOCATIONS)
        self.hits_duration = time.time() - start_time

        self.wait_for_all_probes(statuses=["EMITTING"])
        if not self.wait_for_all_snapshots(timeout=60):
            self.setup_failures.append("Snapshot was not received")
            return

        # Returns as soon as a second snapshot lands; a tracer honoring the rate emits one, so it times out.
        self.wait_for_snapshot_count(2, timeout=5)

    def _assert_single_snapshot(self) -> None:
        self.collect()

        self.assert_setup_ok()
        self.assert_rc_state_not_error()
        self.assert_all_probes_are_emitting()
        self.assert_all_weblog_responses_ok()

        for probe_id in self.probe_ids:
            count = len(self.probe_snapshots.get(probe_id, []))
            assert count == 1, (
                f"probe {probe_id} emitted {count} snapshots for {self._INVOCATIONS} hits over "
                f"{self.hits_duration:.1f}s, expected exactly 1"
            )

    def setup_one_snapshot_every_5_minutes(self) -> None:
        self._setup(1 / 300)

    def test_one_snapshot_every_5_minutes(self) -> None:
        """A probe sampled at 1/300 emits only its first hit."""
        self._assert_single_snapshot()

    def setup_one_snapshot_every_hour(self) -> None:
        self._setup(1 / 3600)

    def test_one_snapshot_every_hour(self) -> None:
        """A probe sampled at 1/3600 emits only its first hit."""
        self._assert_single_snapshot()
