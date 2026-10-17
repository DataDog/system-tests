# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import tests.debugger.utils as debugger
from utils import context, features, logger, remote_config, scenarios, slow, weblog
import json
import time

TIMEOUT = 5
DEFAULT_ENVVARS = {
    "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.2",
}
LOG_PROBE_TEMPLATE = """
{
    "version": 0,
    "where": {
        "typeName": null,
        "sourceFile": "ACTUAL_SOURCE_FILE",
        "lines": ["20"]
    }
}
"""


@features.debugger_inproduct_enablement
@scenarios.debugger_inproduct_enablement
class Test_Debugger_InProduct_Enablement_Dynamic_Instrumentation(debugger.BaseDebuggerTest):
    ############ dynamic instrumentation ############
    def setup_inproduct_enablement_di(self):
        def _send_config(*, enabled: bool | None = None, reset: bool = True):
            probe = json.loads(LOG_PROBE_TEMPLATE)
            probe["id"] = debugger.generate_probe_id("log")
            self.set_probes([probe])

            self.send_rc_apm_tracing_and_probes(dynamic_instrumentation_enabled=enabled, reset=reset)
            self.send_weblog_request("/debugger/log")

        self.initialize_weblog_remote_config()
        self.weblog_responses = []
        self.rc_states = []

        _send_config()
        self.di_initial_disabled = not self.wait_for_all_probes(statuses=["EMITTING"], timeout=TIMEOUT)

        _send_config(enabled=True, reset=False)
        self.di_explicit_enabled = self.wait_for_all_probes(statuses=["EMITTING"], timeout=TIMEOUT)

        _send_config(reset=False)
        self.di_empty_config = self.wait_for_all_probes(statuses=["EMITTING"], timeout=TIMEOUT)

        _send_config(enabled=False, reset=False)
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
        service_name: str = "weblog",
        env: str = "system-tests",
        *,
        enabled: bool | None = None,
        reset: bool = True,
    ):
        self.send_rc_apm_tracing(exception_replay_enabled=enabled, service_name=service_name, env=env, reset=reset)

    def _wait_for_exception_snapshot_received(self, request_path: str, exception_message: str):
        self.weblog_responses = []

        retries = 0
        snapshot_found = False

        while not snapshot_found and retries < self._max_retries:
            logger.debug(f"Waiting for snapshot, retry #{retries}")

            self.send_weblog_request(request_path, reset=False)
            snapshot_found = self.wait_for_all_snapshots(exception_message, TIMEOUT)

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

    @slow
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

    @slow
    def test_inproduct_enablement_exception_replay_apm_multiconfig(self):
        self.assert_rc_state_not_error()
        self.assert_all_weblog_responses_ok(expected_code=500)

        assert self.er_initial_enabled, "Expected snapshots to not be emitting when exception replay was disabled"
        assert self.er_apm_multiconfig_enabled, "Expected snapshots to be emitting after enabling exception replay"
        assert self.er_disabled_by_service_name, "Expected snapshots to stop emitting after service name override"
        assert self.er_apm_multiconfig_enabled_2, "Expected snapshots to not be emitting after service name override"


@features.debugger_inproduct_enablement
@scenarios.debugger_inproduct_enablement
@slow
class Test_Debugger_InProduct_Enablement_Code_Origin(debugger.BaseDebuggerTest):
    ########### code origin ############
    _WARMUP_TIMEOUT = 10
    _CODE_ORIGIN_TIMEOUT = 30

    def _check_code_origin(self):
        """Send a request and check if code origin spans are present."""
        request = self.send_weblog_request("/")
        return self.wait_for_code_origin_span(request, self._CODE_ORIGIN_TIMEOUT)

    def _warmup_code_origin(self):
        """Send a request and wait until the tracer has instrumented the view function."""
        request = self.send_weblog_request("/")
        self.wait_for_code_origin_span(request, self._WARMUP_TIMEOUT, stop_when_absent=False)

    def _set_code_origin_and_check(self, *, enabled: bool | None):
        """Set code origin via remote config and check if spans are present."""
        self.send_rc_apm_tracing(code_origin_enabled=enabled)
        return self._check_code_origin()

    def setup_inproduct_enablement_code_origin(self):
        self.initialize_weblog_remote_config()
        self.weblog_responses = []

        # Node.js starts code origin asynchronously. Let it instrument the view
        # function before checking the default-on state with a fresh request.
        if context.library == "nodejs":
            self._warmup_code_origin()

        # Check initial state (default varies by language)
        self.co_initial_state = self._check_code_origin()

        # Explicitly enable via remote config
        self.co_explicit_enabled = self._set_code_origin_and_check(enabled=True)

        # Send empty config (null value), should maintain enabled state
        self.co_empty_config = self._set_code_origin_and_check(enabled=None)

        # Explicitly disable via remote config
        self.co_explicit_disabled = not self._set_code_origin_and_check(enabled=False)

    def test_inproduct_enablement_code_origin(self):
        self.assert_rc_state_not_error()
        self.assert_all_weblog_responses_ok()

        # Check initial state based on language-specific defaults
        if context.library == "nodejs":
            assert self.co_initial_state, "Expected code origin enabled by default"
        else:
            assert not self.co_initial_state, "Expected code origin disabled by default"

        assert self.co_explicit_enabled, "Expected spans with code origin after explicit enable"
        assert self.co_empty_config, "Expected spans to continue emitting with empty config"
        assert self.co_explicit_disabled, "Expected spans to stop emitting after explicit disable"


