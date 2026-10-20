from unittest.mock import MagicMock, patch

from docker.types import Mount

from utils import scenarios
from utils._context.containers import TestedContainer as _TestedContainer


@scenarios.test_the_test
def test_container_forwards_cgroupns_and_mounts_to_docker() -> None:
    mounts = [Mount(target="/host/proc", source="/some/proc", type="bind", read_only=True)]
    container = _TestedContainer(name="cgroup-config-test", image_name="unused", cgroupns="host", mounts=mounts)
    client = MagicMock()
    with (
        patch("utils._context.containers.get_docker_client", return_value=client),
        patch.object(container, "get_existing_container", return_value=None),
        patch.object(container, "wait_for_health", return_value=False),
    ):
        container.start(MagicMock())

    kwargs = client.containers.run.call_args.kwargs
    assert kwargs["cgroupns"] == "host"
    assert kwargs["mounts"] == mounts
