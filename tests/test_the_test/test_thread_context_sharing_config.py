from collections.abc import Iterator
from pathlib import Path
from typing import Protocol
from unittest.mock import MagicMock, patch

from docker.types import Mount

from utils import pytest, scenarios
from utils._context._scenarios.endtoend import EndToEndScenario
from utils._context._scenarios import thread_context_sharing
from utils._context._scenarios.thread_context_sharing import ThreadContextSharingScenario

VM_HOST_DIRS = ["proc", "sys/fs/cgroup", "sys/kernel/debug", "sys/kernel/tracing", "sys/kernel/security"]


class ScenarioFactory(Protocol):
    def __call__(self, vm_host_dirs: list[str] | None) -> ThreadContextSharingScenario: ...


@pytest.fixture
def vm_host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "vm-host"
    monkeypatch.setattr(thread_context_sharing, "VM_HOST", str(path))
    return path


@pytest.fixture
def configured_scenario(vm_host: Path) -> Iterator[ScenarioFactory]:
    """Configure a fresh THREAD_CONTEXT_SHARING scenario with a fake /vm-host holding the given
    directories (None: no /vm-host), skipping the parent end-to-end configuration, which needs
    docker images.
    """
    created: list[ThreadContextSharingScenario] = []

    def factory(vm_host_dirs: list[str] | None) -> ThreadContextSharingScenario:
        if vm_host_dirs is not None:
            vm_host.mkdir()
            for path in vm_host_dirs:
                (vm_host / path).mkdir(parents=True)
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
def test_vm_host_uses_guest_kernel_mounts(configured_scenario: ScenarioFactory, vm_host: Path) -> None:
    agent = configured_scenario(VM_HOST_DIRS).agent_container

    assert agent.cgroupns == "host"
    assert agent.mounts == [
        Mount(target="/host/proc", source=f"{vm_host}/proc", type="bind", read_only=True),
        Mount(target="/host/sys/fs/cgroup", source=f"{vm_host}/sys/fs/cgroup", type="bind", read_only=True),
        Mount(target="/sys/kernel/debug", source=f"{vm_host}/sys/kernel/debug", type="bind", read_only=False),
        Mount(target="/sys/kernel/tracing", source=f"{vm_host}/sys/kernel/tracing", type="bind", read_only=False),
        Mount(target="/sys/kernel/security", source=f"{vm_host}/sys/kernel/security", type="bind", read_only=False),
    ]
    assert "/sys/kernel/debug" not in agent.volumes
    assert "/sys/kernel/security" not in agent.volumes
    assert agent.environment["DD_RUNTIME_SECURITY_CONFIG_ENFORCEMENT_ENABLED"] == "false"


@scenarios.test_the_test
def test_incomplete_vm_host_is_an_error(configured_scenario: ScenarioFactory) -> None:
    with pytest.raises(pytest.exit.Exception, match="lacks sys/kernel/tracing"):
        configured_scenario([path for path in VM_HOST_DIRS if path != "sys/kernel/tracing"])
