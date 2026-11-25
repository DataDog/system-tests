from threading import RLock
from unittest.mock import MagicMock

from utils import pytest

from utils import interfaces, scenarios
from utils._context._scenarios._core.endtoend import DdTraceEndToEndScenario, DockerScenario
from utils._context._scenarios.aws_lambda import _LambdaScenario
from utils._context._scenarios.open_telemetry import _OpenTelemetryScenario
from utils._context.containers import MsSqlServerContainer, TestedContainer as _TestedContainer

from .utils import extra_hosts_at_start


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
def test_main():
    events: list[str] = []

    class FakeScenario(DockerScenario):
        def __init__(self) -> None:
            super().__init__(name="fake_scenario", github_workflow=None)

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
            super().__init__(name="fake_scenario", github_workflow=None)

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
            super().__init__(name="fake_scenario", github_workflow=None)

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
        include_agent=include_agent,
        use_proxy_for_weblog=False,
    )
    scenario.replay = False
    scenario.library_interface_timeout = 0
    scenario.weblog_infra = MagicMock()
    monkeypatch.setattr(scenario, "_wait_interface", MagicMock())

    monkeypatch.setattr(interfaces.library, "check_deserialization_errors", MagicMock())
    monkeypatch.setattr(scenario, "_stop_mocked_backend", MagicMock())
    monkeypatch.setattr(interfaces.mocked_backend, "ingest_all_files", MagicMock())
    monkeypatch.setattr(interfaces.mocked_backend, "check_deserialization_errors", MagicMock())

    scenario._wait_and_stop_containers(  # noqa: SLF001 - focused lifecycle test
        is_empty_test_run=is_empty_test_run
    )

    scenario.weblog_infra.stop.assert_called_once_with(flush=flush)


@scenarios.test_the_test
def test_mocked_backend_agent_sends_to_the_mocked_backend_container(monkeypatch: pytest.MonkeyPatch) -> None:
    scenario = DdTraceEndToEndScenario("FAKE_MOCKED_BACKEND_V2")
    mocked_backend = scenario.mocked_backend_container
    assert mocked_backend in scenario._containers  # noqa: SLF001

    agent = scenario.agent_container
    # every intake hostname is derived from it, and is an alias of the mocked backend
    assert agent.environment["DD_SITE"] == "mocked-backend.invalid"
    assert agent.dd_site == "mocked-backend.invalid"
    assert "DD_DD_URL" not in agent.environment
    assert "DD_PROXY_HTTPS" not in agent.environment
    # reached by its name on the scenario network: no mapping to the docker host
    assert extra_hosts_at_start(monkeypatch, agent) is None

    weblog = MagicMock(depends_on=[])
    scenario.weblog_infra = MagicMock(get_weblog_containers=MagicMock(return_value=[weblog]))
    scenario._set_containers_dependancies()  # noqa: SLF001
    assert mocked_backend in agent.depends_on
    assert mocked_backend in weblog.depends_on


@scenarios.test_the_test
def test_open_telemetry_scenario_agent_sends_to_the_mocked_backend_container() -> None:
    scenario = _OpenTelemetryScenario("FAKE_OTEL", include_intake=False, include_collector=False)
    agent = scenario.agent_container
    # every intake hostname is derived from it, and is an alias of the mocked backend
    assert agent.environment["DD_SITE"] == "mocked-backend.invalid"
    assert "DD_PROXY_HTTPS" not in agent.environment
    assert scenario.mocked_backend_container in agent.depends_on
    # removed in reverse order: the agent stops before the mocked backend, that receives all it sends
    containers = scenario._containers  # noqa: SLF001
    assert containers.index(scenario.mocked_backend_container) < containers.index(agent)


@scenarios.test_the_test
def test_mocked_backend_does_not_make_the_weblog_databases_depend_on_it() -> None:
    # everything else depends on MsSql, so it starts alone: MsSql depending on the mocked backend would be a cycle
    scenario = DdTraceEndToEndScenario(
        "FAKE_MOCKED_BACKEND_MSSQL",
        other_weblog_containers=(MsSqlServerContainer,),
    )
    scenario._set_containers_dependancies()  # noqa: SLF001

    (mssql,) = [c for c in scenario.weblog_infra.get_containers() if isinstance(c, MsSqlServerContainer)]
    assert scenario.mocked_backend_container not in mssql.depends_on
    assert scenario.mocked_backend_container in scenario.weblog_container.depends_on


@scenarios.test_the_test
def test_lambda_extension_sends_to_the_mocked_backend_container() -> None:
    scenario = _LambdaScenario("FAKE_LAMBDA")
    weblog = scenario.lambda_weblog
    # every intake hostname is derived from it, and is an alias of the mocked backend
    assert weblog.environment["DD_SITE"] == "mocked-backend.invalid"
    assert "DD_PROXY_HTTPS" not in weblog.environment
    assert scenario.mocked_backend_container in weblog.depends_on
    # removed in reverse order: the weblog stops before the mocked backend, that receives all it sends
    containers = scenario._containers  # noqa: SLF001
    assert containers.index(scenario.mocked_backend_container) < containers.index(weblog)
