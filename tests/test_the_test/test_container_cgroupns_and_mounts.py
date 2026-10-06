from unittest.mock import MagicMock, patch

from docker.types import HostConfig, Mount

from utils import pytest, scenarios
from utils._context.containers import TestedContainer as _TestedContainer

MOUNTS = [
    Mount(target="/host/proc", source="/some/proc", type="bind", read_only=True),
    Mount(target="/sys/kernel/debug", source="/some/debug", type="bind", read_only=False),
]


@scenarios.test_the_test
@pytest.mark.parametrize(("cgroupns", "mounts"), [(None, None), ("host", MOUNTS), ("private", None)])
def test_container_forwards_cgroupns_and_mounts_to_docker(cgroupns: str | None, mounts: list[Mount] | None) -> None:
    container = _TestedContainer(name="cgroup-config-test", image_name="unused", cgroupns=cgroupns, mounts=mounts)
    client = MagicMock()
    with (
        patch("utils._context.containers.get_docker_client", return_value=client),
        patch.object(container, "get_existing_container", return_value=None),
        patch.object(container, "wait_for_health", return_value=False),
    ):
        container.start(MagicMock())

    kwargs = client.containers.run.call_args.kwargs
    assert kwargs["cgroupns"] == cgroupns
    assert kwargs["mounts"] == mounts

    # Exercise the pinned SDK's actual host-config serialization, without a daemon: unset
    # values must be omitted, so that the daemon defaults stay in effect for every container
    # that does not ask for them.
    host_config = HostConfig(version="1.41", cgroupns=kwargs["cgroupns"], mounts=kwargs["mounts"])
    if cgroupns is None:
        assert "CgroupnsMode" not in host_config
    else:
        assert host_config["CgroupnsMode"] == cgroupns
    if mounts is None:
        assert "Mounts" not in host_config
    else:
        assert host_config["Mounts"] == [
            {"Target": "/host/proc", "Source": "/some/proc", "Type": "bind", "ReadOnly": True},
            {"Target": "/sys/kernel/debug", "Source": "/some/debug", "Type": "bind", "ReadOnly": False},
        ]


@scenarios.test_the_test
def test_container_defaults_leave_cgroupns_and_mounts_unset() -> None:
    container = _TestedContainer(name="cgroup-config-test", image_name="unused")
    assert container.cgroupns is None
    assert container.mounts is None
