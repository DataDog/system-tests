import os
import time

import requests
from utils import scenarios, features
from utils.tools import logger
from utils import scenarios, context, features


class _TestAdmisionController:
    def _get_dev_agent_traces(self, agent_port, retry=10):
        for _ in range(retry):
            logger.info(f"[Check traces] Checking traces:")
            response = requests.get(f"http://localhost:{agent_port}/test/traces")
            traces_json = response.json()
            if len(traces_json) > 0:
                logger.debug(f"Test traces response: {traces_json}")
                return traces_json
            time.sleep(2)
        return []

    def test_inject_admission_controller(self, test_k8s_instance):
        logger.info(
            f"Launching test _test_inject_admission_controller: Weblog: [{test_k8s_instance.k8s_kind_cluster.weblog_port}] Agent: [{test_k8s_instance.k8s_kind_cluster.agent_port}]"
        )
        test_agent = test_k8s_instance.deploy_test_agent()
        test_agent.deploy_operator_manual()
        test_k8s_instance.deploy_weblog_as_pod()
        traces_json = self._get_dev_agent_traces(test_k8s_instance.k8s_kind_cluster.agent_port)
        assert len(traces_json) > 0, "No traces found"
        logger.info(f"Test _test_inject_admission_controller finished")

    def test_inject_without_admission_controller(self, test_k8s_instance):
        logger.info(
            f"Launching test _test_inject_without_admission_controller: Weblog: [{test_k8s_instance.k8s_kind_cluster.weblog_port}] Agent: [{test_k8s_instance.k8s_kind_cluster.agent_port}]"
        )
        test_k8s_instance.deploy_test_agent()
        test_k8s_instance.deploy_weblog_as_pod(with_admission_controller=False)
        traces_json = self._get_dev_agent_traces(test_k8s_instance.k8s_kind_cluster.agent_port)
        assert len(traces_json) > 0, "No traces found"
        logger.info(f"Test _test_inject_without_admission_controller finished")

    def test_inject_uds_without_admission_controller(self, test_k8s_instance):
        logger.info(
            f"Launching test test_inject_uds_without_admission_controller: Weblog: [{test_k8s_instance.k8s_kind_cluster.weblog_port}] Agent: [{test_k8s_instance.k8s_kind_cluster.agent_port}]"
        )
        test_k8s_instance.deploy_test_agent()
        test_k8s_instance.deploy_weblog_as_pod(with_admission_controller=False, use_uds=True)
        traces_json = self._get_dev_agent_traces(test_k8s_instance.k8s_kind_cluster.agent_port)
        assert len(traces_json) > 0, "No traces found"
        logger.info(f"Test test_inject_uds_without_admission_controller finished")


@features.k8s_admission_controller
@scenarios.k8s_lib_injection_basic
class TestAdmisionControllerBasic(_TestAdmisionController):
    pass


@features.k8s_admission_controller
@scenarios.k8s_lib_injection_full
class TestAdmisionControllerComplete(_TestAdmisionController):
    pass
