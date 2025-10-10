# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import tests.debugger.utils as debugger
from utils import features, scenarios, missing_feature, context, logger
import json
import time

TIMEOUT = 5


@features.debugger_inproduct_enablement
@scenarios.debugger_inproduct_enablement
class Test_Debugger_InProduct_Enablement_Dynamic_Instrumentation(debugger.BaseDebuggerTest):
    ############ dynamic instrumentation ############
    _probe_template = """
    {
        "version": 0,
        "where": {
            "typeName": null,
            "sourceFile": "ACTUAL_SOURCE_FILE",
            "lines": ["20"]
        }
    }
    """

    def setup_inproduct_enablement_di(self):
        def _send_config(enabled=None):
            probe = json.loads(self._probe_template)
            probe["id"] = debugger.generate_probe_id("log")
            self.set_probes([probe])

            self.send_rc_apm_tracing(dynamic_instrumentation_enabled=enabled)
            self.send_rc_probes()
            self.send_weblog_request("/debugger/log")

        self.initialize_weblog_remote_config()
        self.weblog_responses = []
        self.rc_states = []

        _send_config()
        self.di_initial_disabled = not self.wait_for_all_probes(statuses=["EMITTING"], timeout=TIMEOUT)

        _send_config(enabled=True)
        self.di_explicit_enabled = self.wait_for_all_probes(statuses=["EMITTING"], timeout=TIMEOUT)

        _send_config()
        self.di_empty_config = self.wait_for_all_probes(statuses=["EMITTING"], timeout=TIMEOUT)

        _send_config(enabled=False)
        self.di_explicit_disabled = not self.wait_for_all_probes(statuses=["EMITTING"], timeout=TIMEOUT)

    def test_inproduct_enablement_di(self):
        self.assert_rc_state_not_error()
        self.assert_all_weblog_responses_ok()

        assert self.di_initial_disabled, "Expected probes to not be emitting when dynamic instrumentation was disabled"
        assert self.di_explicit_enabled, "Expected probes to be emitting after enabling dynamic instrumentation"
        assert self.di_empty_config, "Expected probes to continue emitting with empty config"
        assert self.di_explicit_disabled, "Expected probes to stop emitting after explicit disable"


