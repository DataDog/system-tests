# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import time
import tests.debugger.utils as debugger

from utils import slow, scenarios, features, context


@features.debugger_probe_budgets
@scenarios.debugger_probes_snapshot
@slow
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

        self._rewrite_where_for_lines(probes, lines)

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

    def setup_log_line_capture_expression_budgets(self):
        self._setup(
            "probe_capture_expressions_budgets",
            "/debugger/budgets/150",
            lines=self.method_and_language_to_line_number("Budgets", self.get_tracer()["language"]),
        )

    def test_log_line_capture_expression_budgets(self):
        self._assert()
        self._validate_snapshots()

        snapshots_with_captures = 0
        for _id in self.probe_ids:
            for span in self.probe_snapshots[_id]:
                captures = span.get("debugger", {}).get("snapshot", {}).get("captures", None)
                if captures is None:
                    continue

                # Capture expressions live under captures.lines.{line}.captureExpressions for line probes.
                has_capture_expressions = any(
                    isinstance(line_data, dict) and "captureExpressions" in line_data
                    for line_data in captures.get("lines", {}).values()
                )
                if not has_capture_expressions:
                    continue

                snapshots_with_captures += 1

            # Probe budgets aren't exact and can take time to be applied, so we allow a range of 1-20 snapshots with
            # capture expressions for 150 requests, matching the 1/s snapshot limit.
            assert 1 <= snapshots_with_captures <= 20, (
                f"Expected 1-20 snapshots with capture expressions, got {snapshots_with_captures} in "
                f"{self.total_request_time} seconds"
            )

    def setup_span_probe_expression_budgets(self):
        self.initialize_weblog_remote_config()

        probes = debugger.read_probes("probe_span_line_budgets_expression")
        for probe in probes:
            probe["id"] = debugger.generate_probe_id("decor")

        # A line probe in the loop body fires 150 times within a single trace. Sending 150 requests instead
        # would lower the agent sampling rate and drop traces of the following span decoration tests.
        self._rewrite_where_for_lines(
            probes, self.method_and_language_to_line_number("Budgets", self.get_tracer()["language"])
        )

        self.set_probes(probes)
        self.send_rc_probes()
        self.wait_for_all_probes(statuses=["INSTALLED"])

        start_time = time.time()
        self.send_weblog_request("/debugger/budgets/150")
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
        # Java's adaptive sampler starts with a budget of 17, allowing an initial burst on top of the 1/s rate.
        buffer = 20 if context.library == "java" else 5
        max_expected = int(self.total_request_time) + buffer
        assert total_error_entries <= max_expected, (
            f"Expected at most {max_expected} error entries (1/sec budget for "
            f"{self.total_request_time:.1f}s), got {total_error_entries}. "
            f"Span probe expression error logging should be rate-limited."
        )

    def setup_per_trace_budget(self):
        self.initialize_weblog_remote_config()

        language = self.get_tracer()["language"]

        probes = []
        for method in ("CorrelationLoopBody", "CorrelationLoopSibling"):
            probe = debugger.read_probes("probe_snapshot_log_correlation_loop")[0]
            probe["id"] = debugger.generate_probe_id("log")
            self._rewrite_where_for_lines([probe], self.method_and_language_to_line_number(method, language))
            probes.append(probe)

        self.set_probes(probes)
        self.send_rc_probes()
        self.wait_for_all_probes(statuses=["INSTALLED"])

        # The loop sleeps one second per iteration, so a time-based budget would emit more than one
        # snapshot while a trace-scoped budget emits exactly one.
        self.send_weblog_request("/debugger/correlation/loop/3")

        self.wait_for_all_probes(statuses=["EMITTING"])
        self.wait_for_all_snapshots()

    def test_per_trace_budget(self):
        """A probe in a loop emits one snapshot per trace and does not starve a sibling probe."""
        self._assert()

        # A single request is a single trace, so every probe must have emitted exactly once.
        for probe_id in self.probe_ids:
            count = len(self.probe_snapshots.get(probe_id, []))
            assert count == 1, f"probe {probe_id} emitted {count} snapshots in one trace, expected exactly 1"
