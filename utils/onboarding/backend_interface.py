from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
import json
import os
from pathlib import Path
import time
from typing import Any
import requests
import random
from utils import interfaces
from utils._logger import logger


API_HOST = "https://dd.datadoghq.com"
_json_meta_values = frozenset(["_dd.appsec.json", "_dd.iast.json"])


MOCKED_BACKEND_TRACE_TIMEOUT = 120
MOCKED_BACKEND_PROFILE_TIMEOUT = 180
_MOCKED_BACKEND_POLL_INTERVAL = 2


def wait_backend_trace_id(trace_id: str, *, profile: bool = False, validator: Callable | None = None) -> None:
    mocked = interfaces.backend_v2.mocked_backend_running
    logger.info(f"Waiting for {'mocked ' if mocked else ''}backend trace with trace_id: {trace_id}")
    if mocked:
        results = _query_mocked_backend_for_trace_id(trace_id, validator=validator)
    else:
        results = _query_for_trace_id(trace_id, validator=validator)
    runtime_id = results["runtime_id"]
    if validator:
        validator_results = results["validator"]
        assert validator_results, f"{validator.__name__} failed to validate trace_id: {trace_id}"

    assert runtime_id, f"Could not find runtime-id for trace_id: {trace_id}"

    if profile:
        if mocked:
            _query_mocked_backend_for_profile(runtime_id)
        else:
            _query_for_profile(runtime_id)


def _headers():
    """The backend can raise a 429 error if the rate limit is reached.
    We can use several app keys trying to avoid the rate limit.
    """
    # Omit credential-selection locals from pytest failure reports.
    __tracebackhide__ = True

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


def _query_for_trace_id(trace_id: str, validator: Callable | None = None):
    url = f"{API_HOST}/api/ui/trace/{trace_id}"

    results = {}

    trace_data = _make_request(url, headers=_headers())
    _deserialize_meta(trace_data)
    if validator:
        logger.info("Validating backend trace...")
        results["validator"] = validator(trace_id, trace_data)
        if not results["validator"]:
            logger.info("Validator failed")

    root_id = trace_data["trace"]["root_id"]
    root_span = trace_data["trace"]["spans"][root_id]
    start_time = root_span["start"]
    start_date = datetime.fromtimestamp(start_time, tz=UTC)
    if (datetime.now(tz=UTC) - start_date).days > 1:
        logger.info("Backend trace is too old")
        results["runtime_id"] = None
    else:
        results["runtime_id"] = root_span["meta"]["runtime-id"]
    return results


def _deserialize_meta(trace: dict) -> dict:
    spans = trace.get("trace", {}).get("spans", {})
    for span in spans.values():
        meta = span.get("meta", {})
        for key in _json_meta_values:
            value = meta.get(key)
            if isinstance(value, str):
                meta[key] = json.loads(value)

    return trace


def _make_request(
    url: str,
    headers: dict[str, str] | None = None,
    method: str = "get",
    json: dict | None = None,
    overall_timeout: int = 300,
    request_timeout: int = 10,
    retry_delay: int = 1,
    backoff_factor: int = 2,
    max_retries: int = 30,
    validator: Callable | None = None,
):
    """Make a request to the backend with retries and backoff.

    With the defaults, this will retry for approximately 5 minutes.
    """
    # Omit authentication headers from pytest failure reports.
    __tracebackhide__ = True

    start_time = time.perf_counter()
    for _attempt in range(max_retries):
        try:
            r = requests.request(method=method, url=url, headers=headers, json=json, timeout=request_timeout)
            logger.debug(f" Backend response status for url [{url}]: [{r.status_code}]")
            if r.status_code == HTTPStatus.OK:
                response_json = r.json()
                if not validator or validator(response_json):
                    return response_json
                logger.debug(f" Backend response does not meet expectation for url [{url}]: [{r.text}]")
            if r.status_code == HTTPStatus.TOO_MANY_REQUESTS:
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


