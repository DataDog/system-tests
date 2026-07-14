# Unless explicitly stated otherwise all files in this repository are licensed under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from typing import Any

import tests.debugger.utils as debugger
from utils import context, features, rfc, scenarios, slow, weblog


MAX_SNAPSHOT_BYTES = 1024 * 1024
# `^(a+)+$` against a non-matching input backtracks exponentially (~2^n), so a few dozen
# characters already blow past any evaluation-time budget. Keep it small so the value fits
# comfortably in the request URL.
REDOS_INPUT_LENGTH = 25
GUARDRAILS_RFC = "https://docs.google.com/document/d/1OhCH3SMuS_B4Ickays94GpqDlqKcc9b9gLos1T85F-Q/edit?usp=sharing"


class _DebuggerEvaluationTimeoutTest(debugger.BaseDebuggerTest):
    """RFC guardrail: expensive expression evaluation must stop before normal snapshot creation.

    A conforming tracer aborts the expensive ``when`` evaluation and surfaces the failure as an
    evaluation-error snapshot (non-empty ``evaluationErrors[]`` with no captured user data),
    exactly like a runtime condition error -- it must not produce a normal, fully-captured snapshot.
    """

    def _prepare_probe(self, _probe: dict[str, Any], _method: str) -> None:
        pass

    def _setup_evaluation_timeout(self, probes_name: str, method: str, request_path: str) -> None:
        self.initialize_weblog_remote_config()

        probes = debugger.read_probes(probes_name)
        for probe in probes:
            probe["id"] = debugger.generate_probe_id("log")
            self._prepare_probe(probe, method)

        self.set_probes(probes)
        self.send_rc_probes()
        if not self.wait_for_all_probes(statuses=["INSTALLED"], timeout=30):
            self.setup_failures.append("Probes did not reach INSTALLED status within 30s")

        self.weblog_responses = [weblog.get(request_path, timeout=15)]
        # A conforming tracer emits an evaluation-error snapshot; wait for it to land before
        # collect(). Tracers that (wrongly) emit nothing just hit the timeout and fail the
        # snapshot-presence assertion in the test with a clear message.
        if self.wait_for_all_snapshots(timeout=10):
            # One hit must emit one error snapshot. Keep watching so a delayed duplicate or
            # normal snapshot cannot arrive after collect() and produce a false pass.
            self.wait_for_additional_snapshots(timeout=5)

    def setup_evaluation_timeout_regex(self) -> None:
        self._setup_evaluation_timeout(
            "probe_evaluation_timeout_regex",
            "StringOperations",
            f"/debugger/expression/strings?strValue={'a' * REDOS_INPUT_LENGTH}!",
        )

    def test_evaluation_timeout_regex(self) -> None:
        self._assert_evaluation_timeout_snapshot()

    def setup_evaluation_timeout_collection_filter(self) -> None:
        self._setup_evaluation_timeout(
            "probe_evaluation_timeout_collection_filter",
            "SnapshotLimits",
            "/debugger/snapshot/limits?collectionSize=100000",
        )

    def test_evaluation_timeout_collection_filter(self) -> None:
        self._assert_evaluation_timeout_snapshot()

    def _assert_evaluation_timeout_snapshot(self) -> None:
        self.collect()
        self.assert_setup_ok()
        self.assert_rc_state_not_error()
        self.assert_all_weblog_responses_ok()

        for probe_id in self.probe_ids:
            snapshots = self.probe_snapshots.get(probe_id, [])
            assert len(snapshots) == 1, (
                f"Expected exactly one evaluation-timeout snapshot for {probe_id}, got {len(snapshots)}; "
                "a conforming tracer must surface only the aborted evaluation result."
            )

            envelope = snapshots[0]
            snapshot = envelope.get("debugger", {}).get("snapshot") or envelope.get("debugger.snapshot") or {}

            evaluation_errors = snapshot.get("evaluationErrors") or []
            assert evaluation_errors, (
                "Evaluation-timeout snapshot has an empty evaluationErrors[]; the tracer must "
                "report that expression evaluation was aborted."
            )

            captures = snapshot.get("captures")
            assert not debugger.captures_contain_data(captures), (
                f"Evaluation-timeout snapshot leaked captured data ({captures!r}); a conforming "
                "tracer must stop before normal snapshot creation."
            )


