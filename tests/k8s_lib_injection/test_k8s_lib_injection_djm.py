import json
from utils import scenarios, features, context, logger

from tests.k8s_lib_injection.utils import get_dev_agent_traces, get_cluster_info, K8sClusterInfo


@features.djm_ssi_k8s
@scenarios.k8s_lib_injection_spark_djm
class TestK8sLibInjectionSparkJdm:
    def _get_spark_application_traces(self, k8s_cluster_info: K8sClusterInfo):
        traces_json = get_dev_agent_traces(k8s_cluster_info)
        logger.debug(f"Traces received: {traces_json}")
        return [
            trace
            for trace in traces_json
            if any(span.get("name") == "spark.application" and span.get("type") == "spark" for span in trace)
        ]

    def test_spark_instrumented_with_ssi(self):
        spark_traces = self._get_spark_application_traces(get_cluster_info())

        logger.info(f"Spark application traces received: {spark_traces}")
        with open(f"{context.scenario.host_log_folder}/spark_traces.json", "w") as f:
            f.write(json.dumps(spark_traces, indent=4))
        assert len(spark_traces) > 0, "No Data Jobs Monitoring Spark application traces found"

        logger.info("Test test_spark_instrumented_with_ssi finished")
