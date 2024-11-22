import time

import requests
from utils import scenarios, features, context, irrelevant
from utils.tools import logger
from utils import scenarios, features

@features.k8s_admission_controller
@scenarios.k8s_library_injection_djm
@irrelevant(condition=(context.library!="java"), reason="Data Jobs Monitoring requires Java library only.")
@irrelevant(condition=(context.weblog_variant!="dd-djm-spark-test-app"), reason="Data Jobs Monitoring tests are only applicable when using dd-djm-spark-test-app web-log variant.")
class TestK8sDJMWithSSI:
    """ This test case validates java lib injection for Data Jobs Monitoring on k8s.
    The tracer is injected using admission controller via annotations on submitted Spark application. 
    We then use the dev test agent to check if the Spark application is instrumented.
    """

    def _get_dev_agent_traces(self, k8s_kind_cluster, retry=10):
        for _ in range(retry):
            logger.info(f"[Check traces] Checking traces:")
            response = requests.get(
                f"http://{k8s_kind_cluster.cluster_host_name}:{k8s_kind_cluster.get_agent_port()}/test/traces"
            )
            traces_json = response.json()
            if len(traces_json) > 0:
                logger.debug(f"Test traces response: {traces_json}")
                return traces_json
            time.sleep(2)
        return []
        
    def test_spark_instrumented_with_ssi(self, test_k8s_instance):
        logger.info(
            f"Launching test test_spark_instrumented_with_ssi: Weblog: [{test_k8s_instance.k8s_kind_cluster.get_weblog_port()}] Agent: [{test_k8s_instance.k8s_kind_cluster.get_agent_port()}]"
        )
        
        test_k8s_instance.deploy_test_agent()
        test_k8s_instance.deploy_datadog_cluster_agent()
        test_k8s_instance.deploy_weblog_as_pod()
        
        traces_json = self._get_dev_agent_traces(test_k8s_instance.k8s_kind_cluster)
        
        logger.debug(f"Traces received: {traces_json}")
        assert len(traces_json) > 0, "No traces found"
        assert any("spark.application" in trace for trace in traces_json), "No spark.application traces found"
        
        self.logger.info(f"Test test_spark_instrumented_with_ssi finished")
