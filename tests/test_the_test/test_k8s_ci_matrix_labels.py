"""GitLab K8s matrix values omit the ECR host. The job puts the registry back."""

from utils import pytest, scenarios
from utils._context._scenarios import get_all_scenarios
from utils.k8s.k8s_components_parser import K8sComponentsParser
from utils.scripts.ci_orchestrators.gitlab_exporter import (
    _short_image_ref,
    get_k8s_scenario_components,
    print_k8s_gitlab_pipeline,
)

_IMAGE_ENV = ("K8S_INJECTOR_IMG", "K8S_LIB_INIT_IMG", "K8S_WEBLOG_IMG")


def _clear_image_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _IMAGE_ENV:
        monkeypatch.delenv(name, raising=False)


@scenarios.test_the_test
def test_short_image_ref_drops_only_the_ecr_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRIVATE_DOCKER_REGISTRY", raising=False)
    host = "235494822917.dkr.ecr.us-east-1.amazonaws.com"
    assert _short_image_ref(f"{host}/ssi/cluster-agent:7.84.3") == "ssi/cluster-agent:7.84.3"
    assert _short_image_ref(f"{host}/ssi-dev/cluster-agent-dev:master") == "ssi-dev/cluster-agent-dev:master"
    assert _short_image_ref("3.257.1") == "3.257.1"
    custom = "my-registry/my-lib-init:my-tag"
    assert _short_image_ref(custom) == custom
    other_account = "486234852809.dkr.ecr.us-east-1.amazonaws.com/ssi/apm-inject:abc"
    assert _short_image_ref(other_account) == other_account
    other_path = f"{host}/team/custom:tag"
    assert _short_image_ref(other_path) == other_path


@scenarios.test_the_test
def test_matrix_job_name_uses_the_image_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CI_PROJECT_NAME", "system-tests")
    monkeypatch.setenv("CI_PIPELINE_SOURCE", "push")
    monkeypatch.delenv("PRIVATE_DOCKER_REGISTRY", raising=False)
    _clear_image_env(monkeypatch)

    matrix = get_k8s_scenario_components("K8S_LIB_INJECTION_PROFILING_ENABLED", get_all_scenarios(), "php")
    parser = K8sComponentsParser()
    cluster = parser.get_default_component_version("cluster_agent")
    helm = parser.get_default_component_version("helm_chart")

    assert matrix["K8S_CLUSTER_IMG"] == cluster.split("/", 1)[1]
    assert matrix["K8S_HELM_CHART"] == helm
    assert matrix["K8S_INJECTOR_IMG"] == [
        item.split("/", 1)[1] for item in parser.get_all_component_versions("injector")
    ]
    assert "235494822917" not in str(matrix)
    assert "${PRIVATE_DOCKER_REGISTRY}" not in str(matrix)

    pipeline: dict = {"stages": []}
    print_k8s_gitlab_pipeline(
        "php",
        {"K8S_LIB_INJECTION_PROFILING_ENABLED": ["dd-lib-php-init-test-app"]},
        "dev",
        pipeline,
    )
    entry = pipeline["K8S_LIB_INJECTION_PROFILING_ENABLED"]["parallel"]["matrix"][0]
    assert entry["K8S_WEBLOG"] == "dd-lib-php-init-test-app"
    assert "K8S_WEBLOG_IMG" not in entry
