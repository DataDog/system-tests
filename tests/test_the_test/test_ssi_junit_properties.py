from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock

from utils import scenarios
from utils._context._scenarios.auto_injection import _VirtualMachineScenario
from utils._context._scenarios.k8s_lib_injection import K8sScenario
from utils._context.component_version import ComponentVersion, Version
from utils._context.junit_parameters import fingerprint_parameters
from utils.k8s.k8s_component_image import K8sComponentImage


def _aws_scenario(weblog: SimpleNamespace) -> _VirtualMachineScenario:
    scenario = _VirtualMachineScenario.__new__(_VirtualMachineScenario)
    scenario.name = "SIMPLE_AUTO_INJECTION_PROFILING"
    scenario._library = ComponentVersion("nodejs", "7.0.0-pre")  # noqa: SLF001
    scenario._weblog = "test-app-nodejs"  # noqa: SLF001
    scenario._datadog_apm_inject_version = "v0.73.0-dev.abc"  # noqa: SLF001
    scenario.components = {
        "agent": Version("7.85.4-1"),
        "datadog-apm-inject": Version("0.73.0-dev.abc"),
        "datadog-installer": Version("7.85.4-1"),
    }
    vm = Mock()
    vm.name = "AlmaLinux_9_amd64"
    vm.os_cpu = "amd64"
    vm.provision_install_error = None
    vm.tested_components = {"runtime_version": " 22.11.0"}
    vm.get_deployed_weblog.return_value = weblog
    scenario.virtual_machine = cast("Any", vm)
    return scenario


@scenarios.test_the_test
def test_aws_ssi_junit_properties_describe_the_machine() -> None:
    scenario = _aws_scenario(SimpleNamespace(app_type="host", runtime_version="22"))

    properties = scenario.get_junit_properties()
    parameters = fingerprint_parameters(properties)

    assert properties["os"] == "AlmaLinux_9"
    assert properties["arch"] == "amd64"
    assert properties["app_type"] == "host"
    assert properties["installed_language_runtime"] == "22.11.0"
    assert properties["datadog-apm-inject"] == {"version": "v0.73.0-dev.abc"}
    assert parameters["os"] == "AlmaLinux_9"
    assert parameters["app_type"] == "host"
    assert parameters["installed_language_runtime"] == "22.11.0"
    assert parameters["library"] == {"name": "nodejs"}
    assert "agent" not in parameters
    assert "datadog-apm-inject" not in parameters
    assert "datadog-installer" not in parameters


@scenarios.test_the_test
def test_aws_ssi_multicontainer_has_no_single_runtime() -> None:
    scenario = _aws_scenario(SimpleNamespace(app_type="multicontainer", runtime_version=None))

    properties = scenario.get_junit_properties()

    assert properties["app_type"] == "multicontainer"
    assert "installed_language_runtime" not in properties


@scenarios.test_the_test
def test_k8s_lib_injection_versions_stay_out_of_the_fingerprint() -> None:
    scenario = K8sScenario.__new__(K8sScenario)
    scenario.name = "K8S_LIB_INJECTION"
    scenario.k8s_weblog = "test-app-python"
    scenario._library = ComponentVersion("python", "2.5.0")  # noqa: SLF001
    scenario._datadog_apm_inject_version = "v0.73.0"  # noqa: SLF001
    scenario.k8s_cluster_img = K8sComponentImage("cluster:1", lambda _: "7.85.4")
    scenario.k8s_injector_img = K8sComponentImage("inject:1", lambda _: "0.73.0")
    scenario.k8s_helm_chart_version = "3.2.1"
    scenario.k8s_helm_chart_operator_version = None

    properties = scenario.get_junit_properties()
    parameters = fingerprint_parameters(properties)

    assert parameters == {
        "scenario": "K8S_LIB_INJECTION",
        "weblog_variant": "test-app-python",
        "library": {"name": "python"},
    }
    assert properties["k8s_cluster_agent"] == {"version": "7.85.4"}
    assert properties["datadog-apm-inject"] == {"version": "v0.73.0"}
    assert properties["k8s_helm_chart"] == {"version": "3.2.1"}
