# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Helpers for reading CWS (Cloud Workload Security) security events out of the agent's
captured HTTPS traffic.

The security agent ships its events to runtime-security-http-intake.logs.datadoghq.com,
which the proxy captures under "/api/v2/secruntime", as a batch (JSON array) of objects
shaped like:

    {"message": "<the event JSON, escaped as a string>", "ddsource": ..., "ddtags": ...,
     "service": ..., "hostname": ..., "timestamp": ..., "status": ...}

This module unwraps that "message" envelope to get back the original event body.
"""

from collections.abc import Generator
import json
from typing import Any

from utils._logger import logger

CWS_EVENTS_PATH = "/api/v2/secruntime"


def iter_cws_events(data: dict[str, Any]) -> Generator[dict[str, Any], None, None]:
    """Yield every decoded CWS security event body carried by one captured request
    (as returned by interfaces.agent.get_data()/wait_for()).
    """
    if data["path"] != CWS_EVENTS_PATH:
        return

    content = data["request"].get("content")
    if not isinstance(content, list):
        return

    for entry in content:
        if not isinstance(entry, dict) or "message" not in entry:
            continue

        try:
            yield json.loads(entry["message"])
        except (TypeError, ValueError):
            logger.debug(f"Could not decode a {CWS_EVENTS_PATH} entry as a CWS event: {entry}")


def cws_event_mentioning(data: dict[str, Any], marker: str) -> dict[str, Any] | None:
    """Return the first CWS event carried by `data` whose JSON body contains `marker`
    (e.g. the unique canary file path a test's request opened), or None.
    """
    for event in iter_cws_events(data):
        if marker in json.dumps(event):
            return event

    return None


def cws_self_test_succeeded(data: dict[str, Any]) -> bool:
    """True if `data` carries the agent's CWS self-test result, with every test passing.

    This is the agent's own end-to-end proof that the CWS pipeline is live: rules evaluate,
    events are generated, and they reach the intake.
    """
    for event in iter_cws_events(data):
        if event.get("agent", {}).get("rule_id") != "self_test":
            continue

        if event.get("failed_tests"):
            logger.error(f"CWS self test reported failures: {event['failed_tests']}")
            return False

        return bool(event.get("succeeded_tests"))

    return False
