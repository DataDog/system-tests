# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import base64
import hashlib
from typing import Any
import json
import os
import re

import requests

from utils.interfaces import library
from utils._context.core import context
from utils.dd_constants import RemoteConfigApplyState as ApplyState
from utils.tools import logger


def send_command(raw_payload, *, wait_for_acknowledged_status: bool = True) -> dict[str, Any]:
    """
        Sends a remote config payload to the library and waits for the config to be applied.
        Then returns the config state returned by the library :

        1. the first config state acknowledging the config
        2. else if not acknowledged, the last config state received
        3. if not config state received, then an harcoded one with apply_state=UNKNOWN

        Arguments:
            wait_for_acknowledge_status
                If True, waits for the config to be acknowledged by the library.
                Else, only wait for the next request sent to /v0.7/config
    """

    assert context.scenario.rc_api_enabled, f"Remote config API is not enabled on {context.scenario}"

    client_configs = raw_payload["client_configs"]

    current_states = {}
    if len(client_configs) == 0:
        if wait_for_acknowledged_status:
            raise ValueError("Empty client config list is not supported with wait_for_acknowledged_status=True")
    else:
        targets = json.loads(base64.b64decode(raw_payload["targets"]))
        version = targets["signed"]["version"]
        for client_config in client_configs:
            _, _, product, config_id, _ = client_config.split("/")
            current_states[config_id] = {
                "id": config_id,
                "product": product,
                "apply_state": ApplyState.UNKNOWN,
                "apply_error": "<No known response from the library>",
            }

    def remote_config_applied(data):
        if data["path"] == "/v0.7/config":
            if len(client_configs) == 0:  # is there a way to know if the "no-config" is acknowledged ?
                return True

            state = data.get("request", {}).get("content", {}).get("client", {}).get("state", {})
            if state["targets_version"] == version:
                config_states = state.get("config_states", [])
                for state in config_states:
                    config_state = current_states.get(state["id"])
                    if config_state and state["product"] == product:
                        logger.debug(f"Remote config state: {state}")
                        config_state.update(state)

                if wait_for_acknowledged_status:
                    for state in current_states.values():
                        if state["apply_state"] == ApplyState.UNKNOWN:
                            return False

                return True

    if "SYSTEM_TESTS_PROXY_HOST" in os.environ:
        domain = os.environ["SYSTEM_TESTS_PROXY_HOST"]
    elif "DOCKER_HOST" in os.environ:
        m = re.match(r"(?:ssh:|tcp:|fd:|)//(?:[^@]+@|)([^:]+)", os.environ["DOCKER_HOST"])
        if m is not None:
            domain = m.group(1)
        else:
            domain = "localhost"
    else:
        domain = "localhost"

    requests.post(f"http://{domain}:11111", data=json.dumps(raw_payload), timeout=30)

    library.wait_for(remote_config_applied, timeout=30)

    return current_states


def build_debugger_command(probes: list, version: int):
    library_name = context.scenario.library.library

    def _json_to_base64(json_object):
        json_string = json.dumps(json_object).encode("utf-8")
        base64_string = base64.b64encode(json_string).decode("utf-8")
        return base64_string

    def _sha256(value):
        return hashlib.sha256(base64.b64decode(value)).hexdigest()

    def _get_probe_type(probe_id):
        if probe_id.startswith("log"):
            return "logProbe"
        if probe_id.startswith("metric"):
            return "metricProbe"
        if probe_id.startswith("span"):
            return "spanProbe"
        if probe_id.startswith("decor"):
            return "spanDecorationProbe"

        return "not_supported"

    rcm = {"targets": "", "target_files": [], "client_configs": []}

    signed = {
        "signed": {
            "_type": "targets",
            "custom": {"opaque_backend_state": "eyJmb28iOiAiYmFyIn0="},  # where does this come from ?
            "expires": "3000-01-01T00:00:00Z",
            "spec_version": "1.0",
            "targets": {},
            "version": version,
        },
        "signatures": [
            {
                # where does this come from ?
                "keyid": "ed7672c9a24abda78872ee32ee71c7cb1d5235e8db4ecbf1ca28b9c50eb75d9e",
                "sig": "e2279a554d52503f5bd68e0a9910c7e90c9bb81744fe9c8824ea3737b279d9e69b3ce5f4b463c402ebe34964fb7a69625eb0e91d3ddbd392cc8b3210373d9b0f",  # pylint: disable=line-too-long
            }
        ],
    }

    if probes is None:
        rcm["targets"] = _json_to_base64(signed)
    else:
        for probe in probes:
            target = {"custom": {"v": 1}, "hashes": {"sha256": ""}, "length": 0}
            target_file = {"path": "", "raw": ""}

            probe["language"] = library_name

            if probe["where"]["typeName"] == "ACTUAL_TYPE_NAME":
                if library_name == "dotnet":
                    probe["where"]["typeName"] = "weblog.DebuggerController"
                elif library_name == "java":
                    probe["where"]["typeName"] = "DebuggerController"
                    probe["where"]["methodName"] = (
                            probe["where"]["methodName"][0].lower() + probe["where"]["methodName"][1:]
                    )
            elif probe["where"]["sourceFile"] == "ACTUAL_SOURCE_FILE":
                if library_name == "dotnet":
                    probe["where"]["sourceFile"] = "DebuggerController.cs"
                elif library_name == "java":
                    probe["where"]["sourceFile"] = "DebuggerController.java"

            probe_64 = _json_to_base64(probe)
            probe_type = _get_probe_type(probe["id"])
            path = "datadog/2/LIVE_DEBUGGING/" + probe_type + "_" + probe["id"] + "/config"

            target["hashes"]["sha256"] = _sha256(probe_64)
            target["length"] = len(json.dumps(probe).encode("utf-8"))
            signed["signed"]["targets"][path] = target

            target_file["path"] = path
            target_file["raw"] = probe_64

            rcm["target_files"].append(target_file)
            rcm["client_configs"].append(path)

        rcm["targets"] = _json_to_base64(signed)
    return rcm


def send_debbuger_command(probes: list, version: int) -> dict:
    raw_payload = build_debugger_command(probes, version)
    return send_command(raw_payload)
