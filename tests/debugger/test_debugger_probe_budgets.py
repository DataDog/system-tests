# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import time
import tests.debugger.utils as debugger

from utils import scenarios, features, missing_feature, context


@features.debugger_probe_budgets
@scenarios.debugger_probes_snapshot
@missing_feature(context.library == "golang", reason="Not yet implemented", force_skip=True)
class Test_Debugger_Probe_Budgets(debugger.BaseDebuggerTest):
    def _setup(
        self,
        probes_name: str,
        request_path: str,
        lines: list | None,
        probe_type: str = "log",
    ):
        self.initialize_weblog_remote_config()

        ### prepare probes
        probes = debugger.read_probes(probes_name)

        # Update probe IDs using the generate_probe_id function with the provided probe_type
        for probe in probes:
            probe["id"] = debugger.generate_probe_id(probe_type)

        for probe in probes:
            if "methodName" in probe["where"]:
                del probe["where"]["methodName"]
            probe["where"]["lines"] = lines
            probe["where"]["sourceFile"] = "ACTUAL_SOURCE_FILE"
            probe["where"]["typeName"] = None

        self.set_probes(probes)

        ### send requests
        self.send_rc_probes()
        self.wait_for_all_probes(statuses=["INSTALLED"])

        start_time = time.time()
        self.send_weblog_request(request_path)
        end_time = time.time()
        # Store the total request time for later use in debugging tests where budgets are limited by time.
        self.total_request_time = end_time - start_time

        self.wait_for_all_probes(statuses=["EMITTING"])

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

    def setup_log_line_budgets(self):
        self._setup(
            "probe_snapshot_log_line_budgets",
            "/debugger/budgets/150",
            lines=self.method_and_language_to_line_number("Budgets", self.get_tracer()["language"]),
        )

    @missing_feature(context.library == "nodejs", reason="Not yet implemented", force_skip=True)
    @missing_feature(context.library == "golang", reason="Not yet implemented", force_skip=True)
    def test_log_line_budgets(self):
        self._assert()
        self._validate_snapshots()

        snapshots_with_captures = 0
        for _id in self.probe_ids:
            for span in self.probe_snapshots[_id]:
                snapshot_with_captures = span.get("debugger", {}).get("snapshot", {}).get("captures", None)
                if snapshot_with_captures is None:
                    continue

                snapshots_with_captures += 1

            # Probe budgets aren't exact and can take time to be applied, so we allow a range of 1-20 snapshots with
            # captures for 150 requests.
            assert 1 <= snapshots_with_captures <= 20, (
                f"Expected 1-20 snapshot with captures, got {snapshots_with_captures} in {self.total_request_time} seconds"
            )

    def setup_span_probe_expression_budgets(self):
        self.initialize_weblog_remote_config()

        probes = debugger.read_probes("probe_span_method_budgets_expression")
        for probe in probes:
            probe["id"] = debugger.generate_probe_id("decor")

        self.set_probes(probes)
        self.send_rc_probes()
        self.wait_for_all_probes(statuses=["INSTALLED"])

        start_time = time.time()
        self.send_weblog_request("/debugger/budgets/1")
        for _ in range(149):
            self.send_weblog_request("/debugger/budgets/1", reset=False)
        end_time = time.time()
        self.total_request_time = end_time - start_time

        # Allow time for the agent to receive data after the last request
        time.sleep(2)

    def test_span_probe_expression_budgets(self):
        self.collect()
        self.assert_setup_ok()
        self.assert_rc_state_not_error()
        self.assert_all_weblog_responses_ok()

        # Count all snapshot entries emitted for the span probe.
        # When a span probe's expression fails (e.g., "Cannot dereference field"),
        # error logs should be rate-limited to at most 1 per second.
        total_error_entries = 0
        for _id in self.probe_ids:
            if _id in self.probe_snapshots:
                total_error_entries += len(self.probe_snapshots[_id])

        # Verify at least one error entry was generated (probe actually fired and failed)
        assert total_error_entries >= 1, (
            "Expected at least 1 error entry to verify the span probe expression error was logged, got 0"
        )

        # Error entries should be rate-limited to at most 1 per second.
        # Allow a buffer for timing imprecision.
        max_expected = int(self.total_request_time) + 5
        assert total_error_entries <= max_expected, (
            f"Expected at most {max_expected} error entries (1/sec budget for "
            f"{self.total_request_time:.1f}s), got {total_error_entries}. "
            f"Span probe expression error logging should be rate-limited."
        )
