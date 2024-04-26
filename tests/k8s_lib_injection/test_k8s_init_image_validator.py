


import os
import time

import requests
from utils import scenarios, features
from utils.tools import logger
from utils import scenarios, context, features

@scenarios.k8s_lib_injection_validation
@features.k8s_admission_controller
class TestK8sInitImageValidatopr:
    
    def _get_dev_agent_traces(self,  retry=10):
        for _ in range(retry):
            logger.info(f"[Check traces] Checking traces:")
            response = requests.get(f"http://localhost:8126/test/traces")
            traces_json = response.json()
            if len(traces_json) > 0:
                return traces_json
            time.sleep(2)
        return []
    
    def _check_weblog_running(self,  retry=10):
        final_status = None
        for _ in range(retry):
            logger.info(f"[Check traces] Checking traces:")
            try:
                response = requests.get(f"http://localhost:8080")
                final_status = response.status_code
                if final_status == 200:
                    logger.info("Weblog is running")
                    break
            except Exception as e:
                logger.error(f"Error checking weblog")
            time.sleep(2)
        
        assert final_status == 200, "Weblog not running"
    
    def test_weblog_instrumented(self):
        logger.info("Launching test test_weblog_instrumented")
        self._check_weblog_running()
        traces_json = self._get_dev_agent_traces()
        logger.debug(f"Traces: {traces_json}")
        assert len(traces_json) > 0, "No traces found. The weblog app was not instrumented"
        