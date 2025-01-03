import time

import requests
import json

from utils import scenarios, features, context, irrelevant
from utils.tools import logger
from utils import scenarios, features
from utils.k8s_lib_injection.k8s_command_utils import execute_command_sync

from tests.k8s_lib_injection.utils import get_dev_agent_traces


@features.djm_ssi_k8s
@scenarios.k8s_library_injection_djm
@irrelevant(condition=(context.library != "java"), reason="Data Jobs Monitoring requires Java library only.")
@irrelevant(
    condition=(context.weblog_variant != "dd-djm-spark-test-app"),
    reason="Data Jobs Monitoring tests are only applicable when using dd-djm-spark-test-app web-log variant.",
)
class TestK8sDJMWithSSI:
    """This test case validates java lib injection for Data Jobs Monitoring on k8s.
    The tracer is injected using admission controller via annotations on submitted Spark application.
    We then use the dev test agent to check if the Spark application is instrumented.
    """

    def _get_spark_application_traces(self, test_k8s_instance):
        traces_json = get_dev_agent_traces(test_k8s_instance.k8s_kind_cluster)
        logger.debug(f"Traces received: {traces_json}")
        return [
            trace
            for trace in traces_json
            if any(span.get("name") == "spark.application" and span.get("type") == "spark" for span in trace)
        ]

    def test_spark_instrumented_with_ssi(self, test_k8s_instance):
        logger.info(
            f"Launching test test_spark_instrumented_with_ssi: Weblog: [{test_k8s_instance.k8s_kind_cluster.get_weblog_port()}] Agent: [{test_k8s_instance.k8s_kind_cluster.get_agent_port()}]"
        )

        # create service account for launching spark application in k8s
        execute_command_sync(f"kubectl create serviceaccount spark", test_k8s_instance.k8s_kind_cluster)
        execute_command_sync(
            f"kubectl create clusterrolebinding spark-role --clusterrole=edit --serviceaccount=default:spark --namespace=default",
            test_k8s_instance.k8s_kind_cluster,
        )

        test_k8s_instance.deploy_test_agent()
        test_k8s_instance.deploy_datadog_cluster_agent()

        extra_envs_for_djm_weblog_app = {"LIB_INIT_IMAGE": test_k8s_instance.library_init_image}
        test_k8s_instance.deploy_weblog_as_pod(env=extra_envs_for_djm_weblog_app, service_account="spark")

        spark_traces = self._get_spark_application_traces(test_k8s_instance)

        logger.info(f"Spark application traces received: {spark_traces}")
        with open(f"{test_k8s_instance.output_folder}/spark_traces.json", "w") as f:
            f.write(json.dumps(spark_traces, indent=4))
        assert len(spark_traces) > 0, "No Data Jobs Monitoring Spark application traces found"

        logger.info(f"Test test_spark_instrumented_with_ssi finished")
