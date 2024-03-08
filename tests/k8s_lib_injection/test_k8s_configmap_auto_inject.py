import os
import time
import json
import requests
from utils import scenarios, features
from utils.tools import logger
from utils import scenarios, context, features
from kubernetes import client, watch


@features.k8s_admission_controller
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
        return [
            {
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
        ]

    def check_for_env_vars(self, test_k8s_instance, expected_env_vars):
        """ evaluates whether the expected tracer config is reflected in the env vars of the targeted pod. """

        v1 = client.CoreV1Api()
        app_name = f"{test_k8s_instance.library}-app"
        pods = v1.list_namespaced_pod(namespace="default", label_selector=f"app={app_name}")
        assert len(pods.items) == 1, f"No pods found for app {app_name}"

        for expected_env_var in expected_env_vars:
            env_var_found = False
            for env_var in pods.items[0].spec.containers[0].env:
                if env_var.name == expected_env_var["name"]:
                    assert (
                        env_var.value == expected_env_var["value"]
                    ), f"Env var {expected_env_var['name']} is not set to {expected_env_var['value']}"
                    env_var_found = True
                    break
            assert env_var_found, f"Env var {expected_env_var['name']} not found"

    def test_simple_auto_install(self, test_k8s_instance):

        test_k8s_instance.deploy_weblog_as_deployment()
        logger.info(f"Launching test test_auto_install")
        test_agent = test_k8s_instance.deploy_test_agent()
        test_agent.deploy_operator_auto()
        default_config_data = self._get_default_auto_inject_config(test_k8s_instance)
        default_config_data[0]["lib_config"]["tracing_sampling_rate"] = 0.50
        test_k8s_instance.apply_config_auto_inject(json.dumps(default_config_data))
        traces_json = self._get_dev_agent_traces()
        logger.debug(f"Traces: {traces_json}")
        assert len(traces_json) > 0, "No traces found"
        expected_env_vars = [{"name": "DD_TRACE_SAMPLE_RATE", "value": "0.50"}]
        self.check_for_env_vars(test_k8s_instance, expected_env_vars)
        logger.info(f"Test test_auto_install finished")

    # TODO
    # ${BASE_DIR}/execFunction.sh check-for-pod-metadata
    # ${BASE_DIR}/execFunction.sh check-for-deploy-metadata