def _parse_retry_after(headers: dict[str, str]):
    # docs: https://docs.datadoghq.com/api/latest/rate-limits/
    limit = headers.get("X-RateLimit-Limit")
    period = headers.get("X-RateLimit-Period")
    remaining = headers.get("X-RateLimit-Remaining")
    reset = headers.get("X-RateLimit-Reset")
    name = headers.get("X-RateLimit-Name")

    logger.info(
        f" Rate limit information: X-RateLimit-Name={name} X-RateLimit-Limit={limit} "
        f"X-RateLimit-period={period} X-RateLimit-Ramaining={remaining} X-RateLimit-Reset={reset}"
    )

    try:
        return int(reset)
    except (ValueError, TypeError):
        return -1


def _validate_profiler_response(json: dict):
    data = json["data"]
    return isinstance(data, list) and len(data) > 0


def _query_for_profile(runtime_id: str):
    # This caller also retains authentication headers while the request runs.
    __tracebackhide__ = True

    url = f"{API_HOST}/api/unstable/profiles/list"
    headers = _headers()
    headers["Content-Type"] = "application/json"

    now = datetime.now(tz=UTC)
    time_to = now + timedelta(minutes=6)
    time_from = now - timedelta(minutes=6)
    query_json = {
        "track": "profile",
        "filter": {
            "query": f"-_dd.hotdog:* runtime-id:{runtime_id}",
            "from": time_from.isoformat(timespec="seconds"),
            "to": time_to.isoformat(timespec="seconds"),
        },
    }

    logger.debug(f"Posting to {url} with query: {query_json}")
    profile_id = _make_request(
        url, headers=headers, method="post", json=query_json, validator=_validate_profiler_response
    )["data"][0]["id"]
    logger.debug(f"Found profile in the backend with ID: {profile_id}")


# Mocked backend
#
# When the scenario runs with the mocked backend (see `mocked_backend` in the VM scenarios), the agent
# sends its payloads to `interfaces.backend_v2` instead of the Datadog intake. The functions below look
# for the trace/profile in what the mock received, and rebuild the subset of the `/api/ui/trace` response
# structure that the validators use: {"trace": {"root_id": ..., "spans": {span_id: {"meta", "metrics", "start"}}}}


def _query_mocked_backend_for_trace_id(trace_id: str, validator: Callable | None = None) -> dict:
    expected_trace_id = int(trace_id)
    deadline = time.perf_counter() + MOCKED_BACKEND_TRACE_TIMEOUT
    trace_data: dict | None = None
    validator_result = None

    while True:
        trace_data = _get_mocked_backend_trace(expected_trace_id)
        if trace_data is not None:
            if validator is None:
                break
            validator_result = validator(trace_id, trace_data)
            if validator_result:
                break
            # spans of a trace may come in several payloads (partial flush), retry until the deadline
            logger.debug(f"Trace {trace_id} found in the mocked backend, but the validator failed, retrying")

        if time.perf_counter() + _MOCKED_BACKEND_POLL_INTERVAL >= deadline:
            break
        time.sleep(_MOCKED_BACKEND_POLL_INTERVAL)

    if trace_data is None:
        _log_mocked_backend_content()
        raise TimeoutError(f"Trace {trace_id} not found in the mocked backend after {MOCKED_BACKEND_TRACE_TIMEOUT}s")

    logger.info(f"Trace {trace_id} found in the mocked backend")
    results: dict[str, Any] = {}
    if validator:
        logger.info("Validating mocked backend trace...")
        results["validator"] = validator_result
        if not validator_result:
            logger.info("Validator failed")

    root_id = trace_data["trace"]["root_id"]
    results["runtime_id"] = trace_data["trace"]["spans"][root_id]["meta"].get("runtime-id")
    return results


