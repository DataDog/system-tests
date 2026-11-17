"""K8S_LIB_INJECTION_OPERATOR on kind: the agents deployed by the operator send their payloads to the mocked backend."""

from pathlib import Path

import yaml

from utils import pytest, scenarios
from utils.k8s_lib_injection import k8s_cluster_provider
from utils.k8s_lib_injection.k8s_cluster_provider import K8sProviderFactory, PrivateRegistryConfig
from utils.k8s_lib_injection.k8s_datadog_kubernetes import add_cluster_agent_img_operator_yaml

_CLUSTER_AGENT_IMG = "gcr.io/datadoghq/cluster-agent:7.85.0"


def _datadog_agent_spec(tmp_path: Path, backend_url: str | None) -> dict:
    output_file = add_cluster_agent_img_operator_yaml(_CLUSTER_AGENT_IMG, str(tmp_path), backend_url=backend_url)
    return yaml.safe_load(Path(output_file).read_text())["spec"]


@pytest.fixture(autouse=True)
def _no_private_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PrivateRegistryConfig, "is_configured", classmethod(lambda _: False))


@scenarios.test_the_test
def test_operator_agents_send_to_the_mocked_backend(tmp_path: Path) -> None:
    spec = _datadog_agent_spec(tmp_path, "http://192.168.5.2:4900")

    # the operator sets DD_DD_URL on every agent from it
    assert spec["global"]["endpoint"] == {"url": "http://192.168.5.2:4900"}
    # the trace agent doesn't derive its intake from DD_DD_URL
    assert spec["override"]["nodeAgent"]["env"] == [
        {"name": "DD_APM_DD_URL", "value": "http://192.168.5.2:4900"},
        {"name": "DD_APM_PROFILING_DD_URL", "value": "http://192.168.5.2:4900/api/v2/profile"},
    ]
    assert spec["override"]["clusterAgent"]["image"] == {"name": _CLUSTER_AGENT_IMG}


@scenarios.test_the_test
def test_operator_agents_send_to_the_real_backend_without_mocked_backend(tmp_path: Path) -> None:
    spec = _datadog_agent_spec(tmp_path, None)

    assert "endpoint" not in spec["global"]
    assert spec["override"] == {"clusterAgent": {"image": {"name": _CLUSTER_AGENT_IMG}}}


@scenarios.test_the_test
@pytest.mark.parametrize("provider_id", ["minikube", "eksremote"])
def test_only_kind_supports_the_mocked_backend(provider_id: str) -> None:
    assert K8sProviderFactory().get_provider("kind").supports_mocked_backend
    assert not K8sProviderFactory().get_provider(provider_id).supports_mocked_backend


@scenarios.test_the_test
def test_kind_exposes_the_mocked_backend_port_to_the_pods(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITLAB_CI", raising=False)
    commands: list[str] = []

    def execute_command(command: str, *_args: object, **_kwargs: object) -> str:
        commands.append(command)
        # host.docker.internal first, then the default gateway of the node
        return "192.168.5.2\n172.18.0.1\n" if "getent" in command else ""

    monkeypatch.setattr(k8s_cluster_provider, "execute_command", execute_command)
    provider = K8sProviderFactory().get_provider("kind")
    provider.configure()

    assert provider.expose_mocked_backend(4900) == "192.168.5.2"
    # the kind node redirects all the traffic sent to the docker host to the docker DNS, except this port
    assert commands[-1].startswith("docker exec lib-injection-testing-control-plane ")
    assert "iptables -t nat -I DOCKER_OUTPUT -d 192.168.5.2 -p tcp --dport 4900 -j RETURN" in commands[-1]
