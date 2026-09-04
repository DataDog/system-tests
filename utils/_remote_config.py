# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import base64
import hashlib
import json
import os
import re
import time
import uuid
from typing import Any, Literal
from collections.abc import Callable, Mapping

from utils._context.core import context

from utils.dd_constants import Capabilities, RemoteConfigApplyState as ApplyState
from utils.interfaces import library
from utils._logger import logger
from utils.proxy.mocked_response import (
    StaticJsonMockedTracerResponse,
    SequentialRemoteConfigJsonMockedTracerResponse,
    MockedBackendResponse,
)
from utils.proxy.tuf import build_signed_targets
from utils.proxy.rc_response_builder import build_rc_configurations_protobuf

RemoteConfigTarget = Literal["tracer", "backend"]


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
    raw_payload: dict,
    *,
    target: RemoteConfigTarget,
    wait_for_acknowledged_status: bool = True,
    state_version: int = -1,
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
        target:
            Where to send the config: "tracer" or "backend".
        wait_for_acknowledged_status:
            If True, waits for the config to be acknowledged by the library.
            Else, only wait for the next request sent to /v0.7/config
        state_version:
            The version of the global state.
            It should be larger than previous versions if you want to apply a new config.

    """

    api_enabled = context.scenario.rc_api_enabled
    backend_enabled = context.scenario.rc_backend_enabled

    assert api_enabled, f"Remote config API is not enabled on {context.scenario}"

    if target == "backend":
        assert backend_enabled, f"Remote config backend is not enabled on {context.scenario}"
        # Build protobuf on test runner side, send bytes to proxy
        rc_protobuf = build_rc_configurations_protobuf(raw_payload)
        MockedBackendResponse(path="/api/v0.1/configurations", content=rc_protobuf).send()
    elif target == "tracer":
        assert not backend_enabled, f"Remote config backend is enabled on {context.scenario}"
        StaticJsonMockedTracerResponse(path="/v0.7/config", mocked_json=raw_payload).send()
    else:
        raise ValueError(f"Invalid target: {target}")

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

    def remote_config_applied(data: dict) -> bool:
        nonlocal state
        if data["path"] != "/v0.7/config":
            return False

        state = data.get("request", {}).get("content", {}).get("client", {}).get("state", {})
        targets_version = state.get("targets_version")
        config_states = state.get("config_states", [])
        logger.info(
            f"RC poll: targets_version={targets_version} (waiting for {version}), config_states={config_states}"
        )

        if len(client_configs) == 0:
            found = state["targets_version"] == state_version and state.get("config_states", []) == []
            if found:
                current_states.state = ApplyState.ACKNOWLEDGED
            return found

        if state["targets_version"] != version:
            return False

        for state in config_states:
            config_state = current_states.configs.get(state["id"])
            if config_state and state["product"] == config_state["product"]:
                logger.debug(f"Remote config state: {state}")
                config_state.update(state)

        if wait_for_acknowledged_status:
            for state in current_states.configs.values():
                if state["apply_state"] == ApplyState.UNKNOWN:
                    logger.info(
                        f"RC config {state['id']} still unacknowledged: "
                        f"apply_state={state['apply_state']}, apply_error={state.get('apply_error')}"
                    )
                    return False

        current_states.state = ApplyState.ACKNOWLEDGED
        return True

    logger.info(f"Waiting for RC version={version}, client_configs={client_configs}")
    rv = library.wait_for(remote_config_applied, timeout=30)
    if not rv:
        logger.error(
            f"RC timed out. Last known state: targets_version={state.get('targets_version')}, "
            f"config_states={state.get('config_states', [])}"
        )
        logger.error(f"Expected version={version}, configs={list(current_states.configs.keys())}")
    # Opt-in fail-fast for Ruby RC timeouts (default off). Setup paths in CI
    # must not raise (.cursor/rules/pr-review.mdc §4); the default-off gate
    # keeps that invariant while letting local debugging see the failure at
    # the timeout point.
    if not rv and context.library == "ruby" and os.environ.get("SYSTEM_TESTS_FAIL_FAST", "").lower() == "true":
        raise AssertionError("Remote config was not applied")
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
    """Send a debugger command."""
    raw_payload = build_debugger_command(probes, version)
    # Use backend target for scenarios with rc_backend_enabled, tracer target otherwise
    target: RemoteConfigTarget = "backend" if context.scenario.rc_backend_enabled else "tracer"
    return send_state(raw_payload, target=target)


def build_symdb_command(version: int):
    path_payloads = {"datadog/2/LIVE_DEBUGGING_SYMBOL_DB/symDb/config": {"upload_symbols": True}}
    return _build_base_command(path_payloads, version)


def send_symdb_command(version: int = 1) -> RemoteConfigStateResults:
    """Send a symbol database command."""
    raw_payload = build_symdb_command(version)
    # Use backend target for scenarios with rc_backend_enabled, tracer target otherwise
    target: RemoteConfigTarget = "backend" if context.scenario.rc_backend_enabled else "tracer"
    return send_state(raw_payload, target=target)


####################################################################################
# SDK_CONFIGURATION payloads
#
# Libraries advertising the SDK_CONFIGURATION capability no longer read the legacy
# `lib_config` object of an APM_TRACING config. They read a `sdk_config` field
# instead, which carries the very same settings keyed by their canonical environment
# variable name, with values in their environment variable (string) form:
#
#   {
#     "schema_version": "v1.0.0",
#     "action": "enable",
#     "service_target": {"service": "weblog", "env": "system-tests"},
#     "sdk_config": {
#       "service_name": "weblog",
#       "env": "system-tests",
#       "config": {"DD_DYNAMIC_INSTRUMENTATION_ENABLED": "true"}
#     }
#   }
#
# `config` is a flat map, matching `jsonconf.SDKConfig` in dd-go
# (`remote-config/pkg/products/apmtracing/jsonconf/domain.go`). It used to be a list of
# `{key, value}` pairs; libraries still read that shape for configs stored before dd-go#14029,
# but the backend no longer produces it, so neither do we.
#
# `service_target` is unchanged: it still drives config matching and priority.
####################################################################################

# `lib_config` fields that describe the config itself instead of a library setting.
_LIB_CONFIG_METADATA_KEYS = frozenset({"env", "library_language", "library_version", "service_name"})

# Canonical environment variable name of each `lib_config` setting. `dynamic_sampling_enabled` and
# `live_debugging_enabled` map to `None`: both are real settings with their own capability bit, but
# they only ever existed as remote configs and have no environment variable counterpart, so there
# is nothing to send for them under SDK_CONFIGURATION. They stay listed rather than being removed,
# so that a setting missing from this table still reports as an unknown one.
APM_TRACING_ENV_VAR_NAMES: dict[str, str | None] = {
    "code_origin_enabled": "DD_CODE_ORIGIN_FOR_SPANS_ENABLED",
    "data_streams_enabled": "DD_DATA_STREAMS_ENABLED",
    "dynamic_instrumentation_enabled": "DD_DYNAMIC_INSTRUMENTATION_ENABLED",
    "dynamic_sampling_enabled": None,
    "exception_replay_enabled": "DD_EXCEPTION_REPLAY_ENABLED",
    "live_debugging_enabled": None,
    "log_injection_enabled": "DD_LOGS_INJECTION",
    "runtime_metrics_enabled": "DD_RUNTIME_METRICS_ENABLED",
    "tracing_debug": "DD_TRACE_DEBUG",
    "tracing_enabled": "DD_TRACE_ENABLED",
    "tracing_header_tags": "DD_TRACE_HEADER_TAGS",
    "tracing_sampling_rate": "DD_TRACE_SAMPLE_RATE",
    "tracing_sampling_rules": "DD_TRACE_SAMPLING_RULES",
    "tracing_service_mapping": "DD_SERVICE_MAPPING",
    "tracing_tags": "DD_TAGS",
}


def _serialize_header_tags(value: Any) -> str:  # noqa: ANN401
    """Turn [{"header": "X-Test", "tag_name": "test"}] into `X-Test:test`."""
    return ",".join(f"{tag['header']}:{tag['tag_name']}" if tag.get("tag_name") else tag["header"] for tag in value)


def _serialize_service_mapping(value: Any) -> str:  # noqa: ANN401
    """Turn [{"from_key": "a", "to_name": "b"}] into `a:b`."""
    return ",".join(f"{entry['from_key']}:{entry['to_name']}" for entry in value)


def _serialize_sampling_rules(value: Any) -> str:  # noqa: ANN401
    """Remote config rules use a list of tag clauses, DD_TRACE_SAMPLING_RULES uses a map."""
    rules = []
    for rule in value:
        rule = dict(rule)  # noqa: PLW2901
        if isinstance(rule.get("tags"), list):
            rule["tags"] = {tag["key"]: tag["value_glob"] for tag in rule["tags"]}
        rules.append(rule)

    return json.dumps(rules)


_SDK_CONFIG_SERIALIZERS: dict[str, Callable[[Any], str]] = {
    "tracing_header_tags": _serialize_header_tags,
    "tracing_sampling_rules": _serialize_sampling_rules,
    "tracing_service_mapping": _serialize_service_mapping,
    "tracing_tags": lambda value: ",".join(value),
}


def _serialize_sdk_config_value(key: str, value: Any) -> str:  # noqa: ANN401
    serializer = _SDK_CONFIG_SERIALIZERS.get(key)
    if serializer is not None:
        return serializer(value)

    # `isinstance(True, int)` is True, so booleans must be handled before numbers.
    if isinstance(value, bool):
        return "true" if value else "false"

    return str(value)


def to_sdk_config_payload(config: dict[str, Any]) -> dict[str, Any]:
    """Rewrite an APM_TRACING config from the legacy `lib_config` shape to the `sdk_config` one.

    Settings set to `None` are omitted: under SDK_CONFIGURATION, a setting missing from the
    payload is what tells the library to fall back to its local value, which is exactly what a
    `null` meant in `lib_config`.
    """
    service_target = config.get("service_target") or {}
    settings: dict[str, str] = {}

    for key, value in (config.get("lib_config") or {}).items():
        if key in _LIB_CONFIG_METADATA_KEYS or value is None:
            continue

        if key not in APM_TRACING_ENV_VAR_NAMES:
            logger.warning(f"No environment variable known for lib_config.{key}, not sent as SDK_CONFIGURATION")
            continue

        env_var_name = APM_TRACING_ENV_VAR_NAMES[key]
        if env_var_name is None:
            logger.debug(f"lib_config.{key} has no environment variable counterpart, not sent as SDK_CONFIGURATION")
            continue

        settings[env_var_name] = _serialize_sdk_config_value(key, value)

    sdk_config: dict[str, Any] = {}
    if service_target.get("service") is not None:
        sdk_config["service_name"] = service_target["service"]
    if service_target.get("env") is not None:
        sdk_config["env"] = service_target["env"]
    sdk_config["config"] = settings

    result = {key: value for key, value in config.items() if key != "lib_config"}
    result["sdk_config"] = sdk_config
    return result


# Every capability of the APM_TRACING family. SDK_CONFIGURATION is deliberately not one of them:
# it is the bit whose meaning is ambiguous (see `resolve_sdk_configuration_contract`), so it cannot
# serve as evidence that the library has registered its APM_TRACING remote config.
APM_TRACING_CAPABILITIES = frozenset(
    capability for capability in Capabilities if capability.name.startswith("APM_TRACING_")
)

# The per-setting APM_TRACING capabilities that SDK_CONFIGURATION replaces. A library on the new
# contract advertises the single SDK_CONFIGURATION bit instead of all of these.
LEGACY_APM_TRACING_CAPABILITIES = frozenset(
    {
        Capabilities.APM_TRACING_CUSTOM_TAGS,
        Capabilities.APM_TRACING_ENABLED,
        Capabilities.APM_TRACING_HTTP_HEADER_TAGS,
        Capabilities.APM_TRACING_LOGS_INJECTION,
        Capabilities.APM_TRACING_SAMPLE_RATE,
        Capabilities.APM_TRACING_SAMPLE_RULES,
    }
)


def resolve_sdk_configuration_contract(capabilities: set[Capabilities]) -> bool | None:
    """Decide which APM_TRACING payload shape a set of advertised capabilities asks for.

    Returns True for `sdk_config`, False for `lib_config`, and None when the capabilities seen so
    far cannot tell, so the caller should look again later.

    The SDK_CONFIGURATION bit alone is not enough to decide. Bit 49 is SDK_CONFIGURATION in the
    remote config source of truth (dd-source `remote-config/shared/libs/rc/capabilities.go`), but
    libdatadog hands the same bit to `ASM_RAW_RESPONSE_BODY`, so a libdatadog-based library such as
    dd-trace-php advertises it while still reading `lib_config`.

    Dropping the per-setting capabilities is the whole point of the unified bit, so their absence
    is what distinguishes the two. Absence only counts once the library has actually registered its
    APM_TRACING remote config, though: capabilities are added as products start, and AppSec ones
    come first, so an early poll from a libdatadog library shows bit 49 with no APM_TRACING bit yet
    and would otherwise be mistaken for the unified contract.
    """
    if not capabilities & APM_TRACING_CAPABILITIES:
        return None

    if capabilities & LEGACY_APM_TRACING_CAPABILITIES:
        return False

    return Capabilities.SDK_CONFIGURATION in capabilities


# Memoized once the capabilities are conclusive, both to skip re-scanning the whole /v0.7/config
# history on every payload and because a library that has not registered its APM_TRACING
# capabilities yet reports a partial set, which must not be cached.
_sdk_configuration_support: dict[str, bool] = {}


def resolve_sdk_configuration_support(get_capabilities: Callable[[], set[Capabilities]]) -> bool:
    """Whether the library reads its APM_TRACING settings from `sdk_config` instead of `lib_config`.

    `get_capabilities` returns the capabilities the library currently advertises. How to obtain
    them, and how long to wait for them, differs between the end-to-end interface and the
    parametric test agent, so that part stays with the caller; everything after it is shared.

    Falls back to `lib_config` whenever the answer is not yet knowable, which is the safe
    direction: a library on the unified contract ignores `lib_config` and its test fails visibly,
    whereas the reverse would silently apply nothing.
    """
    if "value" in _sdk_configuration_support:
        return _sdk_configuration_support["value"]

    try:
        capabilities = get_capabilities()
    except Exception as e:  # callers include setup methods, which must never fail
        logger.error(f"Could not read the RC capabilities ({e}), assuming no SDK_CONFIGURATION support")
        return False

    supported = resolve_sdk_configuration_contract(capabilities)
    if supported is None:
        logger.info("No APM_TRACING capability advertised yet, sending lib_config for now")
        return False

    logger.info(f"Library {'supports' if supported else 'does not support'} the SDK_CONFIGURATION capability")
    _sdk_configuration_support["value"] = supported
    return supported


def library_supports_sdk_configuration() -> bool:
    """End-to-end flavour of `resolve_sdk_configuration_support`."""
    if "value" in _sdk_configuration_support:
        return _sdk_configuration_support["value"]

    # Capabilities are only observable once the library has polled /v0.7/config at least once.
    # This returns straight away when such a request has already been seen.
    if not library.wait_for(lambda data: data["path"] == "/v0.7/config", timeout=30):
        logger.warning("No remote config request seen, assuming the library does not support SDK_CONFIGURATION")
        return False

    return resolve_sdk_configuration_support(library.get_rc_capabilities)


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
    use_sdk_config: bool = False,
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
    for _config in [*prev_payloads, config]:
        path_payloads[f"datadog/2/APM_TRACING/{uuid.uuid4()}/config"] = (
            to_sdk_config_payload(_config) if use_sdk_config else _config
        )

    # `prev_payloads` tracks the legacy shape: it is the input of the next command, and gets
    # translated on its way out just like this one.
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
        use_sdk_config=library_supports_sdk_configuration(),
    )

    # Use backend target for scenarios with rc_backend_enabled, tracer target otherwise
    target: RemoteConfigTarget = "backend" if context.scenario.rc_backend_enabled else "tracer"
    return send_state(raw_payload, target=target)


def build_combined_apm_tracing_and_debugger_command(
    version: int,
    prev_payloads: list[dict[str, Any]],
    probes: list | None = None,
    *,
    dynamic_instrumentation_enabled: bool | None = None,
    exception_replay_enabled: bool | None = None,
    live_debugging_enabled: bool | None = None,
    code_origin_enabled: bool | None = None,
    dynamic_sampling_enabled: bool | None = None,
    service_name: str | None = "weblog",
    env: str | None = "system-tests",
    use_sdk_config: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build a single RC command containing both APM_TRACING and LIVE_DEBUGGING configs.

    Remote Config's client_configs field represents the COMPLETE list of configs that should
    be active. Sending separate payloads causes previously applied configs to be unapplied
    if they're not in the new client_configs list, regardless of product filtering.

    Returns:
        A tuple of (rc_command, apm_config). The caller should update prev_payloads with
        the returned apm_config if tracking state across multiple calls. `apm_config` is always
        in the legacy `lib_config` shape, whatever shape was sent, as that is what the next
        call inherits its defaults from.

    """
    path_payloads: dict[str, Any] = {}

    # Build new APM_TRACING config by merging with previous config (if any)
    lib_config: dict[str, str | bool] = {
        "library_language": "all",
        "library_version": "latest",
    }

    # If there's a previous config, inherit its lib_config fields as defaults.
    # This enables tests to send sequential configs that only specify changed values
    # (e.g., calling with enabled=None after enabled=True preserves the True value).
    if prev_payloads:
        prev_lib_config = prev_payloads[-1].get("lib_config", {})
        # Copy previous fields, but allow new values to override
        lib_config |= {
            key: value
            for key, value in prev_lib_config.items()
            if key not in ["library_language", "library_version", "tracing_enabled"]
        }

    # Apply new values (overriding previous ones)
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

    apm_config = {
        "schema_version": "v1.0.0",
        "action": "enable",
        "lib_config": lib_config,
        "service_target": {"service": service_name, "env": env},
    }

    # Only send the latest APM_TRACING config, not all previous ones
    path_payloads[f"datadog/2/APM_TRACING/{uuid.uuid4()}/config"] = (
        to_sdk_config_payload(apm_config) if use_sdk_config else apm_config
    )

    # Add LIVE_DEBUGGING configs (probes)
    if probes:
        for probe in probes:
            probe_path = re.sub(r"_([a-z])", lambda match: match.group(1).upper(), probe["type"].lower())
            path = f"datadog/2/LIVE_DEBUGGING/{probe_path}_{probe['id']}/config"
            path_payloads[path] = probe

    return _build_base_command(path_payloads, version), apm_config


