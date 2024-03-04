import os
import time

import requests
from utils import scenarios, features
from utils.tools import logger
from utils import scenarios, context, features


@features.host_auto_instrumentation
@scenarios.k8s_lib_injection
class TestConfigMapAutoInject:
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

    def _get_default_auto_inject_config(self, test_k8s_instance):
        return {
            "id": "11777398274940883092",
            "revision": 0,
            "schema_version": "v1.0.0",
            "action": "enable",
            "lib_config": {
                "library_language": f"{test_k8s_instance.library}",
                "library_version": "latest",
                "service_name": f"test-{test_k8s_instance.library}-service",
                "env": "dev",
                "tracing_enabled": True,
                "tracing_sampling_rate": 0.90,
            },
            "k8s_target": {
                "cluster": "lib-injection-testing",
                "kind": "deployment",
                "name": f"test-{test_k8s_instance.library}-deployment",
                "namespace": "default",
            },
        }

    def test_simple_auto_install(self, test_k8s_instance):

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
        default_config_data = self._get_default_auto_inject_config(test_k8s_instance)
        # json = json.dumps(default_config_data)

        test_k8s_instance.apply_config_auto_inject(f"[{str(default_config_data)}]")
        traces_json = self._get_dev_agent_traces()
        logger.debug(f"Traces: {traces_json}")
        assert len(traces_json) > 0, "No traces found"
        logger.info(f"Test test_auto_install finished")
