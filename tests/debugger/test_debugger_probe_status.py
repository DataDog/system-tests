# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import tests.debugger.utils as debugger
from utils import scenarios, features, bug, missing_feature, context, flaky


class BaseDebuggerProbeStatusTest(debugger.BaseDebuggerTest):
    """Base class with common methods for status probe tests"""

    expected_diagnostics: dict = {}

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

        ### set expected
        self.expected_diagnostics = {}
        for probe in self.probe_definitions:
            if probe["id"].endswith("installed"):
                self.expected_diagnostics[probe["id"]] = "INSTALLED"
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

    def _check_probe_status(self, expected_id, expected_status):
        if expected_id not in self.probe_diagnostics:
            return f"Probe {expected_id} was not received."

        actual_status = self.probe_diagnostics[expected_id]["status"]
        if actual_status != expected_status:
            return f"Received probe {expected_id} with status {actual_status}. Expected {expected_status}"

        return None

    def _validate_diagnostics(self):
        assert self.probe_diagnostics, "Probes were not received"

        errors = []
        for expected_id, expected_status in self.expected_diagnostics.items():
            error_message = self._check_probe_status(expected_id, expected_status)
            if error_message is not None:
                errors.append(error_message)

        assert not errors, "Probe status errors:\n" + "\n".join(errors)


@features.debugger_method_probe
@scenarios.debugger_probes_status
@bug(context.library == "python@2.16.0", reason="DEBUG-3127")
@bug(context.library == "python@2.16.1", reason="DEBUG-3127")
@flaky(context.library > "php@1.8.3", reason="DEBUG-3814")
@missing_feature(context.library == "nodejs", reason="Not yet implemented", force_skip=True)
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
    def test_metric_status(self):
        self._assert()

    ############ span probe ############
    def setup_span_method_status(self):
        self._setup("probe_status_span", probe_type="span")

    @missing_feature(context.library == "ruby", reason="Not yet implemented", force_skip=True)
    def test_span_method_status(self):
        self._assert()

    ############ span decoration probe ############
    def setup_span_decoration_method_status(self):
        self._setup("probe_status_spandecoration", probe_type="decor")

    @missing_feature(context.library == "ruby", reason="Not yet implemented", force_skip=True)
    def test_span_decoration_method_status(self):
        self._assert()


@features.debugger_method_probe
@scenarios.debugger_probes_status_with_scm
@bug(context.library == "python@2.16.0", reason="DEBUG-3127")
@bug(context.library == "python@2.16.1", reason="DEBUG-3127")
@flaky(context.library > "php@1.8.3", reason="DEBUG-3814")
@missing_feature(context.library == "nodejs", reason="Not yet implemented", force_skip=True)
class Test_Debugger_Method_Probe_Statuses_With_SCM(BaseDebuggerProbeStatusTest):
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
    def test_metric_status(self):
        self._assert()

    ############ span probe ############
    def setup_span_method_status(self):
        self._setup("probe_status_span", probe_type="span")

    @missing_feature(context.library == "ruby", reason="Not yet implemented", force_skip=True)
    def test_span_method_status(self):
        self._assert()

    ############ span decoration probe ############
    def setup_span_decoration_method_status(self):
        self._setup("probe_status_spandecoration", probe_type="decor")

    @missing_feature(context.library == "ruby", reason="Not yet implemented", force_skip=True)
    def test_span_decoration_method_status(self):
        self._assert()

    def _check_probe_status(self, expected_id, expected_status):
        msg = super()._check_probe_status(expected_id, expected_status)
        if msg is not None:
            return msg
            
        if expected_id not in self.probe_diagnostics:
            return f"Probe {expected_id} was not received."

        query = self.probe_diagnostics[expected_id]["query"]
        if not query:
            return f'Probe {expected_id} did not send query string.'
            
        if 'ddtags' not in query:
            return f'Probe {expected_id} did not send ddtags in query string.'
        tags = query['ddtags'][0]
        if 'git.repository_url:' not in tags:
            return f'Probe {expected_id} did not send git.repository_url metadata.'
        if 'git.repository_url:https://github.com/datadog/hello' not in tags:
            return f'Probe {expected_id} did not send git.repository_url metadata correctly.'
        if 'git.commit.sha:' not in tags:
            return f'Probe {expected_id} did not send git.commit.sha metadata.'
        if 'git.commit.sha:1234hash' not in tags:
            return f'Probe {expected_id} did not send git.commit.sha metadata correctly.'

        return None


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
    def test_log_line_status(self):
        self._assert()

    ############ metric line probe ############
    def setup_metric_line_status(self):
        self._setup("probe_status_metric_line", probe_type="metric")

    @missing_feature(context.library == "ruby", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "nodejs", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "php", reason="Not yet implemented", force_skip=True)
    def test_metric_line_status(self):
        self._assert()

    ############ span decoration line probe ############
    def setup_span_decoration_line_status(self):
        self._setup("probe_status_spandecoration_line", probe_type="decor")

    @missing_feature(context.library == "ruby", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "nodejs", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "php", reason="Not yet implemented", force_skip=True)
    def test_span_decoration_line_status(self):
        self._assert()


@features.debugger_line_probe
@scenarios.debugger_probes_status_with_scm
@bug(context.library == "python@2.16.0", reason="DEBUG-3127")
@bug(context.library == "python@2.16.1", reason="DEBUG-3127")
class Test_Debugger_Line_Probe_Statuses_With_SCM(BaseDebuggerProbeStatusTest):
    """Tests for line-level probe status"""

    ############ log line probe ############
    def setup_log_line_status(self):
        self._setup("probe_status_log_line", probe_type="log")

    @missing_feature(context.library == "php", reason="Not yet implemented", force_skip=True)
    def test_log_line_status(self):
        self._assert()

    ############ metric line probe ############
    def setup_metric_line_status(self):
        self._setup("probe_status_metric_line", probe_type="metric")

    @missing_feature(context.library == "ruby", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "nodejs", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "php", reason="Not yet implemented", force_skip=True)
    def test_metric_line_status(self):
        self._assert()

    ############ span decoration line probe ############
    def setup_span_decoration_line_status(self):
        self._setup("probe_status_spandecoration_line", probe_type="decor")

    @missing_feature(context.library == "ruby", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "nodejs", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "php", reason="Not yet implemented", force_skip=True)
    def test_span_decoration_line_status(self):
        self._assert()

    def _check_probe_status(self, expected_id, expected_status):
        msg = super()._check_probe_status(expected_id, expected_status)
        if msg is not None:
            return msg
            
        if expected_id not in self.probe_diagnostics:
            return f"Probe {expected_id} was not received."

        query = self.probe_diagnostics[expected_id]["query"]
        if not query:
            return f'Probe {expected_id} did not send query string.'
            
        if 'ddtags' not in query:
            return f'Probe {expected_id} did not send ddtags in query string.'
        tags = query['ddtags'][0]
        if 'git.repository_url:' not in tags:
            return f'Probe {expected_id} did not send git.repository_url metadata.'
        if 'git.repository_url:https://github.com/datadog/hello' not in tags:
            return f'Probe {expected_id} did not send git.repository_url metadata correctly.'
        if 'git.commit.sha:' not in tags:
            return f'Probe {expected_id} did not send git.commit.sha metadata.'
        if 'git.commit.sha:1234hash' not in tags:
            return f'Probe {expected_id} did not send git.commit.sha metadata correctly.'

        return None
