import os
import time
from datetime import datetime, timedelta, timezone
import requests
import random
from utils.tools import logger


API_HOST = "https://dd.datadoghq.com"


def wait_backend_trace_id(trace_id, profile: bool = False, validator=None):
    runtime_id = _query_for_trace_id(trace_id, validator=validator)
    if profile:
        _query_for_profile(runtime_id)


def _headers():
    return {
        "DD-API-KEY": os.getenv("DD_API_KEY_ONBOARDING"),
        "DD-APPLICATION-KEY": os.getenv("DD_APP_KEY_ONBOARDING"),
    }


def _query_for_trace_id(trace_id, validator=None):
    url = f"{API_HOST}/api/v1/trace/{trace_id}"

    trace_data = _make_request(url, headers=_headers())
    if validator:
        logger.info("Validating backend trace...")
        if not validator(trace_id, trace_data):
            logger.info("Backend trace is not valid")
            return None
        logger.info("Backend trace is valid")

    root_id = trace_data["trace"]["root_id"]
    start_time = trace_data["trace"]["spans"][root_id]["start"]
    start_date = datetime.fromtimestamp(start_time)
    if (datetime.now() - start_date).days > 1:
        logger.info("Backend trace is too old")
        return None

    return trace_data["trace"]["spans"][root_id]["meta"]["runtime-id"]


def _make_request(
    url, headers=None, method="get", json=None, request_timeout=10, retry_delay=1, backoff_factor=2, max_retries=6
):
    for _attempt in range(max_retries):
        try:
            r = requests.request(method=method, url=url, headers=headers, json=json, timeout=request_timeout)
            logger.debug(f" Backend response status : [{r.status_code}]")
            if r.status_code == 200:
                return r.json()

            if r.status_code == 429:
                retry_after = _parse_retry_after(r.headers.get("Retry-After"))
                if retry_after > 0:
                    retry_delay = max(retry_after, retry_delay)
                    retry_delay += random.uniform(0, 1)
        except requests.exceptions.RequestException as e:
            logger.error(f"Error received connecting to url: [{url}] {e} ")

        time.sleep(retry_delay)
        retry_delay *= backoff_factor
        retry_delay += random.uniform(0, 1)

    raise TimeoutError(f"Reached max retries limit for {method} {url}")


def _parse_retry_after(retry_after):
    try:
        return int(retry_after)
    except ValueError:
        return -1


def _query_for_profile(runtime_id):
    url = f"{API_HOST}/api/unstable/profiles/list"
    headers = _headers()
    headers["Content-Type"] = "application/json"

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

    logger.debug(f"Posting to {url} with query: {queryJson}")
    data = _make_request(url, headers=headers, method="post", json=queryJson)["data"]

    # Check if we got any profile events
    return bool(isinstance(data, list) and len(data) > 0)
