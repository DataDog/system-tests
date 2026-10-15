from collections.abc import Iterator
from typing import Protocol
from unittest.mock import MagicMock, patch

from docker.types import Mount

from utils import pytest, scenarios
from utils._context._scenarios.endtoend import EndToEndScenario
from utils._context._scenarios.thread_context_sharing import ThreadContextSharingScenario

OPT_IN_VARIABLE = "SYSTEM_TESTS_CWS_GUEST_KERNEL_MOUNTS"


class ScenarioFactory(Protocol):
    def __call__(self, value: str | None) -> ThreadContextSharingScenario: ...


@pytest.fixture
def configured_scenario(monkeypatch: pytest.MonkeyPatch) -> Iterator[ScenarioFactory]:
    """Configure a fresh THREAD_CONTEXT_SHARING scenario with the opt-in variable set to the given
    value (None: unset), skipping the parent end-to-end configuration, which needs docker images.
    """
    created: list[ThreadContextSharingScenario] = []

    def factory(value: str | None) -> ThreadContextSharingScenario:
        if value is None:
            monkeypatch.delenv(OPT_IN_VARIABLE, raising=False)
        else:
            monkeypatch.setenv(OPT_IN_VARIABLE, value)
        scenario = ThreadContextSharingScenario("CWS_CONFIG_TEST", "")
        created.append(scenario)
        with patch.object(EndToEndScenario, "configure", MagicMock()):
            scenario.configure(MagicMock())
        return scenario

    yield factory

    # Scenario.__init__ registers every instance in its groups; do not leak test instances
    for scenario in created:
        for group in scenario.scenario_groups:
            group.scenarios.remove(scenario)


@scenarios.test_the_test
def test_default_uses_docker_host_kernel_filesystems(configured_scenario: ScenarioFactory) -> None:
    agent = configured_scenario(None).agent_container

    assert agent.pid_mode == "host"
    assert agent.cgroupns == "host"
    assert agent.mounts is None
    assert agent.volumes["/sys/kernel/debug"] == {"bind": "/sys/kernel/debug", "mode": "rw"}
    assert agent.volumes["/sys/kernel/security"] == {"bind": "/sys/kernel/security", "mode": "rw"}


@scenarios.test_the_test
def test_v1_uses_guest_kernel_mounts(configured_scenario: ScenarioFactory) -> None:
    agent = configured_scenario("v1").agent_container

    assert agent.cgroupns == "host"
    assert agent.mounts == [
        Mount(target="/host/proc", source="/vm-host/proc", type="bind", read_only=True),
        Mount(target="/host/sys/fs/cgroup", source="/vm-host/sys/fs/cgroup", type="bind", read_only=True),
        Mount(target="/sys/kernel/debug", source="/vm-host/sys/kernel/debug", type="bind", read_only=False),
        Mount(target="/sys/kernel/tracing", source="/vm-host/sys/kernel/tracing", type="bind", read_only=False),
        Mount(target="/sys/kernel/security", source="/vm-host/sys/kernel/security", type="bind", read_only=False),
    ]
    assert "/sys/kernel/debug" not in agent.volumes
    assert "/sys/kernel/security" not in agent.volumes
    assert agent.environment["DD_RUNTIME_SECURITY_CONFIG_ENFORCEMENT_ENABLED"] == "false"


@scenarios.test_the_test
def test_invalid_opt_in_value_is_an_error(configured_scenario: ScenarioFactory) -> None:
    with pytest.raises(pytest.exit.Exception, match=OPT_IN_VARIABLE):
        configured_scenario("v2")
