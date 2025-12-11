import os
import time
from datetime import datetime, timedelta, timezone
import requests
import random
from utils._logger import logger


API_HOST = "https://dd.datadoghq.com"


def wait_backend_trace_id(trace_id, profile: bool = False, validator=None):
    logger.info(f"Waiting for backend trace with trace_id: {trace_id}")
    results = _query_for_trace_id(trace_id, validator=validator)
    runtime_id = results["runtime_id"]
    if validator:
        validator_results = results["validator"]
        assert validator_results, f"{validator.__name__} failed to validate trace_id: {trace_id}"

    assert runtime_id, f"Could not find runtime-id for trace_id: {trace_id}"

    if profile:
        _query_for_profile(runtime_id)


def _headers():
    """The backend can raise a 429 error if the rate limit is reached.
    We can use several app keys trying to avoid the rate limit.
    """
    # Retrieve the mandatory API and APP keys.
    api_key = os.getenv("DD_API_KEY_ONBOARDING")
    app_key = os.getenv("DD_APP_KEY_ONBOARDING")

    if not api_key or not app_key:
        raise ValueError("Mandatory API or APP key is missing.")

    # Start with the mandatory pair.
    pairs = [(api_key, app_key)]

    # Check for additional numbered pairs.
    index = 2
    while True:
        candidate_api = os.getenv(f"DD_API_KEY_ONBOARDING_{index}")
        candidate_app = os.getenv(f"DD_APP_KEY_ONBOARDING_{index}")
        if candidate_api and candidate_app:
            pairs.append((candidate_api, candidate_app))
            index += 1
        else:
            break

    # Randomly select one of the available pairs.
    chosen_api, chosen_app = random.choice(pairs)

    return {
        "DD-API-KEY": chosen_api,
        "DD-APPLICATION-KEY": chosen_app,
    }


def _query_for_trace_id(trace_id, validator=None):
    url = f"{API_HOST}/api/ui/trace/{trace_id}"

    results = {}

    trace_data = _make_request(url, headers=_headers())
    if validator:
        logger.info("Validating backend trace...")
        results["validator"] = validator(trace_id, trace_data)
        if not results["validator"]:
            logger.info("Validator failed")

    root_id = trace_data["trace"]["root_id"]
    root_span = trace_data["trace"]["spans"][root_id]
    start_time = root_span["start"]
    start_date = datetime.fromtimestamp(start_time)
    if (datetime.now() - start_date).days > 1:
        logger.info("Backend trace is too old")
        results["runtime_id"] = None
    else:
        results["runtime_id"] = root_span["meta"]["runtime-id"]
    return results


def _make_request(
    url,
    headers=None,
    method="get",
    json=None,
    overall_timeout=300,
    request_timeout=10,
    retry_delay=1,
    backoff_factor=2,
    max_retries=30,
    validator=None,
):
    """Make a request to the backend with retries and backoff. With the defaults, this will retry for approximately 5 minutes."""
    start_time = time.perf_counter()
    for _attempt in range(max_retries):
        try:
            r = requests.request(method=method, url=url, headers=headers, json=json, timeout=request_timeout)
            logger.debug(f" Backend response status for url [{url}]: [{r.status_code}]")
            if r.status_code == 200:
                response_json = r.json()
                if not validator or validator(response_json):
                    return response_json
                logger.debug(f" Backend response does not meet expectation for url [{url}]: [{r.text}]")
            if r.status_code == 429:
                retry_after = _parse_retry_after(r.headers)
                logger.debug(f" Received 429 for url [{url}], rate limit reset in: [{retry_after}]")
                if retry_after > 0:
                    # If we have a rate limit, we should wait for the reset time instead of the exponential backoff.
                    retry_delay = retry_after
                    retry_delay += random.uniform(0, 1)
        except requests.exceptions.RequestException as e:
            logger.error(f"Error received connecting to url: [{url}] {e} ")

        logger.debug(f" Received unsuccessful response for [{url}], retrying in: [{retry_delay}]")

        # Avoid sleeping if we are going to hit the overall timeout.
        if time.perf_counter() + retry_delay - start_time >= overall_timeout:
            raise TimeoutError(f" Reached overall timeout of {overall_timeout} for {method} {url}")

        time.sleep(retry_delay)
        retry_delay *= backoff_factor
        retry_delay += random.uniform(0, 1)

    raise TimeoutError(f"Reached max retries limit for {method} {url}")


def _parse_retry_after(headers):
    # docs: https://docs.datadoghq.com/api/latest/rate-limits/
    limit = headers.get("X-RateLimit-Limit")
    period = headers.get("X-RateLimit-Period")
    remaining = headers.get("X-RateLimit-Remaining")
    reset = headers.get("X-RateLimit-Reset")
    name = headers.get("X-RateLimit-Name")

    logger.info(
        f" Rate limit information: X-RateLimit-Name={name} X-RateLimit-Limit={limit} X-RateLimit-period={period} X-RateLimit-Ramaining={remaining} X-RateLimit-Reset={reset}"
    )

    try:
        return int(reset)
    except (ValueError, TypeError):
        return -1


def _validate_profiler_response(json):
    data = json["data"]
    return isinstance(data, list) and len(data) > 0


def _query_for_profile(runtime_id):
    url = f"{API_HOST}/api/unstable/profiles/list"
    headers = _headers()
    headers["Content-Type"] = "application/json"

    now = datetime.now(timezone.utc)
    time_to = now + timedelta(minutes=6)
    time_from = now - timedelta(minutes=6)
    queryJson = {
        "track": "profile",
        "filter": {
            "query": f"-_dd.hotdog:* runtime-id:{runtime_id}",
            "from": time_from.isoformat(timespec="seconds"),
            "to": time_to.isoformat(timespec="seconds"),
        },
    }

    logger.debug(f"Posting to {url} with query: {queryJson}")
    profileId = _make_request(
        url, headers=headers, method="post", json=queryJson, validator=_validate_profiler_response
    )["data"][0]["id"]
    logger.debug(f"Found profile in the backend with ID: {profileId}")
