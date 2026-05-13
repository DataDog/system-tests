"""Tests for post-collection warmup ordering (ADR-002).

Covers:
- Defer path: both versions known from image labels → container startup
  moves to post_collection_warmups in correct order.
- Fallback/legacy paths: watchdog is inserted at index 2 (after network).
- execute_post_collection_warmups: calls all callables and propagates errors.
"""

from contextlib import contextmanager
from threading import RLock
from unittest.mock import MagicMock, patch

import pytest

from utils import interfaces, scenarios
from utils._context._scenarios.endtoend import EndToEndScenario
from utils._context.component_version import ComponentVersion
from utils._context.containers import ProxyContainer, TestedContainer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(*, replay: bool = False) -> MagicMock:
    cfg = MagicMock()
    cfg.option.replay = replay
    cfg.option.force_dd_trace_debug = False
    cfg.option.force_dd_iast_debug = False
    return cfg


def _stub_base_configure(self, *, host_log_folder: str, replay: bool) -> None:  # noqa: ARG001
    """Minimal TestedContainer.configure substitute: skips Docker and file I/O."""
    self.host_log_folder = host_log_folder
    self._starting_lock = RLock()
    # image.labels / image.env must be pre-populated by the test fixture


def _stub_proxy_configure(self, *, host_log_folder: str, replay: bool) -> None:  # noqa: ARG001
    """ProxyContainer.configure substitute: skips JSON file writes."""
    self.host_log_folder = host_log_folder
    self._starting_lock = RLock()


@contextmanager
def _configured_scenario(*, library_version: str | None, agent_version: str | None):
    """Yield a fully configured EndToEndScenario with all Docker I/O patched out.

    Image labels are pre-populated so that label-based version detection works:
    - library_version set  → WeblogContainer._library is set during configure()
    - agent_version set    → AgentContainer.agent_version is set during configure()
    """
    scenario = EndToEndScenario("FAKE_E2E", doc="test", github_workflow="endtoend")

    # Pre-populate image labels/env to satisfy label-reading logic in configure()
    scenario.weblog_container.image.labels = {
        "system-tests-library": "python",
        "system-tests-weblog-variant": "flask",
    }
    if library_version:
        scenario.weblog_container.image.labels["system-tests-library-version"] = library_version
    scenario.weblog_container.image.env = {}

    scenario.agent_container.image.labels = {}
    if agent_version:
        scenario.agent_container.image.labels["org.opencontainers.image.version"] = agent_version

    with (
        patch("utils._context._scenarios.endtoend.get_docker_client") as mock_dc,
        patch.object(TestedContainer, "configure", _stub_base_configure),
        patch.object(ProxyContainer, "configure", _stub_proxy_configure),
        patch.object(interfaces.agent, "configure"),
        patch.object(interfaces.library, "configure"),
        patch.object(interfaces.backend, "configure"),
        patch.object(interfaces.library_dotnet_managed, "configure"),
        patch.object(interfaces.library_stdout, "configure"),
        patch.object(interfaces.agent_stdout, "configure"),
    ):
        mock_dc.return_value.info.return_value = {"CgroupVersion": "2"}
        scenario.configure(_make_config())
        yield scenario


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@scenarios.test_the_test
class Test_WarmupOrdering:
    """Warmup list invariants after EndToEndScenario.configure()."""

    # -- Defer path ----------------------------------------------------------

    def test_defer_path_container_startup_not_in_warmups(self):
        """Both versions from labels: container startup must be absent from warmups."""
        with _configured_scenario(library_version="1.2.3", agent_version="7.50.0") as s:
            for fn in (s._create_network, s._start_containers):
                assert fn not in s.warmups, f"{fn.__name__} must not be in warmups (defer path)"
            for c in s._containers:
                assert c.post_start not in s.warmups, f"{c.name}.post_start must not be in warmups (defer path)"

    def test_defer_path_post_collection_order(self):
        """Defer path: post_collection_warmups order must be network→watchdog→containers→readiness."""
        with _configured_scenario(library_version="1.2.3", agent_version="7.50.0") as s:
            pcw = s.post_collection_warmups

            idx_net = pcw.index(s._create_network)
            idx_wdg = pcw.index(s._start_interfaces_watchdog)
            idx_start = pcw.index(s._start_containers)
            idx_readiness = pcw.index(s._wait_for_app_readiness)

            assert idx_net < idx_wdg, "network must precede watchdog"
            assert idx_wdg < idx_start, "watchdog must precede _start_containers"

            for c in s._containers:
                idx_ps = pcw.index(c.post_start)
                assert idx_start < idx_ps, f"{c.name}.post_start must follow _start_containers"
                assert idx_ps < idx_readiness, f"{c.name}.post_start must precede _wait_for_app_readiness"

    def test_defer_path_weblog_system_info_before_readiness(self):
        """_get_weblog_system_info must appear in post_collection_warmups before _wait_for_app_readiness."""
        with _configured_scenario(library_version="1.2.3", agent_version="7.50.0") as s:
            pcw = s.post_collection_warmups
            assert s._get_weblog_system_info in pcw
            assert pcw.index(s._get_weblog_system_info) < pcw.index(s._wait_for_app_readiness)

    # -- Fallback path (library known, agent unknown) ------------------------

    def test_fallback_path_watchdog_position(self):
        """Library version from label only: watchdog must be at index 2 (after network)."""
        with _configured_scenario(library_version="1.2.3", agent_version=None) as s:
            assert s.warmups[0] == s._log_starting_containers
            assert s.warmups[1] == s._create_network
            assert s.warmups[2] == s._start_interfaces_watchdog
            assert s.warmups[3] == s._start_containers

    def test_fallback_path_container_startup_in_warmups(self):
        """Library version from label only: container startup must stay in warmups."""
        with _configured_scenario(library_version="1.2.3", agent_version=None) as s:
            assert s._create_network in s.warmups
            assert s._start_containers in s.warmups

    # -- Legacy path (no labels) ---------------------------------------------

    def test_legacy_path_watchdog_position(self):
        """No label versions: watchdog must be at index 2 (after network)."""
        with _configured_scenario(library_version=None, agent_version=None) as s:
            assert s.warmups[0] == s._log_starting_containers
            assert s.warmups[1] == s._create_network
            assert s.warmups[2] == s._start_interfaces_watchdog
            assert s.warmups[3] == s._start_containers


@scenarios.test_the_test
class Test_ExecutePostCollectionWarmups:
    """execute_post_collection_warmups behaviour."""

    def test_all_callables_are_invoked(self):
        """Every item in post_collection_warmups is called in order."""
        from utils._context._scenarios.core import Scenario

        calls: list[int] = []
        scenario = Scenario("FAKE", doc="", github_workflow="testthetest")
        scenario.post_collection_warmups = [lambda i=i: calls.append(i) for i in range(3)]

        scenario.execute_post_collection_warmups()

        assert calls == [0, 1, 2]

    def test_error_calls_close_targets_and_reraises(self):
        """An exception in a warmup must trigger close_targets() and propagate."""
        from utils._context._scenarios.core import Scenario

        closed: list[bool] = []

        class FakeScenario(Scenario):
            def close_targets(self):
                closed.append(True)

        scenario = FakeScenario("FAKE", doc="", github_workflow="testthetest")
        scenario.post_collection_warmups = [lambda: (_ for _ in ()).throw(RuntimeError("boom"))]

        with pytest.raises(RuntimeError, match="boom"):
            scenario.execute_post_collection_warmups()

        assert closed == [True], "close_targets() must be called on warmup error"
