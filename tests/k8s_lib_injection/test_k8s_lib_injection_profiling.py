import time
import requests

from utils import scenarios, features, bug, context
from tests.k8s_lib_injection.utils import get_cluster_info


class _TestK8sLibInjectionProfiling:
    """Test profiling activation with the admission controller."""

    def _check_profiling_request_sent(self, k8s_cluster_info, timeout=90):
        """Use test agent profiling endpoint to check if the profiling data has been sent by the injectect library.
        Checks the request made to the profiling endpoint (/profiling/v1/input).
        The profiling post data can take between 12 and 90 seconds (12 if the library supports both env vars, 90 if it supports neither.
        """
        mustend = time.time() + timeout
        while time.time() < mustend:
            response = requests.get(
                f"http://{k8s_cluster_info.cluster_host_name}:{k8s_cluster_info.get_agent_port()}/test/session/requests",
                timeout=60,
            )
            for request in response.json():
                if request["url"].endswith("/profiling/v1/input"):
                    return True
            time.sleep(1)
        return False


@features.k8s_admission_controller
@scenarios.k8s_lib_injection_profiling_disabled
class TestK8sLibInjectioProfilingDisabledByDefault(_TestK8sLibInjectionProfiling):
    """Test K8s lib injection that should not send profiling data by default."""

    def test_profiling_disabled_by_default(self):
        profiling_request_found = self._check_profiling_request_sent(get_cluster_info())
        assert not profiling_request_found, "Profiling should be disabled by default, but a profiling request was found"


@features.k8s_admission_controller
@scenarios.k8s_lib_injection_profiling_enabled
class TestK8sLibInjectioProfilingClusterEnabled(_TestK8sLibInjectionProfiling):
    """Test K8s lib injection with profiling enabled."""

    @bug(context.library > "python@2.12.2" and context.library < "python@3.10.0", reason="APMON-1496")
    def test_profiling_admission_controller(self):
        profiling_request_found = self._check_profiling_request_sent(get_cluster_info())
        assert profiling_request_found, "No profiling request found"


@features.k8s_admission_controller
@scenarios.k8s_lib_injection_profiling_override
class TestK8sLibInjectioProfilingClusterOverride(_TestK8sLibInjectionProfiling):
    """Test K8s lib injection with profiling enabled, overriting cluster agent config."""

    @bug(context.library > "python@2.12.2" and context.library < "python@3.10.0", reason="APMON-1496")
    def test_profiling_override_cluster_env(self):
        profiling_request_found = self._check_profiling_request_sent(get_cluster_info())
        assert profiling_request_found, "No profiling request found"
