# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from typing import Any

import tests.debugger.utils as debugger
from utils import context, features, scenarios, weblog


@features.debugger_expression_language
@scenarios.debugger_probes_snapshot
class Test_Debugger_Evaluation_Timeout(debugger.BaseDebuggerTest):
    """RFC guardrail: expensive expression evaluation must stop before normal snapshot creation."""

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
        if not self.wait_for_all_probes(statuses=["EMITTING"], timeout=5):
            self.setup_failures.append("Probes did not reach EMITTING status within 5s")

        # A conforming tracer skips the event, so waiting should time out. A non-conforming
        # tracer that evaluates the expression fully will emit a snapshot and fail below.
        self.wait_for_all_snapshots(timeout=3)
        time.sleep(2)

    def setup_evaluation_timeout_regex(self) -> None:
        self._setup_evaluation_timeout(
            "probe_evaluation_timeout_regex",
            "StringOperations",
            f"/debugger/expression/strings?strValue={'a' * 30000}!",
        )

    def test_evaluation_timeout_regex(self) -> None:
        self._assert_no_normal_snapshot()

    def setup_evaluation_timeout_collection_filter(self) -> None:
        self._setup_evaluation_timeout(
            "probe_evaluation_timeout_collection_filter",
            "SnapshotLimits",
            "/debugger/snapshot/limits?collectionSize=100000",
        )

    def test_evaluation_timeout_collection_filter(self) -> None:
        self._assert_no_normal_snapshot()

    def _assert_no_normal_snapshot(self) -> None:
        self.collect()
        self.assert_setup_ok()
        self.assert_rc_state_not_error()
        self.assert_all_weblog_responses_ok()

        for probe_id in self.probe_ids:
            snapshots = self.probe_snapshots.get(probe_id, [])
            assert not snapshots, (
                f"Probe emitted {len(snapshots)} snapshot(s) after evaluation timeout. "
                "A conforming tracer must skip event creation when expression evaluation exceeds 1 second."
            )
