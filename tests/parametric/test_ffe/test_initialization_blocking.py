"""Test that FFE provider initialization blocks until config is received.

This test proves FFL-1843: Python OpenFeature Provider initialization not blocking.
The provider's initialize() should block until Remote Config delivers flag configuration
(or a timeout expires), matching the behavior of Java, Go, and Node.js SDKs.
"""

import json
import threading
import time
import pytest
from typing import Any

from utils import (
    features,
    scenarios,
)
from utils.dd_constants import RemoteConfigApplyState
from utils.docker_fixtures import TestAgentAPI
from tests.parametric.conftest import APMLibrary

RC_PRODUCT = "FFE_FLAGS"
RC_PATH = f"datadog/2/{RC_PRODUCT}"

parametrize = pytest.mark.parametrize

DEFAULT_ENVVARS = {
    "DD_EXPERIMENTAL_FLAGGING_PROVIDER_ENABLED": "true",
    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.2",
    "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.2",
}

# Simple UFC fixture
UFC_FIXTURE_DATA = {
    "createdAt": "2024-04-17T19:40:53.716Z",
    "format": "SERVER",
    "environment": {"name": "Test"},
    "flags": {
        "init-test-flag": {
            "key": "init-test-flag",
            "enabled": True,
            "variationType": "STRING",
            "variations": {
                "on": {"key": "on", "value": "real-flag-value"},
                "off": {"key": "off", "value": "off"},
            },
            "allocations": [
                {
                    "key": "default-allocation",
                    "rules": [],
                    "splits": [{"variationKey": "on", "shards": []}],
                    "doLog": True,
                }
            ],
        }
    },
}


def _set_and_wait_ffe_rc(
    test_agent: TestAgentAPI, ufc_data: dict[str, Any], config_id: str | None = None
) -> dict[str, Any]:
    if not config_id:
        config_id = str(hash(json.dumps(ufc_data, sort_keys=True)))
    test_agent.set_remote_config(path=f"{RC_PATH}/{config_id}/config", payload=ufc_data)
    return test_agent.wait_for_rc_apply_state(RC_PRODUCT, state=RemoteConfigApplyState.ACKNOWLEDGED, clear=True)


