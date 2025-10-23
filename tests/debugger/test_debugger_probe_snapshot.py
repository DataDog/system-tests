# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import time
import tests.debugger.utils as debugger


from utils import scenarios, features, missing_feature, context, irrelevant, bug
from utils.interfaces._library.miscs import validate_process_tags


class BaseDebuggerProbeSnaphotTest(debugger.BaseDebuggerTest):
    """Base class with common methods for snapshot probe tests"""

    def _setup(
        self,
        probes_name: str,
        request_path: str,
        probe_type: str,
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

        self.set_probes(probes)

        ### send requests
        self.send_rc_probes()
        if not self.wait_for_all_probes(statuses=["INSTALLED"], timeout=60):
            self.setup_failures.append("Probes did not reach INSTALLED status")
            # Stop the test if the probes did not reach INSTALLED status since the probe won't exist
            # to send a snapshot.
            return

        start_time = time.time()
        self.send_weblog_request(request_path)
        end_time = time.time()
        # Store the total request time for later use in debugging tests where budgets are limited by time.
        self.total_request_time = end_time - start_time

        self.wait_for_all_probes(statuses=["EMITTING"])

        if not self.wait_for_snapshot_received(timeout=60):
            self.setup_failures.append("Snapshot was not received")

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
@missing_feature(context.library == "ruby", reason="Not yet implemented", force_skip=True)
@missing_feature(context.library == "nodejs", reason="Not yet implemented", force_skip=True)
@missing_feature(
    context.library == "golang" and context.agent_version < "7.71.0-rc.1", reason="Not yet implemented", force_skip=True
)
class Test_Debugger_Method_Probe_Snaphots(BaseDebuggerProbeSnaphotTest):
    """Tests for method-level probe snapshots"""

    ### log probe ###
    def setup_log_method_snapshot(self):
        self._setup("probe_snapshot_log_method", "/debugger/log", "log", lines=None)

    @missing_feature(context.library == "nodejs", reason="Not yet implemented")
    def test_log_method_snapshot(self):
        self._assert()
        self._validate_snapshots()

    ### span probe ###
    def setup_span_method_snapshot(self):
        self._setup("probe_snapshot_span_method", "/debugger/span", "span", lines=None)

    @missing_feature(context.library == "golang", reason="Not yet implemented", force_skip=True)
    def test_span_method_snapshot(self):
        self._assert()
        self._validate_spans()

    ### span decoration probe ###
    def setup_span_decoration_method_snapshot(self):
        self._setup(
            "probe_snapshot_span_decoration_method",
            "/debugger/span-decoration/asd/1",
            "decor",
            lines=None,
        )

    @missing_feature(context.library == "golang", reason="Not yet implemented", force_skip=True)
    def test_span_decoration_method_snapshot(self):
        self._assert()
        self._validate_spans()

    ### mix log probe ###
    def setup_mix_snapshot(self):
        self._setup("probe_snapshot_log_mixed", "/debugger/mix/asd/1", "log", lines=None)

    @missing_feature(context.library == "nodejs", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "golang", reason="Not yet implemented", force_skip=True)
    def test_mix_snapshot(self):
        self._assert()
        self._validate_snapshots()


@features.debugger_method_probe
@scenarios.debugger_probes_snapshot_with_scm
@missing_feature(context.library == "php", reason="Not yet implemented", force_skip=True)
@missing_feature(context.library == "ruby", reason="Not yet implemented", force_skip=True)
@missing_feature(context.library == "nodejs", reason="Not yet implemented", force_skip=True)
@missing_feature(
    context.library == "golang" and context.agent_version < "7.71.0-rc.1", reason="Not yet implemented", force_skip=True
)
class Test_Debugger_Method_Probe_Snaphots_With_SCM(BaseDebuggerProbeSnaphotTest):
    """Tests for method-level probe snapshots"""

    ### log probe ###
    def setup_log_method_snapshot(self):
        self._setup("probe_snapshot_log_method", "/debugger/log", "log", lines=None)

    @missing_feature(context.library == "nodejs", reason="Not yet implemented")
    def test_log_method_snapshot(self):
        self._assert()
        self._validate_snapshots()

    ### span probe ###
    def setup_span_method_snapshot(self):
        self._setup("probe_snapshot_span_method", "/debugger/span", "span", lines=None)

    @missing_feature(context.library == "golang", reason="Not yet implemented", force_skip=True)
    def test_span_method_snapshot(self):
        self._assert()
        self._validate_spans()

    ### span decoration probe ###
    def setup_span_decoration_method_snapshot(self):
        self._setup(
            "probe_snapshot_span_decoration_method",
            "/debugger/span-decoration/asd/1",
            "decor",
            lines=None,
        )

    @missing_feature(context.library == "golang", reason="Not yet implemented", force_skip=True)
    def test_span_decoration_method_snapshot(self):
        self._assert()
        self._validate_spans()

    ### mix log probe ###
    def setup_mix_snapshot(self):
        self._setup("probe_snapshot_log_mixed", "/debugger/mix/asd/1", "log", lines=None)

    @missing_feature(context.library == "nodejs", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "golang", reason="Not yet implemented", force_skip=True)
    def test_mix_snapshot(self):
        self._assert()
        self._validate_snapshots()

    def _validate_snapshots(self):
        super()._validate_snapshots()
        for expected_snapshot in self.probe_ids:
            snapshot = self.probe_snapshots[expected_snapshot][0]
            assert "query" in snapshot
            assert isinstance(snapshot["query"], dict)
            assert "ddtags" in snapshot["query"]
            tags = snapshot["query"]["ddtags"][0]
            assert isinstance(tags, str)
            assert "git.repository_url:https://github.com/datadog/hello" in tags
            assert "git.commit.sha:1234hash" in tags


@features.debugger_line_probe
@scenarios.debugger_probes_snapshot
@missing_feature(context.library == "php", reason="Not yet implemented", force_skip=True)
@missing_feature(context.library == "golang", reason="Not yet implemented", force_skip=True)
class Test_Debugger_Line_Probe_Snaphots(BaseDebuggerProbeSnaphotTest):
    """Tests for line-level probe snapshots"""

    ### log probe ###
    def setup_log_line_snapshot(self):
        self._setup("probe_snapshot_log_line", "/debugger/log", "log", lines=None)

    @bug(context.library == "nodejs", reason="DEBUG-4611")
    def test_log_line_snapshot(self):
        self._assert()
        self._validate_snapshots()

    def setup_log_line_snapshot_debug_track(self):
        self.use_debugger_endpoint = True
        self._setup("probe_snapshot_log_line", "/debugger/log", "log", lines=None)

    @missing_feature(context.library == "ruby", reason="DEBUG-4343")
    @missing_feature(context.library == "nodejs", reason="DEBUG-4345")
    def test_log_line_snapshot_debug_track(self):
        """Test that the library sends snapshots to the debug track endpoint (fallback or not)"""
        self._assert()
        self._validate_snapshots()

    def setup_log_line_snapshot_new_destination(self):
        self.use_debugger_endpoint = True
        self._setup("probe_snapshot_log_line", "/debugger/log", "log", lines=None)

    @missing_feature(context.library == "ruby", reason="DEBUG-4343")
    @missing_feature(context.library == "nodejs", reason="DEBUG-4345")
    @missing_feature(context.agent_version < "7.72.0", reason="Endpoint was introduced in 7.72.0", force_skip=True)
    def test_log_line_snapshot_new_destination(self):
        """Test that the library sends snapshots to the debugger/v2/input endpoint"""
        self._assert()
        self._validate_snapshots()
        assert (
            self._debugger_v2_input_snapshots_received()
        ), "Snapshots were not received at the debugger/v2/input endpoint"

    ### span decoration probe ###
    def setup_span_decoration_line_snapshot(self):
        self._setup(
            "probe_snapshot_span_decoration_line",
            "/debugger/span-decoration/asd/1",
            "decor",
            lines=None,
        )

    @missing_feature(context.library == "ruby", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "nodejs", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "golang", reason="Not yet implemented", force_skip=True)
    def test_span_decoration_line_snapshot(self):
        self._assert()
        self._validate_spans()

    @irrelevant(
        condition=context.library == "java" and context.weblog_variant != "spring-boot",
    )
    def setup_process_tags_snapshot(self):
        self._setup("probe_snapshot_log_line", "/debugger/log", "log", lines=None)

    @features.process_tags
    @missing_feature(
        condition=context.library.name != "java" or context.weblog_variant == "spring-boot-3-native",
        reason="Not yet implemented",
    )
    def test_process_tags_snapshot(self):
        self._assert()
        self._validate_snapshots()
        process_tags = None
        for snapshot_key in self.probe_snapshots:
            for snapshot in self.probe_snapshots[snapshot_key]:
                current_process_tags = snapshot["process_tags"]
                if process_tags is None:
                    process_tags = current_process_tags
                    validate_process_tags(process_tags)
                elif process_tags != current_process_tags:
                    raise ValueError(
                        f"Process tags are not matching. Expected ({process_tags}) vs found({current_process_tags})"
                    )


@features.debugger_line_probe
@scenarios.debugger_probes_snapshot_with_scm
@missing_feature(context.library == "php", reason="Not yet implemented", force_skip=True)
@missing_feature(context.library == "golang", reason="Not yet implemented", force_skip=True)
class Test_Debugger_Line_Probe_Snaphots_With_SCM(BaseDebuggerProbeSnaphotTest):
    """Tests for line-level probe snapshots"""

    ### log probe ###
    def setup_log_line_snapshot(self):
        self._setup("probe_snapshot_log_line", "/debugger/log", "log", lines=None)

    @bug(context.library == "nodejs", reason="DEBUG-4611")
    def test_log_line_snapshot(self):
        self._assert()
        self._validate_snapshots()

    ### span decoration probe ###
    def setup_span_decoration_line_snapshot(self):
        self._setup(
            "probe_snapshot_span_decoration_line",
            "/debugger/span-decoration/asd/1",
            "decor",
            lines=None,
        )

    @missing_feature(context.library == "ruby", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "nodejs", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "golang", reason="Not yet implemented", force_skip=True)
    def test_span_decoration_line_snapshot(self):
        self._assert()
        self._validate_spans()

    def _validate_snapshots(self):
        super()._validate_snapshots()
        for expected_snapshot in self.probe_ids:
            snapshot = self.probe_snapshots[expected_snapshot][0]
            assert "query" in snapshot
            assert isinstance(snapshot["query"], dict)
            assert "ddtags" in snapshot["query"]
            tags = snapshot["query"]["ddtags"][0]
            assert isinstance(tags, str)
            assert "git.repository_url:https://github.com/datadog/hello" in tags
            assert "git.commit.sha:1234hash" in tags
