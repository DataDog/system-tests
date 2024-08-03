import os
import time
from datetime import datetime, timedelta, timezone
import requests
from utils.tools import logger


def _headers():
    return {
        "DD-API-KEY": os.getenv("DD_API_KEY_ONBOARDING"),
        "DD-APPLICATION-KEY": os.getenv("DD_APP_KEY_ONBOARDING"),
    }


def _query_for_trace_id(trace_id, validator=None):
    path = f"/api/v1/trace/{trace_id}"
    host = "https://dd.datadoghq.com"

    try:
        r = requests.get(f"{host}{path}", headers=_headers(), timeout=10)
        logger.debug(f" Backend response status for trace_id [{trace_id}]: [{r.status_code}]")
        if r.status_code == 200:
            logger.debug(f" Backend response for trace_id [{trace_id}]: [{r.text}]")
            # Check if it's  not a old trace
            trace_data = r.json()
            if validator:
                logger.info("Validating backend trace...")
                if not validator(trace_id, trace_data):
                    logger.info("Backend trace is not valid")
                    return -1, None
                logger.info("Backend trace is valid")
            root_id = trace_data["trace"]["root_id"]
            start_time = trace_data["trace"]["spans"][root_id]["start"]
            start_date = datetime.fromtimestamp(start_time)
            if (datetime.now() - start_date).days > 1:
                logger.info("Backend trace is too old")
                return -1, None
            runtime_id = trace_data["trace"]["spans"][root_id]["meta"]["runtime-id"]
            return r.status_code, runtime_id
        return r.status_code, None
    except Exception as e:
        logger.error(f"Error received connecting to host: [{host}] {e} ")
        return -1, None


def _query_for_profile(runtime_id):
    path = "/api/unstable/profiles/list"
    host = "https://dd.datadoghq.com"

    try:
        time_to = datetime.now(timezone.utc)
        time_from = time_to - timedelta(minutes=2)

        queryJson = {
            "track": "profile",
            "filter": {
                "query": f"-_dd.hotdog:* runtime-id:{runtime_id}",
                "from": time_from.isoformat(timespec="seconds"),
                "to": time_to.isoformat(timespec="seconds"),
            },
        }
        logger.debug(f"Posting to {host}{path} with query: {queryJson}")
        headers = _headers()
        headers["Content-Type"] = "application/json"
        r = requests.post(f"{host}{path}", headers=headers, timeout=10, json=queryJson)
        logger.debug(f" Backend response status for profile events for runtime [{runtime_id}]: [{r.status_code}]")
        if r.status_code == 200:
            logger.debug(f" Backend response for profile events for runtime [{runtime_id}]: [{r.text}]")
            data = r.json()["data"]
            # Check if we got any profile events
            if isinstance(data, list) and len(data) > 0:
                return r.status_code
            return -1
        return r.status_code
    except Exception as e:
        logger.error(f"Error received connecting to host: [{host}] {e} ")
        return -1


def wait_backend_trace_id(trace_id, timeout: float = 5.0, profile: bool = False, validator=None):
    start_time = time.perf_counter()
    while True:
        status, runtime_id = _query_for_trace_id(trace_id, validator=validator)
        if status != 200:
            time.sleep(2)
        else:
            logger.info(f"trace [{trace_id}] found in the backend!")
            if profile:
                while True:
                    if _query_for_profile(runtime_id) != 200:
                        time.sleep(2)
                    else:
                        logger.info(f"profile for trace [{trace_id}] (runtime [{runtime_id}]) found in the backend!")
                        break
                    if time.perf_counter() - start_time >= timeout:
                        raise TimeoutError("Backend timeout waiting for profile")
            break
        if time.perf_counter() - start_time >= timeout:
            raise TimeoutError("Backend timeout waiting for trace")
