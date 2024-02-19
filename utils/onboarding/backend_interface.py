import os
import time

import requests
from utils.tools import logger


def _query_for_trace_id(trace_id):
    path = f"/api/v1/trace/{trace_id}"
    host = "https://dd.datadoghq.com"

    headers = {
        "DD-API-KEY": os.getenv("DD_API_KEY_ONBOARDING"),
        "DD-APPLICATION-KEY": os.getenv("DD_APP_KEY_ONBOARDING"),
    }
    try:
        r = requests.get(f"{host}{path}", headers=headers, timeout=10)
        # logger.info(f"Request path [{host}{path}]")
        # logger.info(f"Trying to find trace_id [{trace_id}] in backend with result status [{r.status_code}]")
        logger.debug(f" Backend response for trace_id [{trace_id}]: [{r}]")
        return r.status_code
    except Exception:
        logger.error(f"Error received connecting to host: [{host}] ")
        return -1


def wait_backend_trace_id(trace_id, timeout: float = 5.0):
    start_time = time.perf_counter()
    while True:
        if _query_for_trace_id(trace_id) != 200:
            time.sleep(2)
        else:
            logger.info(f"trace [{trace_id}] found in the backend!")
            break
        if time.perf_counter() - start_time >= timeout:
            raise TimeoutError("Backend timeout")
