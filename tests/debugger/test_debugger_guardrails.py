# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import json
from typing import Any

import tests.debugger.utils as debugger
from utils import context, features, rfc, scenarios, slow, weblog


MAX_SNAPSHOT_BYTES = 1024 * 1024
# `^(a+)+$` against a non-matching input backtracks exponentially (~2^n), so a few dozen
# characters already blow past any evaluation-time budget. Keep it small so the value fits
# comfortably in the request URL.
REDOS_INPUT_LENGTH = 50
GUARDRAILS_RFC = "https://docs.google.com/document/d/1OhCH3SMuS_B4Ickays94GpqDlqKcc9b9gLos1T85F-Q/edit?usp=sharing"


@rfc(GUARDRAILS_RFC)
@features.debugger_expression_language
@scenarios.debugger_probes_snapshot
@slow
class Test_Debugger_Evaluation_Timeout(debugger.BaseDebuggerTest):
    """RFC guardrail: expensive expression evaluation must stop before normal snapshot creation.

    A conforming tracer aborts the expensive ``when`` evaluation and surfaces the failure as an
    evaluation-error snapshot (non-empty ``evaluationErrors[]`` with no captured user data),
    exactly like a runtime condition error -- it must not produce a normal, fully-captured snapshot.
    """

    def _convert_to_line_probe_if_needed(self, probe: dict[str, Any], method: str) -> None:
        if context.library.name not in ("nodejs", "ruby"):
            return

        where = probe["where"]
        where.pop("methodName", None)
        where["typeName"] = None
        where["sourceFile"] = "ACTUAL_SOURCE_FILE"
        where["lines"] = self.method_and_language_to_line_number(method, context.library.name)

    def _setup_evaluation_timeout(self, probes_name: str, method: str, request_path: str) -> None:
        self.initialize_weblog_remote_config()

        probes = debugger.read_probes(probes_name)
        for probe in probes:
            probe["id"] = debugger.generate_probe_id("log")
            self._convert_to_line_probe_if_needed(probe, method)

        self.set_probes(probes)
        self.send_rc_probes()
        if not self.wait_for_all_probes(statuses=["INSTALLED"], timeout=30):
            self.setup_failures.append("Probes did not reach INSTALLED status within 30s")

        self.weblog_responses.append(weblog.get(request_path, timeout=15))
        # A conforming tracer emits an evaluation-error snapshot; wait for it to land before
        # collect(). Tracers that (wrongly) emit nothing just hit the timeout and fail the
        # snapshot-presence assertion in the test with a clear message.
        self.wait_for_all_snapshots(timeout=10)

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
            assert snapshots, (
                "Probe emitted no snapshot; a conforming tracer must surface the aborted "
                "expression evaluation via a probe result carrying evaluationErrors[]."
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
@features.debugger_line_probe
@scenarios.debugger_probes_snapshot
@slow
class Test_Debugger_Snapshot_Guardrails(debugger.BaseDebuggerTest):
    """RFC guardrails for completed snapshot size and capture-time budget."""

    SNAPSHOT_SIZE_COLLECTION_ITEMS = 300000
    CAPTURE_TIMEOUT_COLLECTION_ITEMS = 1000000

    def _setup_snapshot_guardrail(self, probes_name: str, collection_size: int) -> None:
        self.initialize_weblog_remote_config()

        probes = debugger.read_probes(probes_name)
        for probe in probes:
            probe["id"] = debugger.generate_probe_id("log")
            if "methodName" in probe["where"]:
                del probe["where"]["methodName"]
            probe["where"]["lines"] = self.method_and_language_to_line_number("SnapshotLimits", context.library.name)
            probe["where"]["sourceFile"] = "ACTUAL_SOURCE_FILE"
            probe["where"]["typeName"] = None

        self.set_probes(probes)
        self.send_rc_probes()
        if not self.wait_for_all_probes(statuses=["INSTALLED"], timeout=30):
            self.setup_failures.append("Probes did not reach INSTALLED status within 30s")

        self.weblog_responses.append(
            weblog.get(f"/debugger/snapshot/limits?collectionSize={collection_size}", timeout=30)
        )
        if not self.wait_for_all_probes(statuses=["EMITTING"], timeout=10):
            self.setup_failures.append("Probes did not reach EMITTING status within 10s")
        if not self.wait_for_all_snapshots(timeout=30):
            self.setup_failures.append("Snapshot was not received within 30s")

    def setup_snapshot_size_cap(self) -> None:
        self._setup_snapshot_guardrail("probe_snapshot_size_cap", self.SNAPSHOT_SIZE_COLLECTION_ITEMS)

    def test_snapshot_size_cap(self) -> None:
        _, snapshot = self._get_single_snapshot()
        serialized_size = len(json.dumps(snapshot, separators=(",", ":")).encode())
        assert serialized_size <= MAX_SNAPSHOT_BYTES, (
            f"Snapshot should be trimmed to <= {MAX_SNAPSHOT_BYTES} bytes, got {serialized_size} bytes"
        )

        large_collection = self._get_captured_local(snapshot, "largeCollection")
        assert self._is_partially_captured(large_collection, self.SNAPSHOT_SIZE_COLLECTION_ITEMS), (
            "Expected the oversized snapshot to contain only part of largeCollection after trimming, "
            f"got: {large_collection!r}"
        )

    def setup_capture_timeout_reason(self) -> None:
        self._setup_snapshot_guardrail("probe_capture_timeout_reason", self.CAPTURE_TIMEOUT_COLLECTION_ITEMS)

    def test_capture_timeout_reason(self) -> None:
        _, snapshot = self._get_single_snapshot()
        reasons = set(self._iter_not_captured_reasons(snapshot))
        assert "timeout" in reasons, f"Expected notCapturedReason='timeout', got reasons: {sorted(reasons)}"
        unexpected_reasons = {"collectionSize", "stringLength", "fieldCount", "depth"} & reasons
        assert not unexpected_reasons, (
            f"Capture timeout fixture should avoid structural limit reasons, but found: {sorted(unexpected_reasons)}"
        )

    def _get_single_snapshot(self) -> tuple[dict[str, Any], dict[str, Any]]:
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
            return envelope, snapshot

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

    def _is_partially_captured(self, value: object, expected_items: int) -> bool:
        if not isinstance(value, dict):
            return False

        if value.get("notCapturedReason") == "payloadTooLarge" or value.get("pruned") is True:
            return True

        elements = value.get("elements") or value.get("entries")
        if isinstance(elements, list) and len(elements) < expected_items:
            return True

        return any(self._is_partially_captured(child, expected_items) for child in value.values())

    def _iter_not_captured_reasons(self, value: object) -> list[str]:
        if isinstance(value, dict):
            reasons = []
            reason = value.get("notCapturedReason")
            if isinstance(reason, str):
                reasons.append(reason)
            for child in value.values():
                reasons.extend(self._iter_not_captured_reasons(child))
            return reasons

        if isinstance(value, list):
            reasons = []
            for child in value:
                reasons.extend(self._iter_not_captured_reasons(child))
            return reasons

        return []
