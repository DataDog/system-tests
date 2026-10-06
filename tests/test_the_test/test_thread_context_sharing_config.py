from collections.abc import Iterator
from typing import Protocol
from unittest.mock import MagicMock, call, patch

from docker.errors import APIError
from docker.types import Mount

from tests.cws.utils import cws_self_test_succeeded
from utils import interfaces, pytest, scenarios
from utils._context._scenarios.endtoend import EndToEndScenario
from utils._context._scenarios.thread_context_sharing import ThreadContextSharingScenario
from utils._context.containers import AgentContainer, TestedContainer as _TestedContainer

OPT_IN_VARIABLE = "SYSTEM_TESTS_CWS_GUEST_KERNEL_MOUNTS"


class ScenarioFactory(Protocol):
    def __call__(
        self, value: str | None, parent_configure: MagicMock | None = None
    ) -> ThreadContextSharingScenario: ...


# What THREAD_CONTEXT_SHARING adds to the agent container when it is not opted in. This mirrors
# the configuration from before the opt-in existed, and must stay byte-for-byte identical.
DEFAULT_SCENARIO_VOLUMES = {
    "./utils/build/docker/agent/runtime-security.d": {
        "bind": "/etc/datadog-agent/runtime-security.d",
        "mode": "ro",
    },
    "/etc/passwd": {"bind": "/etc/passwd", "mode": "ro"},
    "/etc/group": {"bind": "/etc/group", "mode": "ro"},
    "/sys/kernel/debug": {"bind": "/sys/kernel/debug", "mode": "rw"},
    "/sys/kernel/security": {"bind": "/sys/kernel/security", "mode": "rw"},
}
DEFAULT_SCENARIO_ENVIRONMENT = {
    "DD_RUNTIME_SECURITY_CONFIG_ENABLED": "true",
    "DD_RUNTIME_SECURITY_CONFIG_SPAN_TRACKING_ENABLED": "true",
    "DD_RUNTIME_SECURITY_CONFIG_SELF_TEST_ENABLED": "true",
}
DEFAULT_CAP_ADD = ["SYS_ADMIN", "SYS_RESOURCE", "SYS_PTRACE", "NET_ADMIN", "NET_BROADCAST", "IPC_LOCK", "CHOWN"]

GUEST_KERNEL_MOUNTS_V1 = [
    Mount(target="/host/proc", source="/vm-host/proc", type="bind", read_only=True),
    Mount(target="/host/sys/fs/cgroup", source="/vm-host/sys/fs/cgroup", type="bind", read_only=True),
    Mount(target="/sys/kernel/debug", source="/vm-host/sys/kernel/debug", type="bind", read_only=False),
    Mount(target="/sys/kernel/tracing", source="/vm-host/sys/kernel/tracing", type="bind", read_only=False),
    Mount(target="/sys/kernel/security", source="/vm-host/sys/kernel/security", type="bind", read_only=False),
    Mount(target="/opt/system-tests/vm-host-ready-v1", source="/vm-host/.ready-v1", type="bind", read_only=True),
]


@pytest.fixture
def configured_scenario(monkeypatch: pytest.MonkeyPatch) -> Iterator[ScenarioFactory]:
    """Build and configure a fresh THREAD_CONTEXT_SHARING scenario with the opt-in variable set
    to the given value (None: unset). The parent end-to-end configuration, which needs docker
    images and a logs folder, is skipped: only what this scenario adds is under test.
    """
    created: list[ThreadContextSharingScenario] = []

    def factory(value: str | None, parent_configure: MagicMock | None = None) -> ThreadContextSharingScenario:
        if value is None:
            monkeypatch.delenv(OPT_IN_VARIABLE, raising=False)
        else:
            monkeypatch.setenv(OPT_IN_VARIABLE, value)

        scenario = ThreadContextSharingScenario("CWS_CONFIG_TEST", "")
        created.append(scenario)
        with patch.object(EndToEndScenario, "configure", parent_configure or MagicMock()):
            scenario.configure(MagicMock())
        return scenario

    yield factory

    # Scenario.__init__ registers every instance in its groups; do not leak test instances
    for scenario in created:
        for group in scenario.scenario_groups:
            group.scenarios.remove(scenario)


def _assert_untouched(container: _TestedContainer, pristine: _TestedContainer) -> None:
    assert container.cgroupns is None
    assert container.mounts is None
    assert container.pid_mode == pristine.pid_mode
    assert container.volumes == pristine.volumes
    assert "warmup" not in vars(container)
    assert "start" not in vars(container)


@scenarios.test_the_test
@pytest.mark.parametrize("value", [None, ""])
def test_opted_out_configuration_is_unchanged(configured_scenario: ScenarioFactory, value: str | None) -> None:
    scenario = configured_scenario(value)
    agent = scenario.agent_container
    pristine_agent = AgentContainer()

    assert agent.pid_mode == "host"
    assert agent.cgroupns is None
    assert agent.mounts is None
    assert agent.cap_add == DEFAULT_CAP_ADD
    assert agent.security_opt == ["apparmor:unconfined"]
    assert agent.volumes == {**pristine_agent.volumes, **DEFAULT_SCENARIO_VOLUMES}
    assert agent.environment == {**pristine_agent.environment, **DEFAULT_SCENARIO_ENVIRONMENT}
    # no readiness or error wrappers: the agent keeps its class' methods
    assert "warmup" not in vars(agent)
    assert "start" not in vars(agent)