@scenarios.parametric
@features.feature_flags_dynamic_evaluation
class Test_FFE_Initialization_Blocks_Until_Config:
    """Test that provider initialization blocks until RC config is delivered.

    Validates the fix for FFL-1843: Python's initialize() must block until
    Remote Config delivers config, matching Java/Go/Node.js behavior.
    """

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_ffe_init_blocks_until_config_received(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Baseline: config delivered BEFORE ffe_start, evaluate returns real values."""
        _set_and_wait_ffe_rc(test_agent, UFC_FIXTURE_DATA)

        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        result = test_library.ffe_evaluate(
            flag="init-test-flag",
            variation_type="STRING",
            default_value="default-sentinel",
            targeting_key="user-1",
            attributes={},
        )

        assert result.get("value") == "real-flag-value", (
            f"Expected 'real-flag-value' but got '{result.get('value')}'. "
            f"Config was delivered before ffe_start()."
        )

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_ffe_init_returns_real_values_not_defaults(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Config delivered AFTER ffe_start but BEFORE eval -- should return real values."""
        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        _set_and_wait_ffe_rc(test_agent, UFC_FIXTURE_DATA)

        result = test_library.ffe_evaluate(
            flag="init-test-flag",
            variation_type="STRING",
            default_value="default-sentinel",
            targeting_key="user-1",
            attributes={},
        )

        assert result.get("value") == "real-flag-value", (
            f"Expected 'real-flag-value' but got '{result.get('value')}'. "
            f"Config was delivered after ffe_start() but before evaluation."
        )

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_ffe_evaluation_immediately_after_start_without_config(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """No config, immediate eval -- provider must NOT claim READY in <5s.

        If initialize() blocks correctly, ffe_start() will take ~30s (timeout).
        If initialize() doesn't block (FFL-1843 bug), ffe_start() returns in 0.00s
        and evaluation returns defaults with reason=DEFAULT while appearing READY.
        """
        start_time = time.monotonic()
        test_library.ffe_start()
        elapsed = time.monotonic() - start_time

        result = test_library.ffe_evaluate(
            flag="init-test-flag",
            variation_type="STRING",
            default_value="default-sentinel",
            targeting_key="user-1",
            attributes={},
        )

        value = result.get("value")
        reason = result.get("reason", "UNKNOWN")

        if value == "default-sentinel" and elapsed < 5.0:
            pytest.fail(
                f"BUG FFL-1843: ffe_start() returned in {elapsed:.2f}s (should block ~30s). "
                f"Provider returned default with reason='{reason}' without any config. "
                f"Full result: {result}"
            )

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_ffe_init_blocks_and_resolves_when_config_arrives(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Config arrives DURING blocking init -- provider unblocks and evaluates correctly.

        This is the key test for the fix: initialize() blocks, RC delivers config
        mid-block, the event is signaled, initialize() returns, and evaluations
        return real values immediately.
        """
        # Schedule config delivery 2s from now in a background thread
        def deliver_config():
            time.sleep(2)
            _set_and_wait_ffe_rc(test_agent, UFC_FIXTURE_DATA)

        timer = threading.Thread(target=deliver_config, daemon=True)
        timer.start()

        start_time = time.monotonic()
        success = test_library.ffe_start()
        elapsed = time.monotonic() - start_time

        assert success, "ffe_start() should succeed when config arrives during init"
        assert elapsed > 1.0, (
            f"ffe_start() returned in {elapsed:.1f}s -- too fast, should have blocked until config arrived (~2s)"
        )
        assert elapsed < 25.0, (
            f"ffe_start() took {elapsed:.1f}s -- config should have arrived after ~2s, not timed out"
        )

        # Evaluate immediately -- should get real values since config arrived during init
        result = test_library.ffe_evaluate(
            flag="init-test-flag",
            variation_type="STRING",
            default_value="default-sentinel",
            targeting_key="user-1",
            attributes={},
        )

        assert result.get("value") == "real-flag-value", (
            f"Expected 'real-flag-value' after blocking init resolved, got '{result.get('value')}'"
        )

    @parametrize(
        "library_env",
        [{**DEFAULT_ENVVARS, "DD_EXPERIMENTAL_FLAGGING_PROVIDER_INITIALIZATION_TIMEOUT_MS": "3000"}],
    )
    def test_ffe_init_timeout_returns_error(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Short timeout (3s) with no config -- provider should time out and enter ERROR state.

        After timeout, deliver config and verify late recovery to READY.
        """
        start_time = time.monotonic()
        test_library.ffe_start()
        elapsed = time.monotonic() - start_time

        # Should have blocked for ~3s (the configured timeout), not instant
        assert elapsed > 2.0, (
            f"ffe_start() returned in {elapsed:.1f}s -- should have blocked for ~3s timeout"
        )
        assert elapsed < 10.0, (
            f"ffe_start() took {elapsed:.1f}s -- should have timed out after ~3s, not 30s"
        )

        # Evaluate before config -- should get defaults (provider is in ERROR state after timeout)
        result_before = test_library.ffe_evaluate(
            flag="init-test-flag",
            variation_type="STRING",
            default_value="default-sentinel",
            targeting_key="user-1",
            attributes={},
        )

        assert result_before.get("value") == "default-sentinel", (
            f"Before config delivery, expected default 'default-sentinel', got '{result_before.get('value')}'"
        )

        # Now deliver config -- should trigger late recovery (on_configuration_received -> PROVIDER_READY)
        _set_and_wait_ffe_rc(test_agent, UFC_FIXTURE_DATA)

        # Evaluate after config -- should get real values (provider recovered to READY)
        result_after = test_library.ffe_evaluate(
            flag="init-test-flag",
            variation_type="STRING",
            default_value="default-sentinel",
            targeting_key="user-1",
            attributes={},
        )

        assert result_after.get("value") == "real-flag-value", (
            f"After late config delivery, expected 'real-flag-value', got '{result_after.get('value')}'. "
            f"Provider should recover from ERROR to READY when config arrives."
        )
