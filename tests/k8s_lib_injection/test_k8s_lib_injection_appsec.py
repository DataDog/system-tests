import contextlib
import time

import requests

from utils import scenarios, features
from tests.k8s_lib_injection.utils import get_cluster_info, K8sClusterInfo


class _TestK8sLibInjectionAppsec:
    """Test appsec activation with the admission controller."""

    def _check_appsec_traces(self, k8s_cluster_info: K8sClusterInfo, timeout: int = 90):
        """Use test agent traces endpoint to check if AppSec traces have been generated.
        Sends a request with an attack pattern to trigger AppSec, then checks the spans
        for _dd.appsec.enabled metric and appsec.event meta tag.
        """
        weblog_url = f"http://{k8s_cluster_info.cluster_host_name}:{k8s_cluster_info.get_weblog_port()}/"
        with contextlib.suppress(Exception):
            requests.get(weblog_url, headers={"user-agent": "dd-test-scanner-log"}, timeout=10)

        mustend = time.time() + timeout
        while time.time() < mustend:
            response = requests.get(
                f"http://{k8s_cluster_info.cluster_host_name}:{k8s_cluster_info.get_agent_port()}/test/traces",
                timeout=60,
            )
            for trace in response.json():
                for span in trace:
                    meta = span.get("meta", {})
                    metrics = span.get("metrics", {})
                    if metrics.get("_dd.appsec.enabled") == 1 and meta.get("appsec.event") == "true":
                        return True
            time.sleep(1)
        return False


@features.k8s_admission_controller
@scenarios.k8s_lib_injection_appsec_disabled
class TestK8sLibInjectionAppsecDisabledByDefault(_TestK8sLibInjectionAppsec):
    """Test K8s lib injection that should not have AppSec enabled by default."""

    def test_appsec_disabled_by_default(self):
        appsec_traces_found = self._check_appsec_traces(get_cluster_info())
        assert not appsec_traces_found, "AppSec should be disabled by default, but AppSec traces were found"


@features.k8s_admission_controller
@scenarios.k8s_lib_injection_appsec_enabled
class TestK8sLibInjectionAppsecClusterEnabled(_TestK8sLibInjectionAppsec):
    """Test K8s lib injection with AppSec enabled."""

    def test_appsec_admission_controller(self):
        appsec_traces_found = self._check_appsec_traces(get_cluster_info())
        assert appsec_traces_found, "No AppSec traces found"
