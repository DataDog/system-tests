# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Dynamic Instrumentation (probe upload/logs/snapshots) and Symbol DB, without a Datadog Agent.

Endpoints/shapes here are derived from reading the dd-trace-py/libdatadog source on the
(unmerged) `bob/agentless-setting` branch, not from live-captured traffic - see
tests/debugger/utils.py::AgentlessBaseDebuggerTest and
utils/_context/_scenarios/debugger_agentless.py for the scenario/interface wiring.
"""

import tests.debugger.utils as debugger
from utils import features, scenarios


@features.debugger
@scenarios.debugger_agentless
class Test_Agentless_Debugger_Probe_Snapshot(debugger.AgentlessBaseDebuggerTest):
    """A log probe installed via the agentless native RC client emits a snapshot directly to
    the agentless debugger intake, with no Datadog Agent involved.
    """

    def setup_log_method_snapshot(self):
        self.initialize_weblog_remote_config()

        probes = debugger.read_probes("probe_snapshot_log_method")
        for probe in probes:
            probe["id"] = debugger.generate_probe_id("log")
        self.set_probes(probes)

        self.send_rc_probes()
        if not self.wait_for_all_probes(statuses=["INSTALLED"], timeout=60):
            self.setup_failures.append("Probes did not reach INSTALLED status")
            return

        self.send_weblog_request("/debugger/log")
        self.wait_for_all_probes(statuses=["EMITTING"])
        if not self.wait_for_all_snapshots(timeout=60):
            self.setup_failures.append("Snapshot was not received")

    def test_log_method_snapshot(self):
        self.collect()

        self.assert_setup_ok()
        self.assert_rc_state_not_error()
        self.assert_all_probes_are_emitting()

        for probe_id in self.probe_ids:
            assert probe_id in self.probe_snapshots, f"No snapshot was captured for probe {probe_id}"
            assert len(self.probe_snapshots[probe_id]) > 0, f"No snapshot was captured for probe {probe_id}"

        path = self._snapshot_paths[0]
        requests = list(self._backend_interface.get_data(path))
        assert len(requests) > 0, f"No request captured on {path}"

        request = requests[-1]
        assert request["host"] == "debugger-intake.mock-intake.invalid"
        headers = {name.lower(): value for name, value in request["request"]["headers"]}
        assert "dd-api-key" in headers


@features.debugger_symdb
@scenarios.debugger_agentless
class Test_Agentless_SymbolDB(debugger.AgentlessBaseDebuggerTest):
    """Symbol DB, forced via _DD_SYMBOL_DATABASE_FORCE_UPLOAD, uploads directly to the agentless
    debugger intake (the same unified path as logs/snapshots/diagnostics in agentless mode).
    """

    def setup_symdb_upload(self):
        self.initialize_weblog_remote_config()

    def test_symdb_upload(self):
        self.collect()
        self.assert_setup_ok()

        assert len(self.symbols) > 0, "No symbol files were found"

        errors = []
        for symbol in self.symbols:
            error = symbol.get("system-tests-error")
            if error is not None:
                errors.append(
                    f"Error is: {error}, exported to file: {symbol.get('system-tests-file-path', 'No file path')}"
                )
        assert not errors, "Found system-tests-errors:\n" + "\n".join(f"- {err}" for err in errors)

        requests = list(self._symbols_interface.get_data(self._symbols_path))
        assert len(requests) > 0, f"No request captured on {self._symbols_path}"
        headers = {name.lower(): value for name, value in requests[-1]["request"]["headers"]}
        assert "dd-api-key" in headers