def send_combined_apm_tracing_and_debugger_command(
    prev_payloads: list[dict[str, Any]],
    probes: list | None = None,
    *,
    dynamic_instrumentation_enabled: bool | None = None,
    exception_replay_enabled: bool | None = None,
    live_debugging_enabled: bool | None = None,
    code_origin_enabled: bool | None = None,
    dynamic_sampling_enabled: bool | None = None,
    service_name: str | None = "weblog",
    env: str | None = "system-tests",
    version: int = 1,
) -> RemoteConfigStateResults:
    """Send a single RC command containing both APM_TRACING and LIVE_DEBUGGING configs.

    Note: This function updates prev_payloads in place with the new config, replacing
    all previous entries. This allows callers to track state across sequential calls.
    """
    raw_payload, apm_config = build_combined_apm_tracing_and_debugger_command(
        version,
        prev_payloads,
        probes,
        dynamic_instrumentation_enabled=dynamic_instrumentation_enabled,
        exception_replay_enabled=exception_replay_enabled,
        live_debugging_enabled=live_debugging_enabled,
        code_origin_enabled=code_origin_enabled,
        dynamic_sampling_enabled=dynamic_sampling_enabled,
        service_name=service_name,
        env=env,
        use_sdk_config=library_supports_sdk_configuration(),
    )

    # Update prev_payloads with just the new config (don't accumulate)
    prev_payloads.clear()
    prev_payloads.append(apm_config)

    # Use backend target for scenarios with rc_backend_enabled, tracer target otherwise
    target: RemoteConfigTarget = "backend" if context.scenario.rc_backend_enabled else "tracer"
    return send_state(raw_payload, target=target)


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
        return f"""({self.path!r}, {self.raw_deserialized!r}, {self.config_file_version})"""


