import time

import tests.debugger.utils as debugger
from utils import context, features, scenarios


class _CaptureExpressionsErrorTestBase(debugger.BaseDebuggerTest):
    """Shared base for capture-expression-error compliance tests."""

    def _convert_to_line_probe_if_needed(self, probe: dict) -> None:
        if context.library.name != "nodejs":
            return
        where = probe["where"]
        where.pop("methodName", None)
        where["typeName"] = None
        where["sourceFile"] = "ACTUAL_SOURCE_FILE"
        where["lines"] = self.method_and_language_to_line_number("LogProbe", "nodejs")

    def _assert_probes_installed(self) -> None:
        for probe_id in self.probe_ids:
            assert probe_id in self.probe_diagnostics, "Expected a diagnostic for the probe, but none was received."
            status = self.probe_diagnostics[probe_id]["status"]
            assert status in ("INSTALLED", "EMITTING"), (
                f"Expected the probe to reach INSTALLED/EMITTING status, got {status!r}."
            )


@features.debugger_expression_language
@scenarios.debugger_probes_snapshot
class Test_Debugger_Filter_Rejected_Capture_Expression_Error(_CaptureExpressionsErrorTestBase):
    """On filter-rejected hits, broken ``captureExpressions`` must not produce a flood of error events."""

    def _setup_filter_rejected(self, request_count: int, spacing_s: float) -> None:
        self.initialize_weblog_remote_config()

        probes = debugger.read_probes("probe_capture_expressions_filter_rejected")
        for probe in probes:
            probe["id"] = debugger.generate_probe_id("log")
            self._convert_to_line_probe_if_needed(probe)

        self.set_probes(probes)
        self.send_rc_probes()
        if not self.wait_for_all_probes(statuses=["INSTALLED"], timeout=30):
            self.setup_failures.append("Probes did not reach INSTALLED status within 30s")

        for i in range(request_count):
            self.send_weblog_request("/debugger/log", reset=(i == 0))
            if spacing_s > 0 and i < request_count - 1:
                time.sleep(spacing_s)

    def setup_filter_rejected_probe_installs(self) -> None:
        self._setup_filter_rejected(request_count=1, spacing_s=0.0)

    def test_filter_rejected_probe_installs(self) -> None:
        self.collect()
        self.assert_setup_ok()
        self.assert_rc_state_not_error()
        self._assert_probes_installed()

    def setup_filter_rejected_no_error_spam(self) -> None:
        self._setup_filter_rejected(request_count=5, spacing_s=1.5)
        # Returns as soon as a second event lands; a conforming tracer emits at most one, so it times out.
        self.wait_for_snapshot_count(2, timeout=5)

    def test_filter_rejected_no_error_spam(self) -> None:
        """A ``captureSnapshot: false`` probe with a rejecting ``when`` and broken captures must not spam."""
        self.collect()
        self.assert_setup_ok()
        # Without an installed probe and successful hits, emitting no event is vacuously true.
        self._assert_probes_installed()
        self.assert_all_weblog_responses_ok()

        for probe_id in self.probe_ids:
            snapshots = self.probe_snapshots.get(probe_id, [])
            assert len(snapshots) <= 1, (
                f"The probe emitted {len(snapshots)} event(s) for 5 filter-rejected hits spaced >1s "
                f"apart. A conforming tracer must either skip capture-expression evaluation entirely "
                f"on filter-rejected hits (0 events) or rate-limit any resulting eval errors to at "
                f"most 1 event per probe per 5 minutes."
            )