@features.debugger_inproduct_enablement
@scenarios.debugger_inproduct_enablement
class Test_Debugger_InProduct_Enablement_Exception_Replay(debugger.BaseDebuggerTest):
    ############ exception replay ############
    _max_retries = 2

    def _send_config(
        self,
        enabled: bool | None = None,
        service_name: str = "weblog",
        env: str = "system-tests",
        *,
        reset: bool = True,
    ):
        self.send_rc_apm_tracing(exception_replay_enabled=enabled, service_name=service_name, env=env, reset=reset)

    def _wait_for_exception_snapshot_received(self, request_path, exception_message):
        self.weblog_responses = []

        retries = 0
        snapshot_found = False

        while not snapshot_found and retries < self._max_retries:
            logger.debug(f"Waiting for snapshot, retry #{retries}")

            self.send_weblog_request(request_path, reset=False)
            snapshot_found = self.wait_for_snapshot_received(exception_message, TIMEOUT)

            retries += 1

        return snapshot_found

    def setup_inproduct_enablement_exception_replay(self):
        self.start_time = int(time.time() * 1000)
        self.initialize_weblog_remote_config()
        self.weblog_responses = []

        self.er_initial_enabled = not self._wait_for_exception_snapshot_received(
            "/exceptionreplay/simple", "simple exception"
        )

        self._send_config(enabled=True)
        self.er_explicit_enabled = self._wait_for_exception_snapshot_received(
            "/exceptionreplay/simple", "simple exception"
        )

        self._send_config()
        self.er_empty_config = self._wait_for_exception_snapshot_received(
            "/exceptionreplay/recursion?depth=1", "recursion exception depth 1"
        )

        self._send_config(enabled=False)
        self.er_explicit_disabled = not self._wait_for_exception_snapshot_received(
            "/exceptionreplay/multiframe", "multiple stack frames exception"
        )

    def test_inproduct_enablement_exception_replay(self):
        self.assert_rc_state_not_error()
        self.assert_all_weblog_responses_ok(expected_code=500)

        assert self.er_initial_enabled, "Expected snapshots to not be emitting when exception replay was disabled"
        assert self.er_explicit_enabled, "Expected snapshots to be emitting after enabling exception replay"
        assert self.er_empty_config, "Expected snapshots to continue emitting with empty config"
        assert self.er_explicit_disabled, "Expected snapshots to stop emitting after explicit disable"

    def setup_inproduct_enablement_exception_replay_apm_multiconfig(self):
        self.start_time = int(time.time() * 1000)
        self.initialize_weblog_remote_config()
        self.weblog_responses = []

        # Set a config with the wildcard service and env and ER=false.
        self._send_config(enabled=False, service_name="*", env="*")
        self.er_initial_enabled = not self._wait_for_exception_snapshot_received(
            "/exceptionreplay/simple", "simple exception"
        )

        # Set a config with the wildcard service and env and ER=true.
        self._send_config(enabled=True, service_name="*", env="*")
        self.er_apm_multiconfig_enabled = self._wait_for_exception_snapshot_received(
            "/exceptionreplay/simple", "simple exception"
        )

        # Set a config with the weblog service and env and ER=false.
        self._send_config(enabled=False, service_name="weblog", env="system-tests", reset=False)
        self.er_disabled_by_service_name = not self._wait_for_exception_snapshot_received(
            "/exceptionreplay/recursion?depth=1", "recursion exception depth 1"
        )

        # Set a config with the wildcard service and env and ER=true.
        self._send_config(enabled=True, service_name="*", env="*", reset=False)
        self.er_apm_multiconfig_enabled_2 = not self._wait_for_exception_snapshot_received(
            "/exceptionreplay/multiframe", "multiple stack frames exception"
        )

    @missing_feature(context.library == "python", force_skip=True)
    @missing_feature(context.library == "java", force_skip=True)
    def test_inproduct_enablement_exception_replay_apm_multiconfig(self):
        self.assert_rc_state_not_error()
        self.assert_all_weblog_responses_ok(expected_code=500)

        assert self.er_initial_enabled, "Expected snapshots to not be emitting when exception replay was disabled"
        assert self.er_apm_multiconfig_enabled, "Expected snapshots to be emitting after enabling exception replay"
        assert self.er_disabled_by_service_name, "Expected snapshots to stop emitting after service name override"
        assert self.er_apm_multiconfig_enabled_2, "Expected snapshots to not be emitting after service name override"


@features.debugger_inproduct_enablement
@scenarios.debugger_inproduct_enablement
@missing_feature(context.library == "java", force_skip=True)
@missing_feature(context.library == "python", force_skip=True)
class Test_Debugger_InProduct_Enablement_Code_Origin(debugger.BaseDebuggerTest):
    ########### code origin ############
    def setup_inproduct_enablement_code_origin(self):
        def _send_config(enabled=None):
            self.send_rc_apm_tracing(code_origin_enabled=enabled)
            self.send_weblog_request("/healthcheck")

        self.initialize_weblog_remote_config()
        self.weblog_responses = []
        self.rc_states = []

        self.er_initial_enabled = not self.wait_for_code_origin_span(TIMEOUT)

        _send_config(enabled=True)
        self.er_explicit_enabled = self.wait_for_code_origin_span(TIMEOUT)

        _send_config()
        self.er_empty_config = self.wait_for_code_origin_span(TIMEOUT)

        _send_config(enabled=False)
        self.er_explicit_disabled = not self.wait_for_code_origin_span(TIMEOUT)

    def test_inproduct_enablement_code_origin(self):
        self.assert_rc_state_not_error()
        self.assert_all_weblog_responses_ok()

        assert self.er_initial_enabled, "Expected no spans when code origin was disabled"
        assert self.er_explicit_enabled, "Expected spans to emit after enabling code origin"
        assert self.er_empty_config, "Expected spans to continue emitting with empty config"
        assert self.er_explicit_disabled, "Expected spans to stop emitting after explicit disable"