@rfc(GUARDRAILS_RFC)
@features.debugger_expression_language
@scenarios.debugger_probes_snapshot
@slow
class Test_Debugger_Evaluation_Timeout_Method_Probe(_DebuggerEvaluationTimeoutTest):
    pass


@rfc(GUARDRAILS_RFC)
@features.debugger_expression_language
@scenarios.debugger_probes_snapshot
@slow
class Test_Debugger_Evaluation_Timeout_Line_Probe(_DebuggerEvaluationTimeoutTest):
    def _prepare_probe(self, probe: dict[str, Any], method: str) -> None:
        where = probe["where"]
        where.pop("methodName", None)
        where["typeName"] = None
        where["sourceFile"] = "ACTUAL_SOURCE_FILE"
        where["lines"] = self.method_and_language_to_line_number(method, context.library.name)


class _DebuggerSnapshotGuardrailTest(debugger.BaseDebuggerTest):
    def _setup_snapshot_guardrail(self, probes_name: str, request_path: str, line_mapping: str) -> None:
        self.initialize_weblog_remote_config()

        probes = debugger.read_probes(probes_name)
        for probe in probes:
            probe["id"] = debugger.generate_probe_id("log")
            if "methodName" in probe["where"]:
                del probe["where"]["methodName"]
            probe["where"]["lines"] = self.method_and_language_to_line_number(line_mapping, context.library.name)
            probe["where"]["sourceFile"] = "ACTUAL_SOURCE_FILE"
            probe["where"]["typeName"] = None

        self.set_probes(probes)
        self.send_rc_probes()
        if not self.wait_for_all_probes(statuses=["INSTALLED"], timeout=30):
            self.setup_failures.append("Probes did not reach INSTALLED status within 30s")

        self.weblog_responses = [weblog.get(request_path, timeout=30)]
        if not self.wait_for_all_probes(statuses=["EMITTING"], timeout=10):
            self.setup_failures.append("Probes did not reach EMITTING status within 10s")
        if not self.wait_for_all_snapshots(timeout=30):
            self.setup_failures.append("Snapshot was not received within 30s")

    def _get_single_snapshot(self) -> tuple[str, dict[str, Any]]:
        self.collect()
        self.assert_setup_ok()
        self.assert_rc_state_not_error()
        self.assert_all_probes_are_emitting()
        self.assert_all_weblog_responses_ok()

        for probe_id in self.probe_ids:
            snapshots = self.probe_snapshots.get(probe_id, [])
            assert len(snapshots) == 1, f"Expected exactly 1 snapshot for {probe_id}, got {len(snapshots)}"
            envelope = snapshots[0]
            snapshot = envelope.get("debugger", {}).get("snapshot") or envelope.get("debugger.snapshot")
            assert isinstance(snapshot, dict), f"Snapshot data not found in expected format for {probe_id}"
            return probe_id, snapshot

        raise AssertionError("No probe IDs were registered")

    def _get_captured_local(self, snapshot: dict[str, Any], variable_name: str) -> dict[str, Any]:
        captures = snapshot.get("captures", {})
        lines = captures.get("lines", {})
        assert isinstance(lines, dict), f"Expected line captures to be a dict, got: {lines!r}"
        assert len(lines) == 1, f"Expected one line capture, got: {lines!r}"

        line_data = next(iter(lines.values()))
        locals_data = line_data.get("locals", {})
        assert variable_name in locals_data, f"{variable_name!r} is missing from snapshot locals"
        value = locals_data[variable_name]
        assert isinstance(value, dict), f"Expected {variable_name!r} to be a captured object, got: {value!r}"
        return value

    def _contains_payload_pruning(self, value: object) -> bool:
        if isinstance(value, dict):
            if value.get("notCapturedReason") == "payloadTooLarge" or value.get("pruned") is True:
                return True
            return any(self._contains_payload_pruning(child) for child in value.values())

        if isinstance(value, list):
            return any(self._contains_payload_pruning(child) for child in value)

        return False

    def _contains_not_captured_reason(self, value: object, reason: str) -> bool:
        if isinstance(value, dict):
            if value.get("notCapturedReason") == reason:
                return True
            return any(self._contains_not_captured_reason(child, reason) for child in value.values())

        if isinstance(value, list):
            return any(self._contains_not_captured_reason(child, reason) for child in value)

        return False


