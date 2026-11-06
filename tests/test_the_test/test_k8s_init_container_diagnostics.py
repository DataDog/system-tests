from pathlib import Path

from kubernetes import client

from utils import pytest, scenarios
from utils.k8s_lib_injection.k8s_cluster_provider import K8sClusterInfo
from utils.k8s_lib_injection.k8s_weblog import K8sWeblog


class _FakeCoreV1Api:
    def __init__(self, pod: client.V1Pod) -> None:
        self.pod = pod
        self.log_calls: list[tuple[str, bool]] = []

    def read_namespaced_pod_status(self, name: str, namespace: str) -> client.V1Pod:
        assert name == "my-app"
        assert namespace == "default"
        return self.pod

    def read_namespaced_pod_log(self, name: str, namespace: str, container: str, *, previous: bool = False) -> str:
        assert name == "my-app"
        assert namespace == "default"
        self.log_calls.append((container, previous))
        return "previous attempt logs" if previous else "current attempt logs"


@scenarios.test_the_test
def test_init_container_diagnostics_capture_each_attempt_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    container_name = "datadog-lib-python-init"
    init_status = client.V1ContainerStatus(
        image="registry.example/dd-lib-python-init:latest",
        image_id="registry.example/dd-lib-python-init@sha256:digest",
        name=container_name,
        ready=True,
        restart_count=1,
        state=client.V1ContainerState(terminated=client.V1ContainerStateTerminated(exit_code=0, reason="Completed")),
    )
    pod = client.V1Pod(status=client.V1PodStatus(init_container_statuses=[init_status]))
    api = _FakeCoreV1Api(pod)
    cluster_info = K8sClusterInfo()
    monkeypatch.setattr(cluster_info, "core_v1_api", lambda: api)

    weblog = K8sWeblog(
        "registry.example/app:latest",
        "python",
        "registry.example/dd-lib-python-init:latest",
        "registry.example/apm-inject:latest",
        str(tmp_path),
    )
    weblog.configure(cluster_info)

    weblog.capture_init_container_diagnostics("my-app", "default", capture_current=True)
    weblog.capture_init_container_diagnostics("my-app", "default", capture_current=True)

    assert api.log_calls == [(container_name, True), (container_name, False)]
    assert (tmp_path / f"myapp.init-{container_name}.attempt-0.log").read_text() == "previous attempt logs\n"
    assert (tmp_path / f"myapp.init-{container_name}.attempt-1.log").read_text() == "current attempt logs\n"
    status_log = (tmp_path / "myapp.init-container-status.log").read_text()
    assert "'restart_count': 1" in status_log
    assert "sha256:digest" in status_log
