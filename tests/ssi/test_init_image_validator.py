import os
import time

import requests
from utils import scenarios, features
from utils.tools import logger
from utils import scenarios, context, features
from retry import retry


class _TestInjectionValidator:
    """ This test case validates the lib init image. It checks that the init image contains a correct package of the tracer.
    We can use the tracer for instrument the weblog application. We use the dev test agent to check if the weblog is instrumented."""

    @retry(delay=2, tries=10)
    def _get_dev_agent_traces(self):
        logger.info(f"[Check traces] Checking traces:")
        response = requests.get(f"http://localhost:8126/test/traces")
        traces_json = response.json()
        assert traces_json is not None and len(traces_json) > 0, "No traces found"
        return traces_json

    @retry(delay=2, tries=20)
    def _check_weblog_running(self):
        logger.info(f"[Check traces] Checking traces:")
        response = requests.get(f"http://localhost:8080")
        assert response.status_code == 200, "Weblog not running"
        logger.info("Weblog is running")

    def test_weblog_instrumented(self):
        logger.info("Launching test test_weblog_instrumented")
        self._check_weblog_running()
        traces_json = self._get_dev_agent_traces()
        logger.debug(f"Traces: {traces_json}")
        assert len(traces_json) > 0, "No traces found. The weblog app was not instrumented"


@scenarios.lib_injection_validation
@features.k8s_admission_controller
class TestInitImageValidator(_TestInjectionValidator):
    pass


@scenarios.host_injection_validation
@features.k8s_admission_controller
class TestHostInjectionValidator(_TestInjectionValidator):
    pass
