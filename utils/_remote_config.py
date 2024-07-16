# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import base64
import hashlib
import json
import os
import re
from typing import Any

import requests

from utils._context.core import context
from utils.dd_constants import RemoteConfigApplyState as ApplyState
from utils.interfaces import library
from utils.tools import logger


def _post(path: str, payload) -> None:
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

    requests.post(f"http://{domain}:11111{path}", data=json.dumps(payload), timeout=30)


RC_VERSION = "_ci_global_version"
RC_STATE = "_ci_state"


def send_command(
    raw_payload, *, wait_for_acknowledged_status: bool = True, command_version: int = -1
) -> dict[str, dict[str, Any]]:
    """
    Sends a remote config payload to the library and waits for the config to be applied.
    Then returns a dictionary with the state of each requested file as returned by the library.

    The dictionary keys are the IDs from the files that can be extracted from the path,
    e.g: datadog/2/ASM_FEATURES/asm_features_activation/config => asm_features_activation
    and the values contain the actual state for each file:

    1. a config state acknowledging the config
    2. else if not acknowledged, the last config state received
    3. if no config state received, then a hardcoded one with apply_state=UNKNOWN

    Arguments:
        wait_for_acknowledge_status
            If True, waits for the config to be acknowledged by the library.
            Else, only wait for the next request sent to /v0.7/config
    """

    assert context.scenario.rc_api_enabled, f"Remote config API is not enabled on {context.scenario}"

    client_configs = raw_payload.get("client_configs", [])

    current_states = {}
    version = None
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
    current_states[RC_VERSION] = command_version
    current_states[RC_STATE] = ApplyState.UNKNOWN

    state = {}

    def remote_config_applied(data):
        nonlocal state
        if data["path"] == "/v0.7/config":
            state = data.get("request", {}).get("content", {}).get("client", {}).get("state", {})
            if len(client_configs) == 0:
                found = state["targets_version"] == command_version and state.get("config_states", []) == []
                if found:
                    current_states[RC_STATE] = ApplyState.ACKNOWLEDGED
                return found

            if state["targets_version"] == version:
                config_states = state.get("config_states", [])
                for state in config_states:
                    config_state = current_states.get(state["id"])
                    if config_state and state["product"] == product:
                        logger.debug(f"Remote config state: {state}")
                        config_state.update(state)

                if wait_for_acknowledged_status:
                    for key, state in current_states.items():
                        if key not in (RC_VERSION, RC_STATE):
                            if state["apply_state"] == ApplyState.UNKNOWN:
                                return False

                current_states[RC_STATE] = ApplyState.ACKNOWLEDGED
                return True

    _post("/unique_command", raw_payload)
    library.wait_for(remote_config_applied, timeout=30)

    return current_states


def send_sequential_commands(commands: list[dict]) -> None:
    """DEPRECATED"""
    _post("/sequential_commands", commands)


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
                "sig": "e2279a554d52503f5bd68e0a9910c7e90c9bb81744fe9c8824ea3737b279d9e6"
                "9b3ce5f4b463c402ebe34964fb7a69625eb0e91d3ddbd392cc8b3210373d9b0f",
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


def send_debugger_command(probes: list, version: int) -> dict:
    raw_payload = build_debugger_command(probes, version)
    return send_command(raw_payload)


def _json_to_base64(json_object):
    json_string = json.dumps(json_object, indent=2).encode("utf-8")
    base64_string = base64.b64encode(json_string).decode("utf-8")
    return base64_string


