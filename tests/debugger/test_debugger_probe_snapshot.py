# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import tests.debugger.utils as debugger

from utils import scenarios, features, missing_feature, context, rfc


@features.debugger
@scenarios.debugger_probes_snapshot
class Test_Debugger_Probe_Snaphots(debugger._Base_Debugger_Test):
    ############ setup ############
    def _setup(self, probes_name: str, request_path: str):
        self.initialize_weblog_remote_config()

        ### prepare probes
        probes = debugger.read_probes(probes_name)
        self.set_probes(probes)

        ### send requests
        self.send_rc_probes()
        self.wait_for_all_probes_installed()
        self.send_weblog_request(request_path)
        self.wait_for_all_probes_emitting()

    ########### assert ############
    def _assert(self):
        self.collect()

        ### assert
        self.assert_setup_ok()
        self.assert_rc_state_not_error()
        self.assert_all_probes_are_emitting()
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

    @missing_feature(context.library == "nodejs", reason="Not yet implemented")
    def test_log_method_probe_snaphots(self):
        self._assert()
        self._validate_snapshots()

    ### span probe ###
    def setup_span_method_probe_snaphots(self):
        self._setup("probe_snapshot_span_method", "/debugger/span")

    @missing_feature(context.library == "ruby", reason="Not yet implemented")
    @missing_feature(context.library == "nodejs", reason="Not yet implemented")
    def test_span_method_probe_snaphots(self):
        self._assert()
        self._validate_spans()

    ### span decoration probe ###
    def setup_span_decoration_method_probe_snaphots(self):
        self._setup("probe_snapshot_span_decoration_method", "/debugger/span-decoration/asd/1")

    @missing_feature(context.library == "ruby", reason="Not yet implemented")
    @missing_feature(context.library == "nodejs", reason="Not yet implemented")
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
    @missing_feature(context.library == "nodejs", reason="Not yet implemented")
    def test_span_decoration_line_probe_snaphots(self):
        self._assert()
        self._validate_spans()

    ########### mix ############
    ### mix log probe ###
    def setup_mix_probe(self):
        self._setup("probe_snapshot_log_mixed", "/debugger/mix/asd/1")

    @missing_feature(context.library == "nodejs", reason="Not yet implemented")
    def test_mix_probe(self):
        self._assert()
        self._validate_snapshots()

    ############ test ############
    @rfc(
        "https://docs.google.com/document/d/1lhaEgBGIb9LATLsXxuKDesx4BCYixOcOzFnr4qTTemw/edit?pli=1&tab=t.0#heading=h.o5gstqo08gu5"
    )
    def setup_code_origin_entry_present(self):
        # Code origins are automatically included in spans, so we don't need to configure probes.
        self.initialize_weblog_remote_config()
        self.send_weblog_request("/healthcheck")

    @features.debugger_code_origins
    @missing_feature(context.library == "dotnet", reason="Entry spans code origins not yet implemented")
    @missing_feature(context.library == "java", reason="Entry spans code origins not yet implemented for spring-mvc")
    @missing_feature(context.library == "nodejs", reason="Entry spans code origins not yet implemented for express")
    @missing_feature(context.library == "ruby", reason="Entry spans code origins not yet implemented")
    def test_code_origin_entry_present(self):
        self.collect()

        self.assert_setup_ok()
        self.assert_all_weblog_responses_ok()

        code_origins_entry_found = False
        for span in self.all_spans:
            # Web spans for the healthcheck should have code origins defined.
            resource, resource_type = span.get("resource", None), span.get("type", None)
            if resource == "GET /healthcheck" and resource_type == "web":
                code_origin_type = span["meta"].get("_dd.code_origin.type", "")
                code_origins_entry_found = code_origin_type == "entry"

        assert code_origins_entry_found
