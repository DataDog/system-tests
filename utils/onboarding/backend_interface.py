import os
import time
from datetime import datetime
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
        logger.debug(f" Backend response status for trace_id [{trace_id}]: [{r.status_code}]")
        if r.status_code == 200:
            logger.debug(f" Backend response for trace_id [{trace_id}]: [{r.text}]")
            # Check if it's  not a old trace
            trace_data = r.json()
            root_id = trace_data["trace"]["root_id"]
            start_time = trace_data["trace"]["spans"][root_id]["start"]
            start_date = datetime.fromtimestamp(start_time)
            if (datetime.now() - start_date).days > 1:
                logger.warn("Backend trace is too old")
                return -1
        return r.status_code
    except Exception as e:
        logger.error(f"Error received connecting to host: [{host}] {e} ")
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