class _RemoteConfigState:
    """Base class for remote config state management.

    See module-level singletons `tracer_rc_state` and `backend_rc_state` for usage.

    References:
    - https://docs.google.com/document/d/1u_G7TOr8wJX0dOM_zUDKuRJgxoJU_hVTd5SeaMucQUs/edit#heading=h.octuyiil30ph
    - https://github.com/DataDog/datadog-agent/blob/main/pkg/proto/datadog/remoteconfig/remoteconfig.proto#L180

    """

    backend_state = '{"foo": "bar"}'
    expires = "3000-01-01T00:00:00Z"
    spec_version = "1.0"
    _instances: dict[RemoteConfigTarget, "_RemoteConfigState"] = {}

    def __init__(self, target: RemoteConfigTarget, expires: str | None = None) -> None:
        if target in _RemoteConfigState._instances:
            raise RuntimeError(
                f"Only one instance of _RemoteConfigState can be created per target, got duplicate for {target!r}"
            )
        _RemoteConfigState._instances[target] = self
        self.target: RemoteConfigTarget = target
        self.targets: dict[str, ClientConfig] = {}
        self.version: int = 0
        self.expires: str = expires or _RemoteConfigState.expires
        self.opaque_backend_state = base64.b64encode(self.backend_state.encode("utf-8")).decode("utf-8")
        self._reset_pending: bool = False

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
        self._reset_pending = True
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
        # Go and Java require an explicit empty-config apply before new configs are
        # sent; without it, previously-loaded configs are not deactivated between runs.
        if self._reset_pending and self.targets and context.library.name in ("golang", "java"):
            saved = dict(self.targets)
            self.targets.clear()
            self.version += 1
            send_state(self.to_payload(), target=self.target, state_version=self.version)
            self.targets = saved

        self._reset_pending = False
        self.version += 1
        command = self.to_payload()
        return send_state(
            command,
            target=self.target,
            wait_for_acknowledged_status=wait_for_acknowledged_status,
            state_version=self.version,
        )


tracer_rc_state = _RemoteConfigState(target="tracer")
"""Remote config state for tracer-based scenarios (rc_backend_enabled=False).

Use this singleton for scenarios that send RC configs via the legacy proxy mock
at /v0.7/config. This is the default for most appsec and feature flag scenarios.

The scenario must NOT have rc_backend_enabled=True.
"""

backend_rc_state = _RemoteConfigState(target="backend")
"""Remote config state for backend-based scenarios (rc_backend_enabled=True).

Use this singleton for scenarios that send RC configs via the mocked backend
at /api/v0.1/configurations (protobuf). This is used for debugger scenarios
and other scenarios that require the agent's RC backend path.

The scenario MUST have rc_backend_enabled=True.
"""
