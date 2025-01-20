from utils import scenarios, features, context
from tests.k8s_lib_injection.utils import get_dev_agent_traces
from utils.tools import logger
from utils.onboarding.weblog_interface import make_get_request, warmup_weblog
from utils.onboarding.backend_interface import wait_backend_trace_id
from utils.onboarding.wait_for_tcp_port import wait_for_port


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


@features.k8s_admission_controller
@scenarios.k8s_lib_injection_operator
class TestK8sLibInjection_operator(_TestK8sLibInjection):
    """Test K8s lib injection using the operator"""

    def test_k8s_lib_injection(self):
        cluster_info = context.scenario.k8s_cluster_provider.get_cluster_info()
        context_url = f"http://{cluster_info.cluster_host_name}:{cluster_info.weblog_port}/"
        logger.info(f"Waiting for weblog available [{cluster_info.cluster_host_name}:{cluster_info.weblog_port}]")
        wait_for_port(cluster_info.weblog_port, cluster_info.cluster_host_name, 80.0)
        logger.info(f"[{cluster_info.cluster_host_name}]: Weblog app is ready!")
        warmup_weblog(context_url)
        request_uuid = make_get_request(context_url)
        logger.info(f"Http request done with uuid: [{request_uuid}] for ip [{cluster_info.cluster_host_name}]")
        wait_backend_trace_id(request_uuid, 120.0)
