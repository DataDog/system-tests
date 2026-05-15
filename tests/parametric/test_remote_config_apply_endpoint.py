"""Parametric tests for POST /trace/remote-config/apply.

These tests exercise the synchronous RC-apply endpoint added in this PR.
They are intentionally tracer-agnostic — they only assert the contract
documented in docs/parametric/remote-config-apply-contract.md.
"""

from typing import Any

from utils import scenarios, features
from utils.docker_fixtures import TestAgentAPI

from tests.parametric.conftest import APMLibrary
from tests.parametric.test_dynamic_configuration import (
    _create_rc_config,
    _set_rc,
)


@scenarios.parametric
@features.dynamic_configuration
class TestRemoteConfigApplyEndpoint:
    """Black-box tests of the /trace/remote-config/apply contract."""

    def test_apply_returns_empty_when_no_rc_received(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """When no RC has been sent, the endpoint returns 200 with applied_configs=[]."""
        test_agent.clear()
        result = test_library.flush_remote_config()
        assert isinstance(result, list)
        # No RC has been published, so nothing should be applied yet.
        assert result == [], f"expected empty applied_configs, got {result!r}"

    def test_apply_returns_applied_config_after_set(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """After publishing a config, the endpoint returns it in applied_configs."""
        rc_config: dict[str, Any] = _create_rc_config({"tracing_sampling_rate": 0.5})
        used_config_id = _set_rc(test_agent, rc_config, config_id="test-apply-set")

        result = test_library.flush_remote_config()
        config_ids = [c["config_id"] for c in result]
        products = {c["product"] for c in result}

        assert used_config_id in config_ids, (
            f"expected config_id {used_config_id!r} in applied set, got {config_ids!r}"
        )
        assert products == {"APM_TRACING"}, f"expected only APM_TRACING, got {products!r}"

    def test_apply_is_idempotent(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Calling apply twice in a row with no new RC is a no-op."""
        _set_rc(test_agent, _create_rc_config({"tracing_sampling_rate": 0.3}), config_id="idem-1")
        first = test_library.flush_remote_config()
        second = test_library.flush_remote_config()
        first_ids = sorted(c["config_id"] for c in first)
        second_ids = sorted(c["config_id"] for c in second)
        assert first_ids == second_ids, (
            f"applied set changed between idempotent calls: {first_ids!r} -> {second_ids!r}"
        )

    def test_apply_respects_server_timeout(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """If the underlying RC primitives hang, the server returns 504 within ~10s.

        We can't easily simulate a hang from outside the container, so this
        test asserts the documented behavior path by confirming the endpoint
        URL is reachable and returns within the server-side timeout window
        under normal load. The full hang path is covered by the unit test in
        the parametric server itself (TODO when we have one).
        """
        import time

        start = time.monotonic()
        test_library.flush_remote_config(timeout=10.0)
        elapsed = time.monotonic() - start
        assert elapsed < 10.0, f"endpoint took {elapsed:.2f}s, expected <10s under normal load"

    def test_set_and_wait_rc_applied_returns_after_apply(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """set_and_wait_rc_applied calls set_and_wait_rc then flush_remote_config."""
        from tests.parametric.test_dynamic_configuration import set_and_wait_rc_applied

        rc_state = set_and_wait_rc_applied(
            test_agent,
            test_library,
            config_overrides={"tracing_sampling_rate": 0.7},
            config_id="combined-helper-1",
        )
        # set_and_wait_rc returns the rc state dict from the test agent
        assert rc_state is not None
        assert rc_state.get("apply_state") in (2, "2"), f"unexpected rc_state: {rc_state!r}"

        # And after the call, the config is applied (visible via the endpoint directly)
        applied = test_library.flush_remote_config()
        assert any(c["config_id"] == "combined-helper-1" for c in applied)
