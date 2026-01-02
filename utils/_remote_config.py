# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import base64
import hashlib
import json
import re
import time
import uuid
from typing import Any
from collections.abc import Mapping

from utils._context.core import context
from utils.dd_constants import RemoteConfigApplyState as ApplyState
from utils.interfaces import library
from utils._logger import logger
from utils.proxy.mocked_response import (
    StaticJsonMockedTracerResponse,
    SequentialRemoteConfigJsonMockedTracerResponse,
    MockedBackendResponse,
)
from utils.proxy.tuf import build_signed_targets
from utils.proxy.rc_response_builder import build_rc_configurations_protobuf


class RemoteConfigStateResults:
    def __init__(self, version: int, state: ApplyState = ApplyState.UNKNOWN, configs: dict | None = None) -> None:
        self.version = version
        self.state = state
        self.configs: dict[str, dict] = configs if configs is not None else {}

    def to_json(self) -> dict:
        return {
            "version": self.version,
            "state": self.state,
            "configs": self.configs,
        }

    @staticmethod
    def from_json(d: dict) -> "RemoteConfigStateResults":
        return RemoteConfigStateResults(version=d["version"], state=d["state"], configs=d["configs"])


def send_state(
    raw_payload: dict, *, wait_for_acknowledged_status: bool = True, state_version: int = -1
) -> RemoteConfigStateResults:
    """Sends a remote config payload to the library and waits for the config to be applied.
    Then returns a dictionary with the state of each requested file as returned by the library.

    The dictionary keys are the IDs from the files that can be extracted from the path,
    e.g: datadog/2/ASM_FEATURES/asm_features_activation/config => asm_features_activation
    and the values contain the actual state for each file:

    1. a config state acknowledging the config
    2. else if not acknowledged, the last config state received
    3. if no config state received, then a hardcoded one with apply_state=UNKNOWN

    Args:
        raw_payload:
            The raw payload to send to the library.
        wait_for_acknowledged_status:
            If True, waits for the config to be acknowledged by the library.
            Else, only wait for the next request sent to /v0.7/config
        state_version:
            The version of the global state.
            It should be larger than previous versions if you want to apply a new config.

    """

    assert context.scenario.rc_api_enabled, f"Remote config API is not enabled on {context.scenario}"

    # Route to RC backend if enabled, otherwise use legacy proxy mock
    if getattr(context.scenario, "rc_backend_enabled", False):
        # Build protobuf on test runner side, send bytes to proxy
        rc_protobuf = build_rc_configurations_protobuf(raw_payload)
        MockedBackendResponse(path="/api/v0.1/configurations", content=rc_protobuf).send()
    else:
        StaticJsonMockedTracerResponse(path="/v0.7/config", mocked_json=raw_payload).send()

    client_configs = raw_payload.get("client_configs", [])

    current_states = RemoteConfigStateResults(version=state_version)
    targets = json.loads(base64.b64decode(raw_payload["targets"]))
    version = targets["signed"]["version"]
    for client_config in client_configs:
        _, _, product, config_id, _ = client_config.split("/")
        current_states.configs[config_id] = {
            "id": config_id,
            "product": product,
            "apply_state": ApplyState.UNKNOWN,
            "apply_error": "<No known response from the library>",
        }

    state = {}

    StaticJsonMockedTracerResponse(path="/v0.7/config", mocked_json=raw_payload).send()

    def remote_config_applied(data: dict) -> bool:
        nonlocal state
        if data["path"] != "/v0.7/config":
            return False

        state = data.get("request", {}).get("content", {}).get("client", {}).get("state", {})
        if len(client_configs) == 0:
            found = state["targets_version"] == state_version and state.get("config_states", []) == []
            if found:
                current_states.state = ApplyState.ACKNOWLEDGED
            return found

        if state["targets_version"] != version:
            return False

        config_states = state.get("config_states", [])
        for state in config_states:
            config_state = current_states.configs.get(state["id"])
            if config_state and state["product"] == config_state["product"]:
                logger.debug(f"Remote config state: {state}")
                config_state.update(state)

        if wait_for_acknowledged_status:
            for state in current_states.configs.values():
                if state["apply_state"] == ApplyState.UNKNOWN:
                    return False

        current_states.state = ApplyState.ACKNOWLEDGED
        return True

    library.wait_for(remote_config_applied, timeout=30)
    # ensure the library has enough time to apply the config to all subprocesses
    time.sleep(2)

    return current_states


