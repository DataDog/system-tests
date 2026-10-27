# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Compliance tests: a metric probe whose value expression fails must not fail silently."""

import tests.debugger.utils as debugger
from utils import features, scenarios


@features.debugger_expression_language
@scenarios.debugger_probes_snapshot
class Test_Debugger_Metric_Value_Error(debugger.BaseDebuggerTest):
    """Compliance: a broken metric value expression must surface as an ERROR status or an evaluation error."""

    def setup_metric_value_error_is_reported(self) -> None:
        self.initialize_weblog_remote_config()

        probes = debugger.read_probes("probe_metric_value_error")
        for probe in probes:
            probe["id"] = debugger.generate_probe_id("metric")

        self.set_probes(probes)
        self.send_rc_probes()
        self.wait_for_all_probes(statuses=["INSTALLED", "ERROR"], timeout=30)
        self.send_weblog_request("/debugger/metric/1")
        self.wait_for_all_snapshots(timeout=10)

    def test_metric_value_error_is_reported(self) -> None:
        """The value references the unbound variable ``definitelyDoesNotExist``, so no metric point can ever be produced.

        A conforming tracer either rejects the probe (status=ERROR) or keeps it installed and emits a probe
        result whose ``evaluationErrors[]`` names the failing variable.
        """
        self.collect()
        self.assert_setup_ok()

        for probe_id in self.probe_ids:
            diag = self.probe_diagnostics.get(probe_id)
            assert diag is not None, "The probe did not receive any diagnostic."
            if diag["status"] == "ERROR":
                continue

            evaluation_errors: list[dict] = []
            for envelope in self.probe_snapshots.get(probe_id, []):
                snap = envelope.get("debugger", {}).get("snapshot") or envelope.get("debugger.snapshot") or {}
                evaluation_errors.extend(snap.get("evaluationErrors") or [])

            assert any(
                "definitelyDoesNotExist" in str(entry.get("expr", ""))
                or "definitelyDoesNotExist" in str(entry.get("message", ""))
                for entry in evaluation_errors
            ), (
                f"The probe reached status {diag['status']!r} and reported no evaluation error naming "
                f"'definitelyDoesNotExist' (errors: {evaluation_errors!r}). The metric can never emit a point, "
                f"so the failure must be visible to the user."
            )
