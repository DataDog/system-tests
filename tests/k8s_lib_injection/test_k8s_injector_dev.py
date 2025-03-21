import time
import requests

from utils import scenarios, features, context, missing_feature
from tests.k8s_lib_injection.utils import get_dev_agent_traces


class _BaseProfiling:
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
@scenarios.k8s_lib_injection_single_service
class TestSingleService(_BaseProfiling):
    """Test injector-dev single service that performs the auto injection"""

    def test_traces(self):
        """Check that the app is sending traces to the APM Test Agent"""
        traces_json = get_dev_agent_traces(context.scenario.k8s_cluster_provider.get_cluster_info())
        assert len(traces_json) > 0, "No traces found"

    @missing_feature(context.library == "ruby", reason="Profiling not implemented for Ruby")
    def test_profiling(self):
        """Check that the app is sending profiling traces"""
        profiling_request_found = self._check_profiling_request_sent(
            context.scenario.k8s_cluster_provider.get_cluster_info()
        )
        assert profiling_request_found, "No profiling request found"