def send_sequential_commands(commands: list[dict], *, wait_for_all_command: bool = True) -> None:
    """DEPRECATED"""

    if len(commands) == 0:
        raise ValueError("No commands to send")

    SequentialRemoteConfigJsonMockedTracerResponse(mocked_json_sequence=commands).send()

    if not wait_for_all_command:
        return

    counts_by_runtime_id: dict[str, int] = {}

    def all_payload_sent(data: dict) -> bool:
        if data["path"] != "/v0.7/config":
            return False

        # wait for N successful responses, +1 for the ACK request from the lib
        for count in counts_by_runtime_id.values():
            if count >= len(commands):
                return True

        runtime_id = data["request"]["content"]["client"]["client_tracer"]["runtime_id"]

        if runtime_id not in counts_by_runtime_id:
            counts_by_runtime_id[runtime_id] = 0

        for name, value in data["response"]["headers"]:
            if name == "st-proxy-overwrite-rc-response":
                counts_by_runtime_id[runtime_id] = int(value) + 1
                logger.debug(f"Response {int(value) + 1}/{len(commands)} for {runtime_id}")
                break

        return False

    rc_poll_interval = 5  # seconds
    extra_timeout = 10  # give more room for startup
    timeout = len(commands) * rc_poll_interval + extra_timeout
    logger.debug(f"Waiting for {timeout}s to see {len(commands)} responses")
    library.wait_for(all_payload_sent, timeout=timeout)


def _create_base_rcm():
    return {"targets": "", "target_files": [], "client_configs": []}


def _build_base_command(path_payloads: Mapping[str, Any], version: int):
    """Helper function to build a remote config command with common logic.

    Args:
        path_payloads: Dictionary mapping paths to their corresponding payloads
        version: The version number for the signed data

    """
    rcm = _create_base_rcm()

    if not path_payloads:
        signed = build_signed_targets(version, {})
        rcm["targets"] = _json_to_base64(signed)
        return rcm

    # Build targets dict first, then sign
    targets_dict = {}
    for path, payload in path_payloads.items():
        payload_64 = _json_to_base64(payload)
        payload_length = len(base64.b64decode(payload_64))

        target = {"custom": {"v": 1}, "hashes": {"sha256": _sha256(payload_64)}, "length": payload_length}
        targets_dict[path] = target

        target_file = {"path": path, "raw": payload_64}
        rcm["target_files"].append(target_file)
        rcm["client_configs"].append(path)

    # Sign after all targets are added
    signed = build_signed_targets(version, targets_dict)
    rcm["targets"] = _json_to_base64(signed)
    return rcm


def build_debugger_command(probes: list | None, version: int):
    if probes is None:
        return _build_base_command({}, version)

    path_payloads = {}
    for probe in probes:
        probe_path = re.sub(r"_([a-z])", lambda match: match.group(1).upper(), probe["type"].lower())
        path = f"datadog/2/LIVE_DEBUGGING/{probe_path}_{probe['id']}/config"
        path_payloads[path] = probe

    return _build_base_command(path_payloads, version)


def send_debugger_command(probes: list, version: int = 1) -> RemoteConfigStateResults:
    raw_payload = build_debugger_command(probes, version)
    return send_state(raw_payload)


def build_symdb_command(version: int):
    path_payloads = {"datadog/2/LIVE_DEBUGGING_SYMBOL_DB/symDb/config": {"upload_symbols": True}}
    return _build_base_command(path_payloads, version)


def send_symdb_command(version: int = 1) -> RemoteConfigStateResults:
    raw_payload = build_symdb_command(version)
    return send_state(raw_payload)


def build_apm_tracing_command(
    version: int,
    prev_payloads: list[dict[str, Any]],
    *,
    dynamic_instrumentation_enabled: bool | None = None,
    exception_replay_enabled: bool | None = None,
    live_debugging_enabled: bool | None = None,
    code_origin_enabled: bool | None = None,
    dynamic_sampling_enabled: bool | None = None,
    service_name: str | None = "weblog",
    env: str | None = "system-tests",
):
    lib_config: dict[str, str | bool] = {
        "library_language": "all",
        "library_version": "latest",
    }

    lib_config["tracing_enabled"] = True
    if dynamic_instrumentation_enabled is not None:
        lib_config["dynamic_instrumentation_enabled"] = dynamic_instrumentation_enabled
    if exception_replay_enabled is not None:
        lib_config["exception_replay_enabled"] = exception_replay_enabled
    if live_debugging_enabled is not None:
        lib_config["live_debugging_enabled"] = live_debugging_enabled
    if code_origin_enabled is not None:
        lib_config["code_origin_enabled"] = code_origin_enabled
    if dynamic_sampling_enabled is not None:
        lib_config["dynamic_sampling_enabled"] = dynamic_sampling_enabled

    config = {
        "schema_version": "v1.0.0",
        "action": "enable",
        "lib_config": lib_config,
        "service_target": {"service": service_name, "env": env},
    }

    path_payloads = {}
    for _config in prev_payloads:
        path_payloads[f"datadog/2/APM_TRACING/{uuid.uuid4()}/config"] = _config

    path_payloads[f"datadog/2/APM_TRACING/{uuid.uuid4()}/config"] = config
    prev_payloads.append(config)
    return _build_base_command(path_payloads, version)


