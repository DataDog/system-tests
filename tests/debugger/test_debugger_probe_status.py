# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import tests.debugger.utils as debugger

from utils import scenarios, features, bug, missing_feature, context


@features.debugger
@scenarios.debugger_probes_status
class Test_Debugger_Probe_Statuses(debugger._Base_Debugger_Test):
    expected_diagnostics = {}

    ############ setup ############
    def _setup(self, probes_name: str):
        ### prepare probes
        probes = debugger.read_probes(probes_name)
        self.set_probes(probes)

        ### set expected
        for probe in self.probe_definitions:
            if probe["id"].endswith("installed"):
                self.expected_diagnostics[probe["id"]] = "INSTALLED"
            else:
                self.expected_diagnostics[probe["id"]] = "RECEIVED"

        ### send requests
        self.send_rc_probes()

    ########### assert ############
    def _assert(self):
        self.collect()

        self.assert_rc_state_not_error()
        self._validate_diagnostics()

    def _validate_diagnostics(self):
        def _check_probe_status(expected_id, expected_status):
            if expected_id not in self.probe_diagnostics:
                return f"Probe {expected_id} was not received."

            actual_status = self.probe_diagnostics[expected_id]["status"]
            if actual_status != expected_status and not (
                expected_status == "INSTALLED" and actual_status == "EMITTING"
            ):
                return f"Received probe {expected_id} with status {actual_status}. Expected {expected_status}"

            return None

        assert self.probe_diagnostics, "Probes were not received"

        errors = []
        for expected_id, expected_status in self.expected_diagnostics.items():
            error_message = _check_probe_status(expected_id, expected_status)
            if error_message is not None:
                errors.append(error_message)

        assert not errors, f"Probe status errors:\n" + "\n".join(errors)

    ############ log probe ############
    def setup_probe_status_log(self):
        self._setup("probe_status_log")

    @bug(context.library == "python@2.16.0", reason="DEBUG-3127")
    @bug(context.library == "python@2.16.1", reason="DEBUG-3127")
    def test_probe_status_log(self):
        self._assert()

    ############ metric probe ############
    def setup_probe_status_metric(self):
        self._setup("probe_status_metric")

    @bug(context.library == "python@2.16.0", reason="DEBUG-3127")
    @bug(context.library == "python@2.16.1", reason="DEBUG-3127")
    @missing_feature(context.library == "ruby", reason="Not yet implemented")
    def test_probe_status_metric(self):
        self._assert()

    ############ span probe ############
    def setup_probe_status_span(self):
        self._setup("probe_status_span")

    @missing_feature(context.library == "ruby", reason="Not yet implemented")
    def test_probe_status_span(self):
        self._assert()

    ############ span decoration probe ############
    def setup_probe_status_spandecoration(self):
        self._setup("probe_status_spandecoration")

    @bug(context.library == "python@2.16.0", reason="DEBUG-3127")
    @bug(context.library == "python@2.16.1", reason="DEBUG-3127")
    @missing_feature(context.library == "ruby", reason="Not yet implemented")
    def test_probe_status_spandecoration(self):
        self._assert()