@rfc(GUARDRAILS_RFC)
@features.debugger_line_probe
@scenarios.debugger_probes_snapshot
@slow
class Test_Debugger_Snapshot_Size_Guardrail(_DebuggerSnapshotGuardrailTest):
    """RFC guardrail for the completed snapshot size."""

    # Before enabling, verify this exceeds 1 MB without timing out; otherwise use a dedicated scenario or remove it.
    SNAPSHOT_SIZE_COLLECTION_ITEMS = 20_000
    SNAPSHOT_SIZE_STRING_LENGTH = 1_000_000

    def setup_snapshot_size_cap(self) -> None:
        self._setup_snapshot_guardrail(
            "probe_snapshot_size_cap",
            (
                f"/debugger/snapshot/limits?collectionSize={self.SNAPSHOT_SIZE_COLLECTION_ITEMS}"
                f"&stringLength={self.SNAPSHOT_SIZE_STRING_LENGTH}"
            ),
            "SnapshotLimits",
        )

    def test_snapshot_size_cap(self) -> None:
        probe_id, snapshot = self._get_single_snapshot()
        request_lengths = self.get_snapshot_request_lengths(probe_id)
        assert request_lengths, f"No backend request containing a snapshot was found for {probe_id}"
        oversized_requests = [length for length in request_lengths if length > MAX_SNAPSHOT_BYTES]
        assert not oversized_requests, (
            f"Snapshot backend requests should be <= {MAX_SNAPSHOT_BYTES} bytes, got {request_lengths!r}"
        )

        captures = snapshot.get("captures", {})
        assert self._contains_payload_pruning(captures), (
            f"Expected the oversized snapshot to contain a payload-size pruning marker, got: {captures!r}"
        )


@rfc(GUARDRAILS_RFC)
@features.debugger_line_probe
@scenarios.debugger_capture_timeout
@slow
class Test_Debugger_Capture_Timeout_Guardrail(_DebuggerSnapshotGuardrailTest):
    """RFC guardrail for reporting an incomplete capture caused by its time budget."""

    # Node.js skips collections with 500 or more elements before applying the capture deadline.
    # Keep the collection below that guardrail while making each item expensive to traverse.
    CAPTURE_TIMEOUT_COLLECTION_ITEMS = 499
    CAPTURE_TIMEOUT_NESTING_DEPTH = 8

    def setup_capture_timeout_reports_reason(self) -> None:
        self._setup_snapshot_guardrail(
            "probe_capture_timeout_reason",
            (
                "/debugger/snapshot/capture-timeout"
                f"?collectionSize={self.CAPTURE_TIMEOUT_COLLECTION_ITEMS}"
                f"&nestingDepth={self.CAPTURE_TIMEOUT_NESTING_DEPTH}"
            ),
            "CaptureTimeout",
        )

    def test_capture_timeout_reports_reason(self) -> None:
        """A capture exceeding the tracer's time budget identifies the value it could not finish.

        The dedicated scenario uses a deliberately small tracer budget (10 ms), and the fixture keeps
        only the target collection as a complex value. We do not compare elapsed time, and the
        assertion rejects completed-snapshot payload pruning as a different guardrail.
        """
        _, snapshot = self._get_single_snapshot()
        large_collection = self._get_captured_local(snapshot, "largeCollection")
        assert not self._contains_payload_pruning(large_collection), (
            "Capture-timeout fixture triggered completed-snapshot payload pruning on largeCollection"
        )
        assert self._contains_not_captured_reason(large_collection, "timeout"), (
            "largeCollection should contain notCapturedReason='timeout' when capture exceeds the tracer's "
            f"time budget, got: {large_collection!r}"
        )
