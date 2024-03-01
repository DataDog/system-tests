import os
import time

import requests
from utils import scenarios, features
from utils.tools import logger
from utils import scenarios, context, features


@features.host_auto_instrumentation
@scenarios.k8s_lib_injection
class TestKubernetes:
    def _get_dev_agent_traces(self, retry=10):
        for _ in range(retry):
            logger.info(f"[Check traces] Checking traces:")
            response = requests.get("http://localhost:18126/test/traces")
            traces_json = response.json()
            if len(traces_json) > 0:
                logger.debug(f"Test traces response: {traces_json}")
                return traces_json
            time.sleep(2)
        return []

    def warmup_weblog(self, app_url):
        for _ in range(15):
            try:
                res = requests.get(app_url, timeout=10)
                logger.debug(f"Weblog warmup response: {res.text}")
                if res.status_code == 200 and res.text:
                    logger.debug(f"Weblog warmup complete!")
                    break
                time.sleep(3)
            except Exception:
                time.sleep(3)

    def _test_manual_install(self, test_k8s_instance):
        logger.info(f"Launching test test_manual_install")
        test_agent = test_k8s_instance.deploy_test_agent()
        # time.sleep(60)
        test_agent.deploy_operator_manual()
        # time.sleep(30)
        logger.info(f"Deploying weblog as pod")
        test_k8s_instance.deploy_weblog_as_pod()
        # time.sleep(30)
        # self.warmup_weblog("http://localhost:18080")
        traces_json = self._get_dev_agent_traces()
        assert len(traces_json) > 0, "No traces found"
        logger.info(f"Test test_manual_install finished")

    def test_auto_install(self, test_k8s_instance):

        # echo "[run-auto-lib-injection] Deploying deployment"
        # ${BASE_DIR}/execFunction.sh deploy-app-auto
        # echo "[run-auto-lib-injection] Deploying agents"
        # ${BASE_DIR}/execFunction.sh deploy-agents-auto
        # echo "[run-auto-lib-injection] Apply config"
        # ${BASE_DIR}/execFunction.sh apply-config-auto
        test_k8s_instance.deploy_weblog_as_deployment()
        logger.info(f"Launching test test_auto_install")
        test_agent = test_k8s_instance.deploy_test_agent()
        test_agent.deploy_operator_auto()
        test_k8s_instance.apply_config_auto_inject()
        traces_json = self._get_dev_agent_traces()
        logger.debug(f"Traces: {traces_json}")
        assert len(traces_json) > 0, "No traces found"
        logger.info(f"Test test_auto_install finished")
