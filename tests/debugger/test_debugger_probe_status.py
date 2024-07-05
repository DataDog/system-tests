# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import tests.debugger.utils as base

from utils import (
    scenarios,
    interfaces,
    features,
    remote_config as rc,
)


@features.debugger
@scenarios.debugger_probes_status
class Test_Debugger_Probe_Statuses(base._Base_Debugger_Test):
    version = 0

    def _setup(self, probes_name: str):
        Test_Debugger_Probe_Statuses.version += 1

        self.rc_state = rc.send_debugger_command(
            probes=base.read_probes(probes_name), version=Test_Debugger_Probe_Statuses.version
        )

    def setup_method_probe_status_method_log(self):
        self._setup("probe_status_method_log")

    def test_method_probe_status_method_log(self):
        expected_probes = {
            "loga0cf2-meth-45cf-9f39-591received": "RECEIVED",
            "loga0cf2-meth-45cf-9f39-59installed": "INSTALLED",
        }

        self.assert_all_states_not_error()
        base.validate_probes(expected_probes)

    def setup_method_probe_status_method_metric(self):
        self._setup("probe_status_method_metric")

    def test_method_probe_status_method_metric(self):
        expected_probes = {
            "metricf2-meth-45cf-9f39-591received": "RECEIVED",
            "metricf2-meth-45cf-9f39-59installed": "INSTALLED",
        }

        self.assert_all_states_not_error()
        base.validate_probes(expected_probes)

    def setup_method_probe_status_method_span(self):
        self._setup("probe_status_method_span")

    def test_method_probe_status_method_span(self):
        expected_probes = {
            "span0cf2-meth-45cf-9f39-591received": "RECEIVED",
            "span0cf2-meth-45cf-9f39-59installed": "INSTALLED",
        }

        self.assert_all_states_not_error()
        base.validate_probes(expected_probes)

    def setup_method_probe_status_method_spandecoration(self):
        self._setup("probe_status_method_spandecoration")

    def test_method_probe_status_method_spandecoration(self):
        expected_probes = {
            "decorcf2-meth-45cf-9f39-591received": "RECEIVED",
            "decorcf2-meth-45cf-9f39-59installed": "INSTALLED",
        }

        self.assert_all_states_not_error()
        base.validate_probes(expected_probes)
