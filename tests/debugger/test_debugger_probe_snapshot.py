# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import time
import tests.debugger.utils as debugger
from tests.debugger.utils import EvaluationPoint

from utils import scenarios, features, missing_feature, context, logger


class BaseDebuggerProbeSnaphotTest(debugger.BaseDebuggerTest):
    """Base class with common methods for snapshot probe tests"""
    
    def _setup(
        self,
        probes_name: str,
        request_path: str,
        probe_type: str,
        evaluate_at: EvaluationPoint,
        lines=None,
    ):
        self.initialize_weblog_remote_config()

        ### prepare probes
        probes = debugger.read_probes(probes_name)

        # Update probe IDs using the generate_probe_id function with the provided probe_type
        for probe in probes:
            probe["id"] = debugger.generate_probe_id(probe_type)

        if lines is not None:
            for probe in probes:
                if "methodName" in probe["where"]:
                    del probe["where"]["methodName"]
                probe["where"]["lines"] = lines
                probe["where"]["sourceFile"] = "ACTUAL_SOURCE_FILE"
                probe["where"]["typeName"] = None

        self.set_probes(probes, evaluate_at=evaluate_at)

        ### send requests
        self.send_rc_probes()
        self.wait_for_all_probes_installed()

        start_time = time.time()
        self.send_weblog_request(request_path)
        end_time = time.time()
        # Store the total request time for later use in debugging tests where budgets are limited by time.
        self.total_request_time = end_time - start_time

        self.wait_for_all_probes_emitting()

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

            # Make sure there's at least one span for this trace
            if not self.probe_spans[expected_trace]:
                raise ValueError(f"No spans found for trace {expected_trace}")


@features.debugger_method_probe
@scenarios.debugger_probes_snapshot
@missing_feature(context.library == "php", reason="Not yet implemented", force_skip=True)
class Test_Debugger_Method_Probe_Snaphots(BaseDebuggerProbeSnaphotTest):
    """Tests for method-level probe snapshots"""
    
    ### log probe ###
    def setup_log_method_exit_snapshot(self):
        self._setup("probe_snapshot_log_method", "/debugger/log", "log", evaluate_at=EvaluationPoint.EXIT)

    @missing_feature(context.library == "nodejs", reason="Not yet implemented")
    def test_log_method_exit_snapshot(self):
        self._assert()
        self._validate_snapshots()

    def setup_log_method_entry_snapshot(self):
        self._setup("probe_snapshot_log_method", "/debugger/log", "log", evaluate_at=EvaluationPoint.ENTRY)

    @missing_feature(context.library == "nodejs", reason="Not yet implemented")
    def test_log_method_entry_snapshot(self):
        self._assert()
        self._validate_snapshots()

    ### span probe ###
    def setup_span_method_exit_snapshot(self):
        self._setup("probe_snapshot_span_method", "/debugger/span", "span", evaluate_at=EvaluationPoint.EXIT)

    @missing_feature(context.library == "ruby", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "nodejs", reason="Not yet implemented", force_skip=True)
    def test_span_method_exit_snapshot(self):
        self._assert()
        self._validate_spans()

    def setup_span_method_entry_snapshot(self):
        self._setup("probe_snapshot_span_method", "/debugger/span", "span", evaluate_at=EvaluationPoint.ENTRY)

    @missing_feature(context.library == "ruby", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "nodejs", reason="Not yet implemented", force_skip=True)
    def test_span_method_entry_snapshot(self):
        self._assert()
        self._validate_spans()

    ### span decoration probe ###
    def setup_span_decoration_method_exit_snapshot(self):
        self._setup(
            "probe_snapshot_span_decoration_method",
            "/debugger/span-decoration/asd/1",
            "decor",
            evaluate_at=EvaluationPoint.EXIT,
        )

    @missing_feature(context.library == "ruby", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "nodejs", reason="Not yet implemented", force_skip=True)
    def test_span_decoration_method_exit_snapshot(self):
        self._assert()
        self._validate_spans()

    def setup_span_decoration_method_entry_snapshot(self):
        self._setup(
            "probe_snapshot_span_decoration_method",
            "/debugger/span-decoration/asd/1",
            "decor",
            evaluate_at=EvaluationPoint.ENTRY,
        )

    @missing_feature(context.library == "ruby", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "nodejs", reason="Not yet implemented", force_skip=True)
    def test_span_decoration_method_entry_snapshot(self):
        self._assert()
        self._validate_spans()

    ### mix log probe ###
    def setup_mix_exit_snapshot(self):
        self._setup("probe_snapshot_log_mixed", "/debugger/mix/asd/1", "log", evaluate_at=EvaluationPoint.EXIT)

    @missing_feature(context.library == "nodejs", reason="Not yet implemented", force_skip=True)
    def test_mix_exit_snapshot(self):
        self._assert()
        self._validate_snapshots()

    def setup_mix_entry_snapshot(self):
        self._setup("probe_snapshot_log_mixed", "/debugger/mix/asd/1", "log", evaluate_at=EvaluationPoint.ENTRY)

    @missing_feature(context.library == "nodejs", reason="Not yet implemented", force_skip=True)
    def test_mix_entry_snapshot(self):
        self._assert()
        self._validate_snapshots()


@features.debugger_line_probe
@scenarios.debugger_probes_snapshot
@missing_feature(context.library == "php", reason="Not yet implemented", force_skip=True)
class Test_Debugger_Line_Probe_Snaphots(BaseDebuggerProbeSnaphotTest):
    """Tests for line-level probe snapshots"""
    
    ### log probe ###
    def setup_log_line_exit_snapshot(self):
        self._setup("probe_snapshot_log_line", "/debugger/log", "log", evaluate_at=EvaluationPoint.EXIT)

    def test_log_line_exit_snapshot(self):
        self._assert()
        self._validate_snapshots()

    def setup_log_line_entry_snapshot(self):
        self._setup("probe_snapshot_log_line", "/debugger/log", "log", evaluate_at=EvaluationPoint.ENTRY)

    def test_log_line_entry_snapshot(self):
        self._assert()
        self._validate_snapshots()

    ### span decoration probe ###
    def setup_span_decoration_line_exit_snapshot(self):
        self._setup(
            "probe_snapshot_span_decoration_line",
            "/debugger/span-decoration/asd/1",
            "decor",
            evaluate_at=EvaluationPoint.EXIT,
        )

    @missing_feature(context.library == "ruby", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "nodejs", reason="Not yet implemented", force_skip=True)
    def test_span_decoration_line_exit_snapshot(self):
        self._assert()
        self._validate_spans()

    def setup_span_decoration_line_entry_snapshot(self):
        self._setup(
            "probe_snapshot_span_decoration_line",
            "/debugger/span-decoration/asd/1",
            "decor",
            evaluate_at=EvaluationPoint.ENTRY,
        )

    @missing_feature(context.library == "ruby", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "nodejs", reason="Not yet implemented", force_skip=True)
    def test_span_decoration_line_entry_snapshot(self):
        self._assert()
        self._validate_spans()