class ClientConfig:
    _store: dict[str, "ClientConfig"] = {}
    config_file_version: int = 1

    def __init__(self, path: str, config, config_file_version=None) -> None:
        self.path = path

        self.raw = config if isinstance(config, str) else _json_to_base64(config)
        self.raw_decoded = base64.b64decode(self.raw).decode("utf-8")
        self.config_file_version = self.config_file_version if config_file_version is None else config_file_version

        if config is not None:
            self._store[path] = self
            self.raw_length = len(self.raw_decoded)
            self.raw_sha256 = hashlib.sha256(base64.b64decode(self.raw)).hexdigest()
        else:
            stored_config = self._store.get(path, None)
            self.raw_length = stored_config.raw_length
            self.raw_sha256 = stored_config.raw_sha256

    @property
    def raw_deserialized(self):
        return json.loads(self.raw_decoded)

    def get_target_file(self, deserialized=False):
        return {"path": self.path, "raw": self.raw_deserialized if deserialized else self.raw}

    def get_target(self):
        return {
            "custom": {"v": self.config_file_version},
            "hashes": {"sha256": self.raw_sha256},
            "length": self.raw_length,
        }

    def __repr__(self) -> str:
        if self.config_file_version == ClientConfig.config_file_version:
            return f"""({self.path!r}, {self.raw_deserialized!r})"""

        return f"""({self.path!r}, {self.raw_deserialized!r}, {self.config_file_version})"""


class RemoteConfigCommand:
    """
    https://docs.google.com/document/d/1u_G7TOr8wJX0dOM_zUDKuRJgxoJU_hVTd5SeaMucQUs/edit#heading=h.octuyiil30ph
    https://github.com/DataDog/datadog-agent/blob/main/pkg/proto/datadog/remoteconfig/remoteconfig.proto#L180
    """

    backend_state = '{"foo": "bar"}'
    expires = "3000-01-01T00:00:00Z"
    spec_version = "1.0"
    signatures = [
        {
            "keyid": "ed7672c9a24abda78872ee32ee71c7cb1d5235e8db4ecbf1ca28b9c50eb75d9e",
            "sig": "f5f2f27035339ed841447713eb93e5c62c34f4fa709fac0f9edca4ef5dc77340"
            "e1e81e779c5b536304fe568173c9c0e9125b17c84ce8a58a907bb2f27e7d890b",
        }
    ]
    _store: dict[str, "RemoteConfigCommand"] = {}

    def __new__(cls, expires=None) -> "RemoteConfigCommand":
        scenario = context.scenario.name
        if scenario in cls._store:
            return cls._store[scenario]
        obj = super().__new__(cls)
        cls._store[scenario] = obj
        obj.targets = {}
        obj.version = 0
        obj.expires = expires or RemoteConfigCommand.expires
        obj.opaque_backend_state = base64.b64encode(obj.backend_state.encode("utf-8")).decode("utf-8")
        return obj

    def add_client_config(self, path, config, config_file_version=None) -> "RemoteConfigCommand":
        """Add a file"""
        client_config = ClientConfig(
            path=path,
            config=config,
            config_file_version=(self.version + 1) if config_file_version is None else config_file_version,
        )
        self.targets[path] = client_config
        return self

    def del_client_config(self, path) -> "RemoteConfigCommand":
        """Remove a file"""
        if path in self.targets:
            del self.targets[path]
        return self

    def reset(self) -> "RemoteConfigCommand":
        """Remove all files"""
        self.targets.clear()
        return self

    def serialize_targets(self, deserialized=False):
        result = {
            "signed": {
                "_type": "targets",
                "custom": {"opaque_backend_state": self.opaque_backend_state},
                "expires": self.expires,
                "spec_version": self.spec_version,
                "targets": {path: target.get_target() for path, target in self.targets.items()},
                "version": self.version,
            },
            "signatures": self.signatures,
        }

        return _json_to_base64(result) if not deserialized else result

    def to_payload(self, deserialized=False):
        result = {"targets": self.serialize_targets(deserialized=deserialized)}

        target_files = [
            target.get_target_file(deserialized=deserialized)
            for target in self.targets.values()
            if target.raw_deserialized is not None
        ]
        if len(target_files) > 0:
            result["target_files"] = target_files

        if len(self.targets) > 0:
            result["client_configs"] = list(self.targets)

        return result

    def send(self, *, wait_for_acknowledged_status: bool = True) -> dict[str, dict[str, Any]]:
        self.version += 1
        command = self.to_payload()
        return send_command(
            command, wait_for_acknowledged_status=wait_for_acknowledged_status, command_version=self.version
        )
