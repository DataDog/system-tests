# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import tests.debugger.utils as debugger
from utils import features, scenarios, missing_feature, context, logger
import json

TIMEOUT = 5


@features.debugger_inproduct_enablement
@scenarios.debugger_inproduct_enablement
@missing_feature(context.library == "python", force_skip=True)
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
@missing_feature(context.library == "python", force_skip=True)
class Test_Debugger_InProduct_Enablement_Exception_Replay(debugger.BaseDebuggerTest):
    ############ exception replay ############
    _max_retries = 2

    def setup_inproduct_enablement_exception_replay(self):
        def _send_config(enabled=None):
            self.send_rc_apm_tracing(exception_replay_enabled=enabled)

        def _wait_for_exception_snapshot_received(request_path, exception_message):
            self.weblog_responses = []

            retries = 0
            snapshot_found = False

            while not snapshot_found and retries < self._max_retries:
                logger.debug(f"Waiting for snapshot, retry #{retries}")

                self.send_weblog_request(request_path, reset=False)
                snapshot_found = self.wait_for_exception_snapshot_received(exception_message, TIMEOUT)

                retries += 1

            return snapshot_found

        self.initialize_weblog_remote_config()
        self.weblog_responses = []

        self.er_initial_enabled = not _wait_for_exception_snapshot_received(
            "/exceptionreplay/simple", "simple exception"
        )

        _send_config(enabled=True)
        self.er_explicit_enabled = _wait_for_exception_snapshot_received("/exceptionreplay/simple", "simple exception")

        _send_config()
        self.er_empty_config = _wait_for_exception_snapshot_received(
            "/exceptionreplay/recursion?depth=1", "recursion exception depth 1"
        )

        _send_config(enabled=False)
        self.er_explicit_disabled = not _wait_for_exception_snapshot_received(
            "/exceptionreplay/multiframe", "multiple stack frames exception"
        )

    def test_inproduct_enablement_exception_replay(self):
        self.assert_rc_state_not_error()
        self.assert_all_weblog_responses_ok(expected_code=500)

        assert self.er_initial_enabled, "Expected snapshots to not be emitting when exception replay was disabled"
        assert self.er_explicit_enabled, "Expected snapshots to be emitting after enabling exception replay"
        assert self.er_empty_config, "Expected snapshots to continue emitting with empty config"
        assert self.er_explicit_disabled, "Expected snapshots to stop emitting after explicit disable"

    def setup_inproduct_enablement_exception_default_replay(self):
        def _send_config(exception_replay_enabled=None, exception_replay_default_enabled=None):
            self.send_rc_apm_tracing(
                exception_replay_enabled=exception_replay_enabled,
                exception_replay_default_enabled=exception_replay_default_enabled,
            )

        def _wait_for_exception_snapshot_received(request_path, exception_message):
            self.weblog_responses = []

            retries = 0
            snapshot_found = False

            while not snapshot_found and retries < self._max_retries:
                logger.debug(f"Waiting for snapshot, retry #{retries}")

                self.send_weblog_request(request_path, reset=False)
                snapshot_found = self.wait_for_exception_snapshot_received(exception_message, TIMEOUT)

                retries += 1

            return snapshot_found

        self.initialize_weblog_remote_config()
        self.weblog_responses = []

        # First enable exception replay
        _send_config(exception_replay_enabled=True)
        _send_config(exception_replay_default_enabled=False)
        self.er_explicit_enabled = _wait_for_exception_snapshot_received("/exceptionreplay/simple", "simple exception")

    def test_inproduct_enablement_exception_default_replay(self):
        self.assert_rc_state_not_error()
        self.assert_all_weblog_responses_ok(expected_code=500)

        assert self.er_explicit_enabled, "Expected snapshots to be emitting after enabling exception replay"


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