@features.debugger_code_origins
@scenarios.debugger_inproduct_enablement
@slow
class Test_Debugger_InProduct_Enablement_Code_Origin_Default_On(debugger.BaseDebuggerTest):
    # Timeout for the warmup request that lets the tracer finish instrumenting
    # the view functions, and the longer timeout for the actual check that
    # absorbs slow trace flush/delivery under CI load.
    _WARMUP_TIMEOUT = 10
    _CODE_ORIGIN_TIMEOUT = 30

    def setup_code_origin_enabled_by_default(self):
        self.initialize_weblog_remote_config()

        # The preceding code-origin in-product enablement test explicitly
        # disables code origin via remote config. Clear that RC state so this
        # test observes the true default rather than the previous override.
        self.send_rc_apm_tracing(reset=True)

        # The code origin product is started asynchronously and only instruments
        # the view functions once enabled, so a request sent right after startup
        # may be served before the code origin metadata is attached. Send a
        # warmup request to let instrumentation complete before the real check.
        warmup_request = self.send_weblog_request("/")
        self.wait_for_code_origin_span(warmup_request, timeout=self._WARMUP_TIMEOUT, stop_when_absent=False)

        # Correlate the trace lookup to this request so that stale traces cannot
        # satisfy the check and a fast trace cannot be discarded.
        request = self.send_weblog_request("/")
        self.code_origin_enabled_by_default = self.wait_for_code_origin_span(request, timeout=self._CODE_ORIGIN_TIMEOUT)

    def test_code_origin_enabled_by_default(self):
        self.assert_setup_ok()
        self.assert_all_weblog_responses_ok()

        assert self.code_origin_enabled_by_default, "Expected code origin enabled by default"


@features.debugger_inproduct_enablement
@scenarios.debugger_inproduct_enablement
class Test_Debugger_InProduct_Enablement_Multiconfig_Partial_Update(debugger.BaseDebuggerTest):
    """Updating one APM_TRACING config must not drop the other active configs.

    An unchanged file keeps its hash, so libraries skip it, but it is still listed
    in client_configs and must stay applied.
    """

    _WILDCARD_CONFIG_PATH = "datadog/2/APM_TRACING/inproduct-multiconfig-wildcard/config"
    _SERVICE_CONFIG_PATH = "datadog/2/APM_TRACING/inproduct-multiconfig-service/config"

    def _set_apm_tracing_config(self, path: str, settings: dict, *, service_name: str, env: str) -> None:
        lib_config = {"library_language": "all", "library_version": "latest", "tracing_enabled": True} | settings
        config = {
            "schema_version": "v1.0.0",
            "action": "enable",
            "lib_config": lib_config,
            "service_target": {"service": service_name, "env": env},
        }
        if remote_config.library_supports_sdk_configuration():
            config = remote_config.to_sdk_config_payload(config)
        remote_config.tracer_rc_state.set_config(path, config)

    def _apply_with_new_probe_and_check_emitting(self) -> bool:
        probe = json.loads(LOG_PROBE_TEMPLATE)
        probe["id"] = debugger.generate_probe_id("log")
        self.set_probes([probe])
        remote_config.tracer_rc_state.set_config(
            f"datadog/2/LIVE_DEBUGGING/logProbe_{probe['id']}/config", self.probe_definitions[0]
        )

        self.rc_states.append(remote_config.tracer_rc_state.apply())

        # PHP tracer requires requests to /debugger/* to process RC and resolve probe hooks.
        if context.library == "php":
            weblog.get(f"/debugger/init?probes={probe['id']}")

        self.send_weblog_request("/debugger/log", reset=False)
        return self.wait_for_all_probes(statuses=["EMITTING"], timeout=TIMEOUT)

    def setup_inproduct_enablement_multiconfig_partial_update(self):
        self.initialize_weblog_remote_config()
        self.weblog_responses = []
        self.rc_states = []
        remote_config.tracer_rc_state.reset().apply()

        # The wildcard config enables dynamic instrumentation, the service config only sets code origin.
        self._set_apm_tracing_config(
            self._WILDCARD_CONFIG_PATH, {"dynamic_instrumentation_enabled": True}, service_name="*", env="*"
        )
        self._set_apm_tracing_config(
            self._SERVICE_CONFIG_PATH, {"code_origin_enabled": True}, service_name="weblog", env="system-tests"
        )
        self.di_enabled = self._apply_with_new_probe_and_check_emitting()

        # Change a single setting of the service config. The wildcard config is resent unchanged.
        self._set_apm_tracing_config(
            self._SERVICE_CONFIG_PATH, {"code_origin_enabled": False}, service_name="weblog", env="system-tests"
        )
        self.di_kept_enabled = self._apply_with_new_probe_and_check_emitting()

    def test_inproduct_enablement_multiconfig_partial_update(self):
        self.assert_rc_state_not_error()
        self.assert_all_weblog_responses_ok()

        assert self.di_enabled, (
            "Expected probes to be emitting after the wildcard config enabled dynamic instrumentation"
        )
        assert self.di_kept_enabled, "Expected probes to keep emitting after updating only the service config"
