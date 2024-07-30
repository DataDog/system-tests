# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import tests.debugger.utils as base

from utils import scenarios, features, remote_config as rc


@features.debugger
@scenarios.debugger_probes_status
class Test_Debugger_Probe_Statuses(base._Base_Debugger_Test):
    version = 0
    expected_status_map = {}

    def _setup(self, probes):
        Test_Debugger_Probe_Statuses.version += 1
        self.rc_state = rc.send_debugger_command(probes=probes, version=Test_Debugger_Probe_Statuses.version)

    def _assert(self):
        self.assert_all_states_not_error()
        self._validate_probe_status(self.expected_status_map)

    def setup_probe_status_log(self):
        message_map, probes = self._get_probes("probe_status_log")
        self.expected_status_map = message_map

        self._setup(probes)

    def test_probe_status_log(self):
        self._assert()

    def setup_probe_status_metric(self):
        message_map, probes = self._get_probes("probe_status_metric")
        self.expected_status_map = message_map

        self._setup(probes)

    def test_probe_status_metric(self):
        self._assert()

    def setup_probe_status_span(self):
        message_map, probes = self._get_probes("probe_status_span")
        self.expected_status_map = message_map

        self._setup(probes)

    def test_probe_status_span(self):
        self._assert()

    def setup_probe_status_spandecoration(self):
        message_map, probes = self._get_probes("probe_status_spandecoration")
        self.expected_status_map = message_map

        self._setup(probes)

    def test_probe_status_spandecoration(self):
        self._assert()

    def _get_probes(self, probes_name: str):
        expected_status_map = {}

        probes = base.read_probes(probes_name)
        for probe in probes:
            if probe["id"].endswith("installed"):
                expected_status_map[probe["id"]] = "INSTALLED"
            else:
                expected_status_map[probe["id"]] = "RECEIVED"

        return expected_status_map, probes

    def _validate_probe_status(self, expected_probes):
        def _check_probe_status(expected_id, expected_status, probe_status_map):
            if expected_id not in probe_status_map:
                return f"Probe {expected_id} was not received."

            actual_status = probe_status_map[expected_id]["status"]
            if actual_status != expected_status and not (
                expected_status == "INSTALLED" and actual_status == "EMITTING"
            ):
                return f"Received probe {expected_id} with status {actual_status}. Expected {expected_status}"

            return None

        errors = []
        probe_map = base.get_probes_map(base.read_diagnostic_data())

        assert probe_map, "Probes were not receieved"

        for expected_id, expected_status in expected_probes.items():
            error_message = _check_probe_status(expected_id, expected_status, probe_map)
            if error_message is not None:
                errors.append(error_message)

        assert not errors, f"Probe status errors:\n" + "\n".join(errors)
