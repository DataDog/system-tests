# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Go expression errors that the system-probe can detect, because Go types are fixed at compile time."""

import tests.debugger.utils as debugger
from utils import context, features, irrelevant, scenarios


class _GoExpressionTestBase(debugger.BaseDebuggerTest):
    def _setup_probes(self, probes_name: str, install_statuses: list[debugger.ProbeStatus]) -> None:
        self.initialize_weblog_remote_config()

        probes = debugger.read_probes(probes_name)
        for probe in probes:
            probe["id"] = debugger.generate_probe_id("log")

        self.set_probes(probes)
        self.send_rc_probes()
        self.wait_for_all_probes(statuses=install_statuses, timeout=30)
        self.send_weblog_request("/debugger/expression?inputValue=asd")
        self.wait_for_all_snapshots(timeout=10)


@features.debugger_expression_language
@scenarios.debugger_probes_snapshot
@irrelevant(context.library != "golang", reason="Only Go checks expression types at install time")
class Test_Debugger_Go_Static_Template_Error(_GoExpressionTestBase):
    """A template the system-probe already knows can never evaluate must be rejected, like the same condition is."""

    def setup_static_template_error_probe_rejected(self) -> None:
        self._setup_probes("probe_static_template_error", ["INSTALLED", "ERROR"])

    def test_static_template_error_probe_rejected(self) -> None:
        """Each template references something the system-probe resolves at install time and can't find.

        A member access on a ``map[string]int``, an unknown variable, and a missing struct field are all
        rejected with an ERROR diagnostic when used in a ``when`` condition. In a log template they must also
        reach status=ERROR, not stay installed and print the error inline.
        """
        self.collect()
        self.assert_setup_ok()

        for probe_id in self.probe_ids:
            diag = self.probe_diagnostics.get(probe_id)
            assert diag is not None, "The probe did not receive any diagnostic."
            assert diag["status"] == "ERROR", (
                f"Probe reached status {diag['status']!r}; its template can never evaluate, so it must be "
                f"rejected with status=ERROR like the equivalent condition."
            )


@features.debugger_expression_language
@scenarios.debugger_probes_snapshot
@irrelevant(context.library != "golang", reason="Go-specific repro for map index conditions")
class Test_Debugger_Go_Missing_Map_Key_Condition(_GoExpressionTestBase):
    """A condition on a key that isn't in the map must not fire."""

    def setup_missing_map_key_condition_does_not_fire(self) -> None:
        self._setup_probes("probe_missing_map_key_condition", ["INSTALLED"])

    def test_missing_map_key_condition_does_not_fire(self) -> None:
        """``testStruct.Dictionary['nope'] == 1``: in Go a missing key reads as 0, so the condition is false.

        A conforming tracer emits nothing, or an error-only snapshot without captured data.
        """
        self.collect()
        self.assert_setup_ok()

        for probe_id in self.probe_ids:
            for envelope in self.probe_snapshots.get(probe_id, []):
                snap = envelope.get("debugger", {}).get("snapshot") or envelope.get("debugger.snapshot") or {}
                assert not debugger.captures_contain_data(snap.get("captures")), (
                    "The probe emitted a snapshot with captured data, so the condition fired as if true. "
                    "A missing key in a map[string]int reads as 0, and 0 == 1 is false."
                )