def send_apm_tracing_command(
    *,
    dynamic_instrumentation_enabled: bool | None = None,
    exception_replay_enabled: bool | None = None,
    live_debugging_enabled: bool | None = None,
    code_origin_enabled: bool | None = None,
    dynamic_sampling_enabled: bool | None = None,
    service_name: str | None = "weblog",
    env: str | None = "system-tests",
    prev_payloads: list[dict[str, Any]] | None = None,
    version: int = 1,
) -> RemoteConfigStateResults:
    if prev_payloads is None:
        prev_payloads = []

    raw_payload = build_apm_tracing_command(
        version=version,
        prev_payloads=prev_payloads,
        dynamic_instrumentation_enabled=dynamic_instrumentation_enabled,
        exception_replay_enabled=exception_replay_enabled,
        live_debugging_enabled=live_debugging_enabled,
        code_origin_enabled=code_origin_enabled,
        dynamic_sampling_enabled=dynamic_sampling_enabled,
        service_name=service_name,
        env=env,
    )

    return send_state(raw_payload)


def _json_to_base64(json_object: dict) -> str:
    json_string = json.dumps(json_object, indent=2).encode("utf-8")
    return base64.b64encode(json_string).decode("utf-8")


def _sha256(value: str) -> str:
    return hashlib.sha256(base64.b64decode(value)).hexdigest()


class ClientConfig:
    _store: dict[str, "ClientConfig"] = {}

    def __init__(self, path: str, config: str | dict, config_file_version: int = 1) -> None:
        self.path = path

        self.raw = config if isinstance(config, str) else _json_to_base64(config)
        self.raw_decoded = base64.b64decode(self.raw).decode("utf-8")
        self.config_file_version = config_file_version

        if config is not None:
            self._store[path] = self
            self.raw_length = len(self.raw_decoded)
            self.raw_sha256 = hashlib.sha256(base64.b64decode(self.raw)).hexdigest()
        else:
            stored_config = self._store.get(path, None)
            if stored_config is None:
                raise ValueError(f"Config for {path} not found")
            self.raw_length = stored_config.raw_length
            self.raw_sha256 = stored_config.raw_sha256

    @property
    def raw_deserialized(self):
        return json.loads(self.raw_decoded)

    def get_target_file(self, *, deserialized: bool = False):
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


class _RemoteConfigState:
    """https://docs.google.com/document/d/1u_G7TOr8wJX0dOM_zUDKuRJgxoJU_hVTd5SeaMucQUs/edit#heading=h.octuyiil30ph
    https://github.com/DataDog/datadog-agent/blob/main/pkg/proto/datadog/remoteconfig/remoteconfig.proto#L180
    """

    backend_state = '{"foo": "bar"}'
    expires = "3000-01-01T00:00:00Z"
    spec_version = "1.0"
    _uniq = True

    def __init__(self, expires: str | None = None) -> None:
        if _RemoteConfigState._uniq:
            _RemoteConfigState._uniq = False
        else:
            raise RuntimeError("Only one instance of _RemoteConfigState can be created")
        self.targets: dict[str, ClientConfig] = {}
        self.version: int = 0
        self.expires: str = expires or _RemoteConfigState.expires
        self.opaque_backend_state = base64.b64encode(self.backend_state.encode("utf-8")).decode("utf-8")

    def set_config(self, path: str, config: dict, config_file_version: int | None = None) -> "_RemoteConfigState":
        """Set a file in current state."""
        client_config = ClientConfig(
            path=path,
            config=config,
            config_file_version=(self.version + 1) if config_file_version is None else config_file_version,
        )
        self.targets[path] = client_config
        return self

    def del_config(self, path: str) -> "_RemoteConfigState":
        """Remove a file in current state."""
        if path in self.targets:
            del self.targets[path]
        return self

    def reset(self) -> "_RemoteConfigState":
        """Remove all files."""
        self.targets.clear()
        return self

    def serialize_targets(self, *, deserialized: bool = False):
        targets_dict = {path: target.get_target() for path, target in self.targets.items()}
        result = build_signed_targets(
            version=self.version,
            targets=targets_dict,
            opaque_backend_state=self.opaque_backend_state,
            expires=self.expires,
        )

        return _json_to_base64(result) if not deserialized else result

    def to_payload(self, *, deserialized: bool = False):
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

    def apply(self, *, wait_for_acknowledged_status: bool = True) -> RemoteConfigStateResults:
        self.version += 1
        command = self.to_payload()
        return send_state(
            command, wait_for_acknowledged_status=wait_for_acknowledged_status, state_version=self.version
        )


rc_state = _RemoteConfigState()
