from threading import RLock
from unittest.mock import MagicMock

import pytest

from utils import interfaces, scenarios
from utils._context._scenarios.endtoend import DdTraceEndToEndScenario, DockerScenario, _load_environment_overrides
from utils._context.containers import TestedContainer as _TestedContainer


class FakeContainer(_TestedContainer):
    def __init__(self, name: str, events: list | None = None) -> None:
        super().__init__(name=name, image_name=name)
        self._test_events = events if events is not None else []

    def configure(self, *, host_log_folder: str, replay: bool):  # noqa: ARG002
        self._starting_lock = RLock()

    def start(self, network):  # noqa: ARG002, ANN001
        self._test_events.append(f"start {self.name}")
        self.healthy = True

    def remove(self):
        pass


@scenarios.test_the_test
def test_load_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYSTEM_TESTS_WEBLOG_ENV", '{"DD_TRACE_AGENT_PROTOCOL_VERSION": "1.0"}')

    assert _load_environment_overrides("SYSTEM_TESTS_WEBLOG_ENV") == {"DD_TRACE_AGENT_PROTOCOL_VERSION": "1.0"}

    monkeypatch.setenv("SYSTEM_TESTS_WEBLOG_ENV", '["not", "an", "object"]')
    with pytest.raises(ValueError, match="must be a JSON object"):
        _load_environment_overrides("SYSTEM_TESTS_WEBLOG_ENV")


@scenarios.test_the_test
def test_main():
    events: list[str] = []

    class FakeScenario(DockerScenario):
        def __init__(self) -> None:
            super().__init__(name="fake_scenario", github_workflow=None, doc="")

            container_a = FakeContainer("A", events)
            container_b = FakeContainer("B", events)
            container_c = FakeContainer("C", events)
            container_d = FakeContainer("D", events)

            container_a.depends_on.append(container_b)
            container_a.depends_on.append(container_c)
            container_b.depends_on.append(container_d)
            container_c.depends_on.append(container_d)
            container_b.depends_on.append(container_c)

            self._containers = [container_a, container_b, container_c, container_d]

    scenario = FakeScenario()
    scenario.configure(None)
    scenario.pytest_sessionstart(None)

    assert events == ["start D", "start C", "start B", "start A"]


@scenarios.test_the_test
def test_recursive():
    class FakeScenario(DockerScenario):
        def __init__(self) -> None:
            super().__init__(name="fake_scenario", github_workflow=None, doc="")

            container_a = FakeContainer("A")
            container_b = FakeContainer("B")
            container_c = FakeContainer("C")

            container_a.depends_on.append(container_b)
            container_b.depends_on.append(container_c)
            container_c.depends_on.append(container_a)

            self._containers = [container_a, container_b, container_c]

    scenario = FakeScenario()
    scenario.configure(None)
    with pytest.raises(RuntimeError):
        scenario.pytest_sessionstart(None)


@scenarios.test_the_test
def test_recursive_2():
    """More complex"""

    class FakeScenario(DockerScenario):
        def __init__(self) -> None:
            super().__init__(name="fake_scenario", github_workflow=None, doc="")

            container_a = FakeContainer("A")
            container_b = FakeContainer("B")
            container_c = FakeContainer("D")
            container_d = FakeContainer("E")
            container_e = FakeContainer("F")
            container_f = FakeContainer("G")
            container_g = FakeContainer("G")

            container_a.depends_on.append(container_b)
            container_b.depends_on.append(container_c)
            container_c.depends_on.append(container_d)
            container_d.depends_on.append(container_e)
            container_e.depends_on.append(container_f)
            container_f.depends_on.append(container_g)
            container_g.depends_on.append(container_c)

            self._containers = [container_a]

    scenario = FakeScenario()
    scenario.configure(None)
    with pytest.raises(RuntimeError):
        scenario.pytest_sessionstart(None)


@scenarios.test_the_test
@pytest.mark.parametrize(
    ("include_agent", "is_empty_test_run", "flush"),
    [(True, True, False), (True, False, True), (False, True, False), (False, False, False)],
)
def test_end_to_end_scenario_only_flushes_agent_backed_non_empty_test_runs(
    monkeypatch: pytest.MonkeyPatch, *, include_agent: bool, is_empty_test_run: bool, flush: bool
) -> None:
    scenario = DdTraceEndToEndScenario(
        "FAKE_END_TO_END",
        doc="",
        include_agent=include_agent,
        use_proxy_for_agent=False,
        use_proxy_for_weblog=False,
    )
    scenario.replay = False
    scenario.library_interface_timeout = 0
    scenario.weblog_infra = MagicMock()
    monkeypatch.setattr(scenario, "_wait_interface", MagicMock())

    monkeypatch.setattr(interfaces.library, "check_deserialization_errors", MagicMock())
    monkeypatch.setattr(interfaces.backend, "check_deserialization_errors", MagicMock())

    scenario._wait_and_stop_containers(  # noqa: SLF001 - focused lifecycle test
        is_empty_test_run=is_empty_test_run
    )

    scenario.weblog_infra.stop.assert_called_once_with(flush=flush)
