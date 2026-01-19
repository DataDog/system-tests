# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import time
import tests.debugger.utils as debugger

from utils import scenarios, features, missing_feature, context


class BaseDebuggerCaptureExpressionsTest(debugger.BaseDebuggerTest):
    """Base class with common methods for capture expressions tests"""

    def _setup(
        self,
        probes_name: str,
        request_path: str,
        probe_type: str,
        lines: list[str] | None = None,
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

    def _validate_capture_expressions(self, expected_captures: dict[str, dict]):
        """Validate that capture expressions are present in snapshots.

        Args:
            expected_captures: Dict mapping probe IDs to expected captured expression names and their validation functions
                              Example: {"probe_id": {"intValue": lambda v: v == 1, "stringValue": lambda v: v == "test"}}

        """
        for probe_id in self.probe_ids:
            if probe_id not in self.probe_snapshots:
                raise ValueError(f"Snapshot for probe {probe_id} was not received.")

            snapshots = self.probe_snapshots[probe_id]
            if not snapshots:
                raise ValueError(f"No snapshots found for probe {probe_id}")

            for snapshot in snapshots:
                if "debugger" not in snapshot:
                    raise ValueError(f"Snapshot for probe {probe_id} does not contain 'debugger' field")

                debugger_data = snapshot["debugger"]
                if "snapshot" not in debugger_data:
                    raise ValueError(f"Snapshot for probe {probe_id} does not contain 'snapshot' field")

                snapshot_data = debugger_data["snapshot"]

                # Validate that captureSnapshot is false or not present
                if snapshot_data.get("captureSnapshot", False):
                    raise ValueError(f"Probe {probe_id} should have captureSnapshot=false but it's true")

                # Check if captures field exists
                if "captures" not in snapshot_data:
                    raise ValueError(f"Snapshot for probe {probe_id} does not contain 'captures' field")

                captures = snapshot_data["captures"]

                # For capture expressions, they are nested in:
                # - captures.return.captureExpressions (for method exit probes)
                # - captures.entry.captureExpressions (for method entry probes)
                # - captures.lines.{line_number}.captureExpressions (for line probes)
                capture_expressions = None
                if "return" in captures and "captureExpressions" in captures["return"]:
                    capture_expressions = captures["return"]["captureExpressions"]
                elif "entry" in captures and "captureExpressions" in captures["entry"]:
                    capture_expressions = captures["entry"]["captureExpressions"]
                elif "lines" in captures:
                    # For line probes, check all line numbers for captureExpressions
                    for line_data in captures["lines"].values():
                        if isinstance(line_data, dict) and "captureExpressions" in line_data:
                            capture_expressions = line_data["captureExpressions"]
                            break

                if capture_expressions is None:
                    raise ValueError(
                        f"Snapshot for probe {probe_id} does not contain 'captureExpressions' "
                        f"in captures.return, captures.entry, or captures.lines"
                    )

                # Validate expected captures
                if probe_id in expected_captures:
                    for capture_name, validator in expected_captures[probe_id].items():
                        if capture_name not in capture_expressions:
                            available_captures = list(capture_expressions.keys())
                            raise ValueError(
                                f"Capture expression '{capture_name}' not found in probe {probe_id}. "
                                f"Available captures: {available_captures}"
                            )

                        captured_value = capture_expressions[capture_name]
                        if not validator(captured_value):
                            raise ValueError(
                                f"Validation failed for capture expression '{capture_name}' "
                                f"in probe {probe_id}. Value: {captured_value}"
                            )


@features.debugger_method_probe
@scenarios.debugger_probes_snapshot
@missing_feature(context.library == "php", reason="Not yet implemented", force_skip=True)
@missing_feature(context.library == "nodejs", reason="Not yet implemented", force_skip=True)
@missing_feature(context.library == "golang", reason="Not yet implemented", force_skip=True)
@missing_feature(context.library == "dotnet", reason="Not yet implemented", force_skip=True)
@missing_feature(context.library == "python", reason="Not yet implemented", force_skip=True)
@missing_feature(context.library <= "java@1.54.0", reason="Not yet implemented", force_skip=True)
class Test_Debugger_Method_Capture_Expressions(BaseDebuggerCaptureExpressionsTest):
    """Tests for method-level probe capture expressions"""

    ### log probe with capture expressions ###
    def setup_log_method_capture_expressions(self):
        self._setup("probe_capture_expressions_method", "/debugger/expression?inputValue=testValue", "log", lines=None)

    def test_log_method_capture_expressions(self):
        self._assert()

        # Build expected captures with validation functions
        expected_captures = {}
        for probe_id in self.probe_ids:
            expected_captures[probe_id] = {
                "inputValue": lambda v: isinstance(v, dict) and "type" in v and "value" in v,
                "localValue": lambda v: isinstance(v, dict) and "type" in v and "value" in v,
                "testStruct": lambda v: isinstance(v, dict) and "type" in v,
            }

        self._validate_capture_expressions(expected_captures)

    ### complex capture expressions ###
    def setup_complex_capture_expressions(self):
        self._setup("probe_capture_expressions_complex", "/debugger/expression?inputValue=testValue", "log", lines=None)

    @missing_feature(context.library == "dotnet", reason="Not yet implemented", force_skip=True)
    def test_complex_capture_expressions(self):
        self._assert()

        # Build expected captures with validation functions
        expected_captures = {}
        for probe_id in self.probe_ids:
            expected_captures[probe_id] = {
                "collection_first_element": lambda v: isinstance(v, dict) and "type" in v,
                "dictionary_value": lambda v: isinstance(v, dict) and "type" in v,
                "nested_field": lambda v: isinstance(v, dict) and "type" in v,
            }

        self._validate_capture_expressions(expected_captures)


@features.debugger_line_probe
@scenarios.debugger_probes_snapshot
@missing_feature(context.library == "php", reason="Not yet implemented", force_skip=True)
@missing_feature(context.library == "nodejs", reason="Not yet implemented", force_skip=True)
@missing_feature(context.library == "golang", reason="Not yet implemented", force_skip=True)
@missing_feature(context.library == "dotnet", reason="Not yet implemented", force_skip=True)
@missing_feature(context.library == "python", reason="Not yet implemented", force_skip=True)
@missing_feature(context.library < "java@1.59.0", reason="DEBUG-4929", force_skip=True)
class Test_Debugger_Line_Capture_Expressions(BaseDebuggerCaptureExpressionsTest):
    """Tests for line-level probe capture expressions"""

    ### log probe with capture expressions ###
    def setup_log_line_capture_expressions(self):
        self._setup("probe_capture_expressions_line", "/debugger/expression?inputValue=testValue", "log", lines=None)

    def test_log_line_capture_expressions(self):
        self._assert()

        # Build expected captures with validation functions
        expected_captures = {}
        for probe_id in self.probe_ids:
            expected_captures[probe_id] = {
                "inputValue": lambda v: isinstance(v, dict) and "type" in v and "value" in v,
                "localValue": lambda v: isinstance(v, dict) and "type" in v and "value" in v,
                "testStruct": lambda v: isinstance(v, dict) and "type" in v,
            }

        self._validate_capture_expressions(expected_captures)
