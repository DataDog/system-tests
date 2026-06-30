from utils import scenarios, features, context, bug, logger
from tests.k8s_lib_injection.utils import get_dev_agent_traces, get_cluster_info, run_https_probe_pod
from utils.onboarding.weblog_interface import make_get_request, warmup_weblog
from utils.onboarding.backend_interface import wait_backend_trace_id
from utils.onboarding.wait_for_tcp_port import wait_for_port


@features.k8s_admission_controller
@scenarios.k8s_lib_injection
@scenarios.k8s_lib_injection_uds
@scenarios.k8s_lib_injection_no_ac
@scenarios.k8s_lib_injection_no_ac_uds
class TestK8sLibInjection:
    """Test K8s lib injection"""

    @bug(context.library >= "python@2.20.0" and context.k8s_cluster_agent_version == "7.56.2", reason="APMSP-1750")
    @bug(context.library in ("nodejs", "ruby") and context.k8s_cluster_agent_version == "7.56.2", reason="APMSP-2215")
    def test_k8s_lib_injection(self):
        traces_json = get_dev_agent_traces(get_cluster_info())
        assert len(traces_json) > 0, "No traces found"

    def test_k8s_init_container_https_egress(self):
        """The init image must be able to complete a TLS-verified HTTPS request.

        The init container ships a CA trust store so admission-controller wrappers that dial
        HTTPS from inside it (e.g. bank-vaults' vault-env) keep working. This runs a throwaway
        pod from the init image doing `curl -fsS https://...` (verification on) and asserts it
        succeeds; a missing or broken cert store makes curl exit non-zero.
        """
        image = context.scenario.test_weblog.library_init_image
        phase, logs = run_https_probe_pod(get_cluster_info(), image, "https://app.datadoghq.com")
        if phase != "Succeeded":
            logger.error(f"[HTTPS probe] init image {image} failed HTTPS egress; pod logs:\n{logs}")
        assert phase == "Succeeded", f"init image could not complete a verified HTTPS request (pod phase: {phase})"


@features.k8s_admission_controller
@scenarios.k8s_lib_injection_operator
class TestK8sLibInjection_operator:
    """Test K8s lib injection using the operator"""

    @bug(context.library > "python@2.21.0" and context.k8s_cluster_agent_version == "7.56.2", reason="APMSP-1750")
    @bug(context.library in ("nodejs", "ruby") and context.k8s_cluster_agent_version == "7.56.2", reason="APMSP-2215")
    def test_k8s_lib_injection(self):
        cluster_info = get_cluster_info()
        context_url = f"http://{cluster_info.cluster_host_name}:{cluster_info.get_weblog_port()}/"
        logger.info(f"Waiting for weblog available [{cluster_info.cluster_host_name}:{cluster_info.get_weblog_port()}]")
        assert wait_for_port(cluster_info.get_weblog_port(), cluster_info.cluster_host_name, 80.0), (
            "Weblog port not reachable. Is the weblog running?"
        )
        logger.info(f"[{cluster_info.cluster_host_name}]: Weblog app is ready!")
        warmup_weblog(context_url)
        request_uuid = make_get_request(context_url)
        logger.info(f"Http request done with uuid: [{request_uuid}] for ip [{cluster_info.cluster_host_name}]")
        wait_backend_trace_id(request_uuid)
