from utils import scenarios, features, context
from tests.k8s_lib_injection.utils import get_dev_agent_traces


class _TestK8sLibInjection:
    """Test K8s lib injection"""

    def test_k8s_lib_injection(self):
        traces_json = get_dev_agent_traces(context.scenario.k8s_cluster_provider.get_cluster_info())
        assert len(traces_json) > 0, "No traces found"


@features.k8s_admission_controller
@scenarios.k8s_lib_injection
class TestK8sLibInjection(_TestK8sLibInjection):
    """Test K8s lib injection with admission controller"""

    pass


@features.k8s_admission_controller
@scenarios.k8s_lib_injection_uds
class TestK8sLibInjectionUDS(_TestK8sLibInjection):
    """Test K8s lib injection with admission controller and UDS"""

    pass


@features.k8s_admission_controller
@scenarios.k8s_lib_injection_no_ac
class TestK8sLibInjectionNoAC(_TestK8sLibInjection):
    """Test K8s lib injection without admission controller"""

    pass


@features.k8s_admission_controller
@scenarios.k8s_lib_injection_no_ac_uds
class TestK8sLibInjectionNoAC_UDS(_TestK8sLibInjection):
    """Test K8s lib injection without admission controller and UDS"""

    pass
