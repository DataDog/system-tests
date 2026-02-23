import logging
import time

import requests

from utils import scenarios, features
from tests.k8s_lib_injection.utils import get_cluster_info, K8sClusterInfo

logger = logging.getLogger(__name__)


class _TestK8sLibInjectionAppsec:
    """Test appsec activation with the admission controller."""

    def _check_appsec_traces(self, k8s_cluster_info: K8sClusterInfo, timeout: int = 90):
        """Use test agent traces endpoint to check if AppSec traces have been generated.
        Sends a request with an attack pattern to trigger AppSec, then checks the spans
        for _dd.appsec.enabled metric and appsec.event meta tag.
        """
        weblog_url = f"http://{k8s_cluster_info.cluster_host_name}:{k8s_cluster_info.get_weblog_port()}/"
        logger.info(f"Sending attack request to weblog: {weblog_url}")

        try:
            weblog_response = requests.get(weblog_url, headers={"user-agent": "dd-test-scanner-log"}, timeout=10)
            logger.info(f"Weblog response status: {weblog_response.status_code}")
        except Exception as e:
            logger.warning(f"Weblog request failed with exception: {e}")

        agent_url = f"http://{k8s_cluster_info.cluster_host_name}:{k8s_cluster_info.get_agent_port()}/test/traces"
        logger.info(f"Starting to poll agent traces endpoint: {agent_url} (timeout: {timeout}s)")

        mustend = time.time() + timeout
        iteration = 0
        while time.time() < mustend:
            iteration += 1
            logger.info(f"Polling iteration {iteration}, time remaining: {int(mustend - time.time())}s")

            try:
                response = requests.get(agent_url, timeout=60)
                logger.info(f"Agent response status: {response.status_code}")

                traces = response.json()
                logger.info(f"Received {len(traces)} traces")

                for trace_idx, trace in enumerate(traces):
                    logger.debug(f"  Trace {trace_idx}: {len(trace)} spans")
                    for span_idx, span in enumerate(trace):
                        meta = span.get("meta", {})
                        metrics = span.get("metrics", {})

                        has_appsec_enabled_metric = "_dd.appsec.enabled" in metrics
                        appsec_enabled_value = metrics.get("_dd.appsec.enabled")
                        has_appsec_event = "appsec.event" in meta
                        appsec_event_value = meta.get("appsec.event")

                        if has_appsec_enabled_metric or has_appsec_event:
                            logger.info(
                                f"  Span {span_idx} - "
                                f"_dd.appsec.enabled present: {has_appsec_enabled_metric} (value: {appsec_enabled_value}), "
                                f"appsec.event present: {has_appsec_event} (value: {appsec_event_value})"
                            )

                        if metrics.get("_dd.appsec.enabled") == 1 and meta.get("appsec.event") == "true":
                            logger.info("✓ Found AppSec trace with correct values!")
                            return True

            except Exception as e:
                logger.warning(f"Error during iteration {iteration}: {e}")

            time.sleep(1)

        logger.warning(f"No AppSec traces found after {iteration} iterations ({timeout}s)")
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
