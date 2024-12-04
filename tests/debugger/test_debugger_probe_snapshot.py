# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import tests.debugger.utils as debugger

from utils import scenarios, features, bug, missing_feature, context


@features.debugger
@scenarios.debugger_probes_snapshot
class Test_Debugger_Probe_Snaphots(debugger._Base_Debugger_Test):
    ############ setup ############
    def _setup(self, probes_name: str, request_path: str):
        ### prepare probes
        probes = debugger.read_probes(probes_name)
        self.set_probes(probes)

        ### send requests
        self.send_rc_probes()
        self.wait_for_all_probes_installed()
        self.send_weblog_request(request_path)

    ########### assert ############
    def _assert(self):
        self.collect()

        ### assert
        self.assert_rc_state_not_error()
        self.assert_all_probes_are_installed()
        self.assert_all_weblog_responses_ok()

    def _validate_snapshots(self):
        for expected_snapshot in self.probe_ids:
            if expected_snapshot not in self.probe_snapshots:
                raise ValueError("Snapshot " + expected_snapshot + " was not received.")

    def _validate_spans(self):
        for expected_trace in self.probe_ids:
            if expected_trace not in self.probe_spans:
                raise ValueError("Trace " + expected_trace + " was not received.")

    ########### method ############
    ### log probe ###
    def setup_log_method_probe_snaphots(self):
        self._setup("probe_snapshot_log_method", "/debugger/log")

    @bug(library="python", reason="DEBUG-2708, DEBUG-2709")
    def test_log_method_probe_snaphots(self):
        self._assert()
        self._validate_snapshots()

    ### span probe ###
    def setup_span_method_probe_snaphots(self):
        self._setup("probe_snapshot_span_method", "/debugger/span")

    @bug(library="python", reason="DEBUG-2708, DEBUG-2709")
    def test_span_method_probe_snaphots(self):
        self._assert()
        self._validate_spans()

    ### span decoration probe ###
    def setup_span_decoration_method_probe_snaphots(self):
        self._setup("probe_snapshot_span_decoration_method", "/debugger/span-decoration/asd/1")

    @bug(library="python", reason="DEBUG-2708, DEBUG-2709")
    @missing_feature(context.library == "ruby", reason="Not yet implemented")
    def test_span_decoration_method_probe_snaphots(self):
        self._assert()
        self._validate_spans()

    ########### line ############
    ### log probe ###
    def setup_log_line_probe_snaphots(self):
        self._setup("probe_snapshot_log_line", "/debugger/log")

    def test_log_line_probe_snaphots(self):
        self._assert()
        self._validate_snapshots()

    ### span decoration probe ###
    def setup_span_decoration_line_probe_snaphots(self):
        self._setup("probe_snapshot_span_decoration_line", "/debugger/span-decoration/asd/1")

    @missing_feature(context.library == "ruby", reason="Not yet implemented")
    def test_span_decoration_line_probe_snaphots(self):
        self._assert()
        self._validate_spans()

    ########### mix ############
    ### mix log probe ###
    def setup_mix_probe(self):
        self._setup("probe_snapshot_log_mixed", "/debugger/mix/asd/1")

    @bug(library="python", reason="DEBUG-2710")
    def test_mix_probe(self):
        self._assert()
        self._validate_snapshots()
