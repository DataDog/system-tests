# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from typing import Any
import base64
import json
import os
import re

import requests

from utils.interfaces import library
from utils._context.core import context
from utils.dd_constants import RemoteConfigApplyState as ApplyState
from utils.tools import logger


def send_command(raw_payload) -> dict[str, Any]:
    """
        Sends a remote config payload to the library and waits for the config to be applied.
        Then returns the config state returned by the library :

        1. the first config state acknowledging the config
        2. else if not acknowledged, the last config state received
        3. if not config state received, then an harcoded one with apply_state=UNKNOWN
    """

    assert context.scenario.rc_api_enabled, f"Remote config API is not enabled on {context.scenario}"

    client_configs = raw_payload["client_configs"]
    targets = json.loads(base64.b64decode(raw_payload["targets"]))
    version = targets["signed"]["version"]
    assert len(client_configs) == 1, "Only one client config is supported"
    _, _, product, config_id, _ = client_configs[0].split("/")

    config_state = {
        "id": config_id,
        "product": product,
        "apply_state": ApplyState.UNKNOWN,
        "apply_error": "<No known response from the library>",
    }

    def remote_config_applied(data):
        if data["path"] == "/v0.7/config":
            config_states = (
                data.get("request", {}).get("content", {}).get("client", {}).get("state", {}).get("config_states", [])
            )
            for state in config_states:
                if state["id"] == config_id and state["product"] == product and state["version"] == version:
                    logger.debug(f"Remote config state: {state}")
                    config_state.update(state)
                    if state["apply_state"] == ApplyState.ACKNOWLEDGED:
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

    return config_state
