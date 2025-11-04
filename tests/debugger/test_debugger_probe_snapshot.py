# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import time
import tests.debugger.utils as debugger


from utils import scenarios, features, missing_feature, context, irrelevant, bug, logger
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
@bug(context.library == "golang" and context.agent_version >= "7.73.0-rc.0", reason="DEBUG-4676", force_skip=True)
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
@bug(context.library == "golang" and context.agent_version >= "7.73.0-rc.0", reason="DEBUG-4676", force_skip=True)
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

    # Default snapshot capture limits
    DEFAULT_MAX_REFERENCE_DEPTH = 3
    DEFAULT_MAX_COLLECTION_SIZE = 100
    DEFAULT_MAX_FIELD_COUNT = 20
    DEFAULT_MAX_LENGTH = 255

    ### log probe ###
    def setup_log_line_snapshot(self):
        self._setup("probe_snapshot_log_line", "/debugger/log", "log", lines=None)

    @bug(context.library == "nodejs", reason="DEBUG-4611")
    def test_log_line_snapshot(self):
        self._assert()
        self._validate_snapshots()

    def setup_default_max_reference_depth(self):
        """Setup test for default maxReferenceDepth"""
        self._setup_default_capture_limits()

    def setup_default_max_field_count(self):
        """Setup test for default maxFieldCount"""
        self._setup_default_capture_limits()

    def setup_default_max_collection_size(self):
        """Setup test for default maxCollectionSize"""
        self._setup_default_capture_limits()

    def setup_default_max_length(self):
        """Setup test for default maxLength"""
        self._setup_default_capture_limits()

    def _setup_default_capture_limits(self):
        """Shared setup method for default capture limit tests"""
        test_depth = self.DEFAULT_MAX_REFERENCE_DEPTH + 7
        test_fields = self.DEFAULT_MAX_FIELD_COUNT + 30
        test_collection_size = self.DEFAULT_MAX_COLLECTION_SIZE + 100
        test_string_length = self.DEFAULT_MAX_LENGTH + 1000

        # Get the line number dynamically based on the language
        lines = self.method_and_language_to_line_number("SnapshotLimits", context.library.name)

        self._setup(
            "probe_snapshot_default_capture_limits",
            f"/debugger/snapshot/limits?"
            f"depth={test_depth}&"
            f"fields={test_fields}&"
            f"collectionSize={test_collection_size}&"
            f"stringLength={test_string_length}",
            "log",
            lines=lines,
        )

    def _get_snapshot_locals_variable(self, variable_name: str) -> dict:
        """Helper method to extract a specific local variable from snapshot for default capture limit tests"""
        self._assert()
        self._validate_snapshots()

        for probe_id in self.probe_ids:
            if probe_id not in self.probe_snapshots:
                raise ValueError(f"Snapshot {probe_id} was not received.")

            snapshots = self.probe_snapshots[probe_id]
            if not snapshots:
                raise ValueError(f"No snapshots found for probe {probe_id}")

            if len(snapshots) > 1:
                raise ValueError(f"Expected 1 snapshot, got {len(snapshots)} for probe {probe_id}")

            snapshot = snapshots[0]
            debugger_snapshot = snapshot.get("debugger", {}).get("snapshot") or snapshot.get("debugger.snapshot")

            if not debugger_snapshot:
                raise ValueError(f"Snapshot data not found in expected format for probe {probe_id}")
            if "captures" not in debugger_snapshot:
                raise ValueError(f"No captures found in snapshot for probe {probe_id}")

            captures = debugger_snapshot["captures"]
            if "lines" in captures:
                lines = captures["lines"]
                if isinstance(lines, dict) and len(lines) == 1:
                    line_key = next(iter(lines))
                    line_data = lines[line_key]
                else:
                    raise ValueError(f"Expected 'lines' to be a dict with a single key, got: {len(lines)}")

                if line_data and "locals" in line_data:
                    locals_data = line_data["locals"]
                    assert variable_name in locals_data, f"'{variable_name}' is missing from snapshot locals"
                    return locals_data[variable_name]

        raise ValueError("No locals data found in snapshot")

    def _measure_captured_depth(self, obj: dict, current_depth: int = 1) -> int:
        """Measure the actual depth captured before truncation (notCapturedReason='depth')"""
        fields = obj["fields"]
        assert isinstance(fields, dict), f"Expected 'fields' to be a dict, got: {type(fields)}"
        expected_nested_key = "@nested" if context.library.name == "ruby" else "nested"
        assert (
            expected_nested_key in fields
        ), f"Expected '{expected_nested_key}' to be present in the 'fields' object, got: {list(fields.keys())}"
        nested = fields[expected_nested_key]
        assert isinstance(nested, dict), f"Expected '{expected_nested_key}' to be a dict, got: {type(nested)}"

        if "notCapturedReason" in nested:
            assert (
                nested["notCapturedReason"] == "depth"
            ), f"Expected notCapturedReason to be 'depth', got: {nested['notCapturedReason']}"
            return current_depth

        return self._measure_captured_depth(nested, current_depth + 1)

    @bug(context.library.name == "nodejs", reason="DEBUG-4611")  # Correct default works (fails if no root capture obj)
    @bug(context.library.name == "ruby", reason="DEBUG-4675")  # Ruby has off-by-one bug: captures 4 levels instead of 3
    def test_default_max_reference_depth(self):
        """Test that the tracer uses default maxReferenceDepth=3 when capture property is omitted"""
        deep_object = self._get_snapshot_locals_variable("deepObject")
        actual_depth = self._measure_captured_depth(deep_object)
        assert (
            actual_depth == self.DEFAULT_MAX_REFERENCE_DEPTH
        ), f"deepObject should have been captured with {self.DEFAULT_MAX_REFERENCE_DEPTH} levels, got: {actual_depth}"

    @bug(context.library.name == "nodejs", reason="DEBUG-4611")  # Correct default works (fails if no root capture obj)
    def test_default_max_field_count(self):
        """Test that the tracer uses default maxFieldCount=20 when capture property is omitted"""
        many_fields = self._get_snapshot_locals_variable("manyFields")
        assert (
            many_fields.get("notCapturedReason") == "fieldCount"
        ), f"manyFields should have notCapturedReason='fieldCount', got: {many_fields.get('notCapturedReason')}"

        captured_count = len(many_fields["fields"])
        assert (
            captured_count == self.DEFAULT_MAX_FIELD_COUNT
        ), f"manyFields should have exactly {self.DEFAULT_MAX_FIELD_COUNT} fields captured, got: {captured_count}"

    @bug(context.library.name == "nodejs", reason="DEBUG-4611")  # Correct default works (fails if no root capture obj)
    def test_default_max_collection_size(self):
        """Test that the tracer uses default maxCollectionSize=100 when capture property is omitted"""
        large_collection = self._get_snapshot_locals_variable("largeCollection")
        assert (
            large_collection.get("notCapturedReason") == "collectionSize"
        ), f"largeCollection should have notCapturedReason='collectionSize', got: {large_collection.get('notCapturedReason')}"

        actual_size = large_collection.get("size")
        if isinstance(actual_size, str) and context.library.name == "java":
            # TODO: Remove special handling for Java once JIRA ticket DEBUG-4671 is closed
            logger.warning("size property is a string! Expected an int")
            actual_size = int(actual_size)
        expected_collection_size = self.DEFAULT_MAX_COLLECTION_SIZE + 100
        assert (
            actual_size == expected_collection_size
        ), f"largeCollection should report size={expected_collection_size}, got: {actual_size}"

        captured_count = len(large_collection["elements"])
        assert (
            captured_count == self.DEFAULT_MAX_COLLECTION_SIZE
        ), f"largeCollection should have exactly {self.DEFAULT_MAX_COLLECTION_SIZE} elements, got: {captured_count}"

    @bug(context.library.name == "nodejs", reason="DEBUG-4611")  # Correct default works (fails if no root capture obj)
    @bug(context.library.name == "dotnet", reason="DEBUG-4669")  # .NET uses a different default maxLength: 1000
    def test_default_max_length(self):
        """Test that the tracer uses default maxLength=255 when capture property is omitted"""
        long_string = self._get_snapshot_locals_variable("longString")
        string_value = long_string["value"]
        assert (
            len(string_value) <= self.DEFAULT_MAX_LENGTH
        ), f"longString should have length {self.DEFAULT_MAX_LENGTH}, got: {len(string_value)}"

    def setup_log_line_snapshot_debug_track(self):
        self.use_debugger_endpoint = True
        self._setup("probe_snapshot_log_line", "/debugger/log", "log", lines=None)

    @missing_feature(context.library == "ruby", reason="DEBUG-4343")
    @missing_feature(context.library == "nodejs", reason="DEBUG-4345")
    @missing_feature(
        context.library < "python@3.15.0", reason="Python 3.15.0 introduced the track change", force_skip=True
    )
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
    @missing_feature(
        context.library < "python@3.15.0", reason="Python 3.15.0 introduced the track change", force_skip=True
    )
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