def _get_mocked_backend_trace(trace_id: int) -> dict | None:
    """Gather all spans of the trace received by the mocked backend, and build a structure
    similar to the one returned by the backend `/api/ui/trace` endpoint
    """
    spans: dict[str, dict] = {}

    for data in interfaces.backend_v2.get_data(path_filters="/api/v0.2/traces"):
        content = data["request"].get("content")
        if not isinstance(content, dict):
            continue

        if "tracerPayloads" in content:
            payloads, is_v1 = content["tracerPayloads"], False
        elif "idxTracerPayloads" in content:
            payloads, is_v1 = content["idxTracerPayloads"], True
        else:
            continue

        for payload in payloads:
            payload_meta = _get_mocked_backend_payload_meta(payload, is_v1=is_v1)
            for chunk in payload.get("chunks", []):
                if is_v1:
                    if (int(chunk["traceID"], 16) & 0xFFFFFFFFFFFFFFFF) != trace_id:
                        continue
                    chunk_meta = {k: v for k, v in chunk.get("attributes", {}).items() if k.startswith("_dd.p.")}
                else:
                    chunk_meta = {}

                for raw_span in chunk.get("spans", []):
                    if not is_v1 and int(raw_span.get("traceID", 0)) != trace_id:
                        continue
                    span = _to_backend_span(raw_span, is_v1=is_v1)
                    span["meta"] = {**payload_meta, **chunk_meta, **span["meta"]}
                    spans[span["span_id"]] = span

    if not spans:
        return None

    # the root span is the one whose parent is not part of the trace (the weblog request
    # propagates a trace id, so the parent id of the local root may not be 0)
    roots = [span for span in spans.values() if span["parent_id"] not in spans]
    root = min(roots or spans.values(), key=lambda span: span["start"])

    trace_data = {"trace": {"root_id": root["span_id"], "spans": spans}}
    _deserialize_meta(trace_data)
    return trace_data


def _log_mocked_backend_content() -> None:
    """Help to understand why a trace is missing: did the agent reach the mock at all, and with which traces?"""
    paths: dict[str, int] = {}
    trace_ids: list[str] = []
    for data in interfaces.backend_v2.get_data():
        paths[data["path"]] = paths.get(data["path"], 0) + 1
        if data["path"] != "/api/v0.2/traces":
            continue
        content = data["request"].get("content")
        if not isinstance(content, dict):
            trace_ids.append(f"<undeserialized payload in {data['log_filename']}>")
            continue
        for payload in content.get("tracerPayloads", []):
            trace_ids.extend(
                str(span.get("traceID")) for chunk in payload.get("chunks", []) for span in chunk.get("spans", [])[:1]
            )
        for payload in content.get("idxTracerPayloads", []):
            trace_ids.extend(
                str(int(chunk["traceID"], 16) & 0xFFFFFFFFFFFFFFFF)
                for chunk in payload.get("chunks", [])
                if "traceID" in chunk
            )

    if not paths:
        logger.error("The mocked backend did not receive anything: the agent may not be able to reach it")
    else:
        logger.error(f"Requests received by the mocked backend: {paths}")
        logger.error(f"Trace ids received by the mocked backend: {trace_ids}")


def _get_mocked_backend_payload_meta(payload: dict, *, is_v1: bool) -> dict[str, Any]:
    """The backend copies some payload level values on the spans. Reproduce the ones used by the tests"""
    result: dict[str, Any] = {}

    if is_v1:
        tags = payload.get("attributes", {})
        runtime_id = payload.get("runtimeID") or _get_v1_string_ref(payload, "runtimeIDRef")
    else:
        tags = payload.get("tags", {})
        runtime_id = payload.get("runtimeID")

    if "_dd.tags.container" in tags:
        result["_dd.tags.container"] = tags["_dd.tags.container"]

    if runtime_id:
        result["runtime-id"] = runtime_id

    return result


def _get_v1_string_ref(payload: dict, key: str) -> str | None:
    ref = payload.get(key)
    strings = payload.get("strings", [])
    if isinstance(ref, int) and 0 < ref < len(strings):
        return strings[ref]
    return None


