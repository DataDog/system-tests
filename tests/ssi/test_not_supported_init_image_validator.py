import os
import time

import requests
from utils import scenarios, features
from utils.tools import logger
from utils import scenarios, context, features
from retry import retry


@scenarios.lib_injection_validation_not_supported_lang
@features.k8s_admission_controller
class TestK8sInitImageValidator:
    """ This test case validates the lib init image. This test run through no supported version of the language.
    We validate that the app is running but not instrumented because the lang version is not supported.
    For example, JDK 7 is not supported, but can run without send traces to the agent"""

    @retry(delay=1, tries=10)
    def _get_dev_agent_traces(self):
        logger.info(f"[Check traces] Checking traces:::")
        response = requests.get(f"http://localhost:8126/test/traces")
        traces_json = response.json()
        return traces_json

    @retry(delay=2, tries=10)
    def _check_weblog_running(self):
        logger.info(f"[Check traces] Checking traces:")
        response = requests.get(f"http://localhost:8080")
        assert response.status_code == 200, "Weblog not running"
        logger.info("Weblog is running")

    def test_weblog_instrumented(self):
        logger.info("Launching test test_weblog_instrumented")
        self._check_weblog_running()
        traces_json = self._get_dev_agent_traces()
        assert (
            traces_json is None or len(traces_json) == 0
        ), "Traces found, but we should not have the traces, because lang version is not supported"
