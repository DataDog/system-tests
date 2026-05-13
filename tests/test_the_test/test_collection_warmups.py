"""Tests for post-collection warmup ordering (ADR-002)."""

from contextlib import contextmanager
from threading import RLock
from unittest.mock import MagicMock, patch

import pytest

from utils import interfaces, scenarios
from utils._context._scenarios.core import Scenario
from utils._context._scenarios.endtoend import EndToEndScenario
from utils._context.containers import ProxyContainer, TestedContainer


def _stub_configure(self, *, host_log_folder: str, replay: bool) -> None:  # noqa: ARG001
    """Stand-in for *Container.configure that skips Docker and file I/O."""
    self.host_log_folder = host_log_folder
    self._starting_lock = RLock()


@contextmanager
def _configured_scenario(*, library_version: str | None, agent_version: str | None):
    """Yield a configured EndToEndScenario with all Docker / interface I/O patched out.

    Image labels drive label-based version detection in container.configure().
    """
    scenario = EndToEndScenario("FAKE_E2E", doc="test")

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

    cfg = MagicMock()
    cfg.option.replay = False

    with (
        patch("utils._context._scenarios.endtoend.get_docker_client") as mock_dc,
        patch.object(TestedContainer, "configure", _stub_configure),
        patch.object(ProxyContainer, "configure", _stub_configure),
        patch.object(interfaces.agent, "configure"),
        patch.object(interfaces.library, "configure"),
        patch.object(interfaces.backend, "configure"),
        patch.object(interfaces.library_dotnet_managed, "configure"),
        patch.object(interfaces.library_stdout, "configure"),
        patch.object(interfaces.agent_stdout, "configure"),
    ):
        mock_dc.return_value.info.return_value = {"CgroupVersion": "2"}
        scenario.configure(cfg)
        try:
            yield scenario
        finally:
            # Pop from the global scenario group registry to avoid polluting other tests.
            for group in scenario.scenario_groups:
                if scenario in group.scenarios:
                    group.scenarios.remove(scenario)


@scenarios.test_the_test
class Test_WarmupOrdering:
    """Warmup list invariants after EndToEndScenario.configure()."""

    def test_defer_path_container_startup_not_in_warmups(self):
        with _configured_scenario(library_version="1.2.3", agent_version="7.50.0") as s:
            for fn in (s._create_network, s._start_containers):
                assert fn not in s.warmups
            for c in s._containers:
                assert c.post_start not in s.warmups

    def test_defer_path_post_collection_order(self):
        with _configured_scenario(library_version="1.2.3", agent_version="7.50.0") as s:
            pcw = s.post_collection_warmups
            idx_net = pcw.index(s._create_network)
            idx_wdg = pcw.index(s._start_interfaces_watchdog)
            idx_start = pcw.index(s._start_containers)
            idx_readiness = pcw.index(s._wait_for_app_readiness)

            assert idx_net < idx_wdg < idx_start < idx_readiness
            for c in s._containers:
                idx_ps = pcw.index(c.post_start)
                assert idx_start < idx_ps < idx_readiness

    def test_defer_path_weblog_system_info_before_readiness(self):
        with _configured_scenario(library_version="1.2.3", agent_version="7.50.0") as s:
            pcw = s.post_collection_warmups
            assert pcw.index(s._get_weblog_system_info) < pcw.index(s._wait_for_app_readiness)

    def test_fallback_path_watchdog_after_network(self):
        """Library version from label only: watchdog must follow network creation."""
        with _configured_scenario(library_version="1.2.3", agent_version=None) as s:
            assert s._create_network in s.warmups
            assert s._start_containers in s.warmups
            assert s.warmups.index(s._create_network) < s.warmups.index(s._start_interfaces_watchdog)
            assert s.warmups.index(s._start_interfaces_watchdog) < s.warmups.index(s._start_containers)

    def test_legacy_path_watchdog_after_network(self):
        with _configured_scenario(library_version=None, agent_version=None) as s:
            assert s.warmups.index(s._create_network) < s.warmups.index(s._start_interfaces_watchdog)
            assert s.warmups.index(s._start_interfaces_watchdog) < s.warmups.index(s._start_containers)


@scenarios.test_the_test
class Test_ExecutePostCollectionWarmups:
    def test_all_callables_are_invoked(self):
        calls: list[int] = []
        scenario = Scenario("FAKE", doc="", github_workflow="testthetest")
        scenario.post_collection_warmups = [lambda i=i: calls.append(i) for i in range(3)]

        scenario.execute_post_collection_warmups()

        assert calls == [0, 1, 2]

    def test_error_calls_close_targets_and_reraises(self):
        closed: list[bool] = []

        class FakeScenario(Scenario):
            def close_targets(self):
                closed.append(True)

        scenario = FakeScenario("FAKE2", doc="", github_workflow="testthetest")

        def boom():
            raise RuntimeError("boom")

        scenario.post_collection_warmups = [boom]

        with pytest.raises(RuntimeError, match="boom"):
            scenario.execute_post_collection_warmups()

        assert closed == [True]