def _to_backend_span(raw_span: dict, *, is_v1: bool) -> dict:
    if is_v1:
        attributes: dict[str, Any] = raw_span.get("attributes", {})
        meta = {k: v for k, v in attributes.items() if isinstance(v, (str, dict, list))}
        metrics: dict[str, int | float] = {}
        for k, v in attributes.items():
            number = _as_number(v)
            if number is not None:
                metrics[k] = number
    else:
        meta = dict(raw_span.get("meta", {}))
        metrics = dict(raw_span.get("metrics", {}))

    span_id = raw_span.get("spanID", raw_span.get("span_id", "0"))
    parent_id = raw_span.get("parentID", raw_span.get("parent_id", "0"))

    return {
        "span_id": str(span_id),
        "parent_id": str(parent_id),
        # agent payloads express start in nanoseconds, the backend in seconds
        "start": int(raw_span.get("start", 0)) / 1e9,
        "meta": meta,
        "metrics": metrics,
    }


def _as_number(value: object) -> int | float | None:
    """In v1 payloads, meta and metrics are merged in attributes, and protobuf int64 are serialized as strings"""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _query_mocked_backend_for_profile(runtime_id: str) -> None:
    deadline = time.perf_counter() + MOCKED_BACKEND_PROFILE_TIMEOUT

    while True:
        for data in interfaces.backend_v2.get_data(path_filters="/api/v2/profile"):
            if runtime_id in json.dumps(data["request"].get("content"), default=repr):
                logger.debug(f"Found profile in the mocked backend: {data['log_filename']}")
                _validate_mocked_backend_profile(data)
                return

        if time.perf_counter() + _MOCKED_BACKEND_POLL_INTERVAL >= deadline:
            raise TimeoutError(
                f"Profile for runtime-id {runtime_id} not found in the mocked backend "
                f"after {MOCKED_BACKEND_PROFILE_TIMEOUT}s"
            )
        time.sleep(_MOCKED_BACKEND_POLL_INTERVAL)


def _validate_mocked_backend_profile(data: dict) -> None:
    """Light checks, only to catch an obviously malformed profile: the event can be decoded, and the
    attachments it lists are present and not empty. The attachments content is not decoded: some are
    compressed (e.g. code-provenance.json), whatever their file name
    """
    log_filename = data["log_filename"]
    parts = data["request"].get("content")
    assert isinstance(parts, list), f"Profile is not a multipart payload: {log_filename}"

    # Compressed parts may have a .gz suffix, the attachments listed in the event don't
    files = {_get_multipart_filename(part).removesuffix(".gz"): part for part in parts}

    event_part = files.get("event.json")
    assert event_part is not None, f"No event.json in profile {log_filename}"
    event = event_part.get("content")
    assert isinstance(event, dict), f"Malformed event.json in profile {log_filename}: {event_part}"
    attachments = event.get("attachments")
    assert attachments, f"No attachments listed in event.json of profile {log_filename}"

    for attachment in attachments:
        part = files.get(attachment.removesuffix(".gz"))
        assert part is not None, f"Attachment {attachment} missing from profile {log_filename}"
        file_path = part.get("system-tests-file-path")
        if file_path is not None:
            assert Path(file_path).stat().st_size > 0, f"Attachment {attachment} is empty in profile {log_filename}"
        elif "content" in part:
            assert part["content"], f"Attachment {attachment} is empty in profile {log_filename}"


def _get_multipart_filename(part: dict) -> str:
    """The deserializer only sets system-tests-filename on binary parts: read it from the part headers"""
    content_disposition = part.get("headers", {}).get("content-disposition", "")
    for item in content_disposition.split(";"):
        key, _, value = item.partition("=")
        if key.strip() == "filename":
            return value.strip().strip('"')
    return part.get("system-tests-filename", "")
