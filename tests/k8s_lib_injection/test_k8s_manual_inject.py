import os
import time

import requests
from utils import scenarios, features
from utils.tools import logger
from utils import scenarios, context, features


@features.host_auto_instrumentation
@scenarios.k8s_lib_injection
class TestKubernetes:
    def _get_dev_agent_traces(self):
        logger.info(f"[Check traces] Checking traces:")
        response = requests.get("http://localhost:18126/test/traces")
        traces_json = response.json()
        logger.debug(f"Test traces response: {traces_json}")
        return traces_json

    def test_manual_install(self, test_k8s_instance):
        logger.info(f"Launching test test_manual_install")
        test_agent = test_k8s_instance.deploy_test_agent()
        test_agent.deploy_operator_manual()
        logger.info(f"Deploying weblog as pod")
        test_k8s_instance.deploy_weblog_as_pod()
        traces_json = self._get_dev_agent_traces()
        assert traces_json is None or len(traces_json) == 0, "No traces found"
        logger.info(f"Test test_manual_install finished")
