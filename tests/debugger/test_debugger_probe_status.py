# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import tests.debugger.utils as debugger
from utils import scenarios, features, bug, missing_feature, context, flaky


class BaseDebuggerProbeStatusTest(debugger.BaseDebuggerTest):
    """Base class with common methods for status probe tests"""

    expected_diagnostics: dict[str, debugger.ProbeStatus] = {}
    expect_error_on_missing_symbol: bool = False

    def _setup(self, probes_name: str, probe_type: str):
        self.initialize_weblog_remote_config()

        ### prepare probes
        probes = debugger.read_probes(probes_name)

        for probe in probes:
            if probe["where"]["typeName"] == "NotReallyExists":
                suffix = "received"
            else:
                suffix = "installed"
            probe["id"] = debugger.generate_probe_id(probe_type, suffix)

        self.set_probes(probes)

        # The Go debugger can report an ERROR status if a symbol is missing
        # because it knows definitively that a symbol will not later show up.
        if context.library == "golang":
            self.expect_error_on_missing_symbol = True

        ### set expected
        self.expected_diagnostics = {}
        for probe in self.probe_definitions:
            if probe["id"].endswith("installed"):
                self.expected_diagnostics[probe["id"]] = "INSTALLED"
            elif self.expect_error_on_missing_symbol:
                self.expected_diagnostics[probe["id"]] = "ERROR"
            else:
                self.expected_diagnostics[probe["id"]] = "RECEIVED"

        ### send requests
        self.send_rc_probes()
        self.wait_for_all_probes(statuses=["INSTALLED", "RECEIVED"])

    def _assert(self):
        self.collect()

        self.assert_setup_ok()
        self.assert_rc_state_not_error()
        self._validate_diagnostics()

    def _validate_diagnostics(self):
        def _check_probe_status(expected_id, expected_status: debugger.ProbeStatus):
            if expected_id not in self.probe_diagnostics:
                return f"Probe {expected_id} was not received."

            probe_data = self.probe_diagnostics[expected_id]
            actual_status = probe_data["status"]

            if actual_status != expected_status:
                return f"Received probe {expected_id} with status {actual_status}. Expected {expected_status}"
            return None

        assert self.probe_diagnostics, "Probes were not received"

        errors = []
        for expected_id, expected_status in self.expected_diagnostics.items():
            error_message = _check_probe_status(expected_id, expected_status)
            if error_message is not None:
                errors.append(error_message)

        assert not errors, "Probe status errors:\n" + "\n".join(errors)


@features.debugger_method_probe
@scenarios.debugger_probes_status
@bug(context.library == "python@2.16.0", reason="DEBUG-3127")
@bug(context.library == "python@2.16.1", reason="DEBUG-3127")
@flaky(context.library > "php@1.8.3", reason="DEBUG-3814")
@missing_feature(context.library == "nodejs", reason="Not yet implemented", force_skip=True)
@missing_feature(
    context.library == "golang" and context.agent_version < "7.71.0-rc.1", reason="Not yet implemented", force_skip=True
)
class Test_Debugger_Method_Probe_Statuses(BaseDebuggerProbeStatusTest):
    """Tests for method-level probe status"""

    ############ log method probe ############
    def setup_log_method_status(self):
        self._setup("probe_status_log_method", probe_type="log")

    def test_log_method_status(self):
        self._assert()

    ############ metric probe ############
    def setup_metric_status(self):
        self._setup("probe_status_metric", probe_type="metric")

    @missing_feature(context.library == "ruby", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "golang", reason="Not yet implemented", force_skip=True)
    def test_metric_status(self):
        self._assert()

    ############ span probe ############
    def setup_span_method_status(self):
        self._setup("probe_status_span", probe_type="span")

    @missing_feature(context.library == "ruby", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "golang", reason="Not yet implemented", force_skip=True)
    def test_span_method_status(self):
        self._assert()

    ############ span decoration probe ############
    def setup_span_decoration_method_status(self):
        self._setup("probe_status_spandecoration", probe_type="decor")

    @missing_feature(context.library == "ruby", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "golang", reason="Not yet implemented", force_skip=True)
    def test_span_decoration_method_status(self):
        self._assert()


@features.debugger_line_probe
@scenarios.debugger_probes_status
@bug(context.library == "python@2.16.0", reason="DEBUG-3127")
@bug(context.library == "python@2.16.1", reason="DEBUG-3127")
class Test_Debugger_Line_Probe_Statuses(BaseDebuggerProbeStatusTest):
    """Tests for line-level probe status"""

    ############ log line probe ############
    def setup_log_line_status(self):
        self._setup("probe_status_log_line", probe_type="log")

    @missing_feature(context.library == "php", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "golang", reason="Not yet implemented", force_skip=True)
    @flaky(context.library == "nodejs", reason="JIRA-XXX")
    def test_log_line_status(self):
        self._assert()

    ############ metric line probe ############
    def setup_metric_line_status(self):
        self._setup("probe_status_metric_line", probe_type="metric")

    @missing_feature(context.library == "ruby", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "nodejs", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "php", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "golang", reason="Not yet implemented", force_skip=True)
    def test_metric_line_status(self):
        self._assert()

    ############ span decoration line probe ############
    def setup_span_decoration_line_status(self):
        self._setup("probe_status_spandecoration_line", probe_type="decor")

    @missing_feature(context.library == "ruby", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "nodejs", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "php", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "golang", reason="Not yet implemented", force_skip=True)
    def test_span_decoration_line_status(self):
        self._assert()