@scenarios.test_the_test
def test_v1_uses_guest_kernel_mounts(configured_scenario: ScenarioFactory) -> None:
    scenario = configured_scenario("v1")
    agent = scenario.agent_container
    pristine_agent = AgentContainer()

    assert agent.pid_mode == "host"
    assert agent.cgroupns == "host"
    assert agent.mounts == GUEST_KERNEL_MOUNTS_V1
    assert agent.cap_add == DEFAULT_CAP_ADD
    assert agent.security_opt == ["apparmor:unconfined"]

    # The kernel filesystems come from the Kata guest through /vm-host only: no bind of the
    # (DIND) container's own /sys/kernel/*, which would also clash with the mounts' targets.
    expected_volumes = {**pristine_agent.volumes, **DEFAULT_SCENARIO_VOLUMES}
    del expected_volumes["/sys/kernel/debug"]
    del expected_volumes["/sys/kernel/security"]
    assert agent.volumes == expected_volumes

    # enforcement must never be enabled in this topology; no debug logging by default
    assert agent.environment == {
        **pristine_agent.environment,
        **DEFAULT_SCENARIO_ENVIRONMENT,
        "DD_RUNTIME_SECURITY_CONFIG_ENFORCEMENT_ENABLED": "false",
    }


@scenarios.test_the_test
@pytest.mark.parametrize("value", ["v2", "V1", "1", "true", " v1", "v1 "])
def test_invalid_opt_in_value_is_an_error(configured_scenario: ScenarioFactory, value: str) -> None:
    parent_configure = MagicMock()
    # pytest.exit, as other scenarios do for configuration errors: pytest prints the message
    # alone, where an exception from pytest_configure would be an INTERNALERROR traceback
    with pytest.raises(pytest.exit.Exception, match=OPT_IN_VARIABLE) as excinfo:
        configured_scenario(value, parent_configure)

    assert excinfo.value.returncode == 1

    # fails before the parent configuration, which e.g. requires the weblog image to exist
    parent_configure.assert_not_called()


@scenarios.test_the_test
def test_v1_agent_warmup_waits_for_cws_self_test(configured_scenario: ScenarioFactory) -> None:
    events = MagicMock()
    with patch.object(AgentContainer, "warmup", events.agent_warmup):
        scenario = configured_scenario("v1")

    with patch.object(interfaces.agent, "wait_for", events.wait_for) as wait_for:
        wait_for.return_value = True
        scenario.agent_container.warmup()

    # the agent's own warmup first, then CWS readiness, so that the weblog (which depends on
    # the agent) only starts once CWS can see it
    assert events.mock_calls == [call.agent_warmup(), call.wait_for(cws_self_test_succeeded, timeout=90)]


@scenarios.test_the_test
def test_v1_agent_warmup_fails_when_cws_is_not_ready(configured_scenario: ScenarioFactory) -> None:
    scenario = configured_scenario("v1")

    with (
        patch.object(interfaces.agent, "wait_for", return_value=False),
        pytest.raises(RuntimeError) as excinfo,
    ):
        scenario.agent_container.warmup()

    _assert_explains_guest_kernel_mounts(str(excinfo.value))
    assert "self test" in str(excinfo.value)


def _assert_explains_guest_kernel_mounts(message: str) -> None:
    assert OPT_IN_VARIABLE in message
    assert "/vm-host/.ready-v1" in message
    assert "docker-in-docker" in message
    assert "io.katacontainers.datadog.guest-kernel-mounts=v1" in message
    assert "dmesg | grep 'kata-agent: hook failed'" in message


@scenarios.test_the_test
def test_v1_missing_guest_kernel_mounts_are_explained(configured_scenario: ScenarioFactory) -> None:
    missing = APIError(
        "500 Server Error",
        explanation='invalid mount config for type "bind": bind source path does not exist: /vm-host/.ready-v1',
    )
    with patch.object(AgentContainer, "start", side_effect=missing):
        scenario = configured_scenario("v1")

    with patch(f"{ThreadContextSharingScenario.__module__}.logger") as logger, pytest.raises(RuntimeError) as excinfo:
        scenario.agent_container.start(MagicMock())

    _assert_explains_guest_kernel_mounts(str(excinfo.value))
    assert "bind source path does not exist: /vm-host/.ready-v1" in str(excinfo.value)
    assert excinfo.value.__cause__ is missing
    # the framework only logs a start exception to tests.log, and shows a generic "can't be
    # started" on the console, so the explanation is also written to the console
    logger.stdout.assert_called_once_with(str(excinfo.value))


@scenarios.test_the_test
def test_v1_other_agent_start_errors_are_unchanged(configured_scenario: ScenarioFactory) -> None:
    other = APIError("500 Server Error", explanation="no space left on device")
    with patch.object(AgentContainer, "start", side_effect=other):
        scenario = configured_scenario("v1")

    with pytest.raises(APIError) as excinfo:
        scenario.agent_container.start(MagicMock())

    assert excinfo.value is other


@scenarios.test_the_test
@pytest.mark.parametrize("value", [None, "v1"])
def test_proxy_and_weblog_are_unaffected(configured_scenario: ScenarioFactory, value: str | None) -> None:
    scenario = configured_scenario(value)
    pristine = configured_scenario(None)

    _assert_untouched(scenario.proxy_container, pristine.proxy_container)
    _assert_untouched(scenario.weblog_infra.http_container, pristine.weblog_infra.http_container)
    assert scenario.proxy_container.environment == pristine.proxy_container.environment
    assert scenario.weblog_infra.http_container.environment == pristine.weblog_infra.http_container.environment
