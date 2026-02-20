# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import time
import tests.debugger.utils as debugger

from utils import scenarios, features, missing_feature, context, logger, interfaces


class BaseDebuggerCircuitBreakerTest(debugger.BaseDebuggerTest):
    """Base class for circuit breaker tests"""

    def _setup(self):
        """Setup test where circuit breaker should trip after first execution"""
        self.initialize_weblog_remote_config()

        # Prepare probe
        probes = debugger.read_probes("probe_snapshot_log_line")

        # Update probe ID
        for probe in probes:
            probe["id"] = debugger.generate_probe_id("log")

        # Set probe on a line that exists
        lines = self.method_and_language_to_line_number("LogProbe", context.library.name)
        for probe in probes:
            if "methodName" in probe["where"]:
                del probe["where"]["methodName"]
            probe["where"]["lines"] = lines
            probe["where"]["sourceFile"] = "ACTUAL_SOURCE_FILE"
            probe["where"]["typeName"] = None

        self.set_probes(probes)

        # Send remote config
        self.send_rc_probes()

        # Wait for probe to be installed
        if not self.wait_for_all_probes(statuses=["INSTALLED"], timeout=60):
            self.setup_failures.append("Probe did not reach INSTALLED status")
            return

        # Call endpoint FIRST time - should work and produce snapshot
        logger.info("Calling endpoint first time - should produce snapshot")
        self.send_weblog_request("/debugger/log")

        # Wait for probe to emit and then get disabled
        if not self.wait_for_all_probes(statuses=["EMITTING"], timeout=10):
            logger.warning("Probe did not reach EMITTING status after first call")

        # Wait for circuit breaker to trigger and diagnostic to be sent
        # Cannot use wait_for_all_probes here because the status change is immediate
        # after the probe executes, and there's no guarantee the diagnostic has been
        # sent to the agent yet. Give it time to process and send the diagnostic.
        time.sleep(2)

        # Check if probe transitioned to ERROR status (circuit breaker tripped)
        if not self.wait_for_all_probes(statuses=["ERROR"], timeout=10):
            self.setup_failures.append("Probe did not reach ERROR status (circuit breaker did not trip)")
            return

        # Call endpoint SECOND time - should NOT produce snapshot (probe disabled)
        logger.info("Calling endpoint second time - should NOT produce snapshot")
        self.send_weblog_request("/debugger/log")

        # Wait to ensure no second snapshot arrives
        # This sleep is necessary to give the system time to potentially send a second
        # snapshot (if the circuit breaker failed to disable the probe). We want to
        # ensure that the test would fail if a second snapshot was sent.
        time.sleep(2)

    def _assert(self):
        """Assert circuit breaker disabled probe after first execution"""
        self.collect()

        # Assert setup was ok
        self.assert_setup_ok()
        self.assert_rc_state_not_error()
        self.assert_all_weblog_responses_ok()

        # Assert probe reached ERROR status
        probe_id = self.probe_ids[0]
        probe_diagnostics = self.probe_diagnostics

        assert probe_id in probe_diagnostics, f"Probe {probe_id} not found in diagnostics"
        assert probe_diagnostics[probe_id]["status"] == "ERROR", \
            f"Expected probe status ERROR, got {probe_diagnostics[probe_id]['status']}"

        # Assert exactly ONE snapshot was captured (from first call only)
        snapshot_count = len(self.probe_snapshots.get(probe_id, []))
        assert snapshot_count == 1, \
            f"Expected exactly 1 snapshot (circuit breaker should prevent second), got {snapshot_count}"

        # Assert exception field exists in diagnostic payload
        self._assert_exception_in_diagnostics(probe_id)

    def _assert_exception_in_diagnostics(self, probe_id: str):
        """Assert that the diagnostic payload contains exception field with circuit breaker message"""
        # Get raw diagnostic payloads
        debugger_requests = list(interfaces.agent.get_data("/api/v2/debugger"))

        found_exception = False
        for request in debugger_requests:
            content = request["request"].get("content", []) or []
            for item in content:
                if "debugger" not in item:
                    continue

                debugger_data = item["debugger"]
                if "diagnostics" not in debugger_data:
                    continue

                diagnostics = debugger_data["diagnostics"]
                if diagnostics.get("probeId") != probe_id:
                    continue

                if diagnostics.get("status") == "ERROR":
                    # Check for exception field
                    assert "exception" in diagnostics, \
                        f"Expected 'exception' field in ERROR diagnostic for probe {probe_id}"

                    exception = diagnostics["exception"]
                    assert "type" in exception, "Expected 'type' field in exception"
                    assert "message" in exception, "Expected 'message' field in exception"

                    # Verify message mentions circuit breaker/disabled/CPU time
                    message = exception["message"]
                    assert "disabled" in message.lower() or "cpu" in message.lower(), \
                        f"Expected circuit breaker message, got: {message}"

                    logger.info(f"Found exception in diagnostic: {exception}")
                    found_exception = True
                    break

            if found_exception:
                break

        assert found_exception, \
            f"Did not find exception field in ERROR diagnostic for probe {probe_id}"


@features.debugger_circuit_breaker
@scenarios.debugger_circuit_breaker
@missing_feature(context.library != "ruby", reason="Circuit breaker test only for Ruby for now", force_skip=True)
class Test_Debugger_Circuit_Breaker(BaseDebuggerCircuitBreakerTest):
    """Test that circuit breaker disables probe after consuming too much CPU time"""

    def setup_circuit_breaker(self):
        self._setup()

    def test_circuit_breaker(self):
        self._assert()
