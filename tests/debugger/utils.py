# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import json
import re
import os
import os.path
from pathlib import Path
import uuid
from urllib.parse import parse_qs

from utils import interfaces, remote_config, weblog, context, logger
from utils.dd_constants import RemoteConfigApplyState as ApplyState


_CONFIG_PATH = "/v0.7/config"
_DEBUGGER_PATH = "/api/v2/debugger"
_LOGS_PATH = "/api/v2/logs"
_TRACES_PATH = "/api/v0.2/traces"
_SYMBOLS_PATH = "/symdb/v1/input"
_TELEMETRY_PATH = "/api/v2/apmtelemetry"

_CUR_DIR = str(Path(__file__).resolve().parent)


def read_probes(test_name: str) -> list:
    with open(os.path.join(_CUR_DIR, "probes/", test_name + ".json"), "r", encoding="utf-8") as f:
        return json.load(f)


def generate_probe_id(probe_type: str, suffix: str = "") -> str:
    uuid_str = str(uuid.uuid4())
    if suffix:
        # Replace the last len(suffix) characters of the UUID with the suffix
        uuid_str = uuid_str[: -len(suffix)] + suffix

    return probe_type + uuid_str[len(probe_type) :]


def extract_probe_ids(probes: dict | list) -> list:
    if not probes:
        return []

    if isinstance(probes, dict):
        return list(probes.keys())

    return [probe["id"] for probe in probes]


def _get_path(test_name: str, suffix: str) -> str:
    filename = test_name + "_" + BaseDebuggerTest.tracer["language"] + "_" + suffix + ".json"
    return os.path.join(_CUR_DIR, "approvals", filename)


def write_approval(data: list, test_name: str, suffix: str) -> None:
    with open(_get_path(test_name, suffix), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def read_approval(test_name: str, suffix: str) -> dict:
    with open(_get_path(test_name, suffix), "r", encoding="utf-8") as f:
        return json.load(f)


def get_env_bool(env_var_name: str, *, default: bool = False) -> bool:
    value = os.getenv(env_var_name, str(default)).lower()
    return value in {"true", "True", "1"}


class BaseDebuggerTest:
    tracer: dict[str, str] = {}

    probe_definitions: list[dict] = []
    probe_ids: list = []

    probe_diagnostics: dict = {}
    probe_snapshots: dict = {}
    probe_spans: dict = {}
    all_spans: list = []
    symbols: list = []

    rc_states: list[remote_config.RemoteConfigStateResults] = []
    weblog_responses: list = []

    setup_failures: list = []

    def initialize_weblog_remote_config(self) -> None:
        if self.get_tracer()["language"] in ["ruby"]:
            # Ruby tracer initializes remote configuration client from
            # middleware that is only invoked during request processing.
            # Therefore, we need to issue a request to the application for
            # remote config to start.
            response = weblog.get("/debugger/init")
            if response.status_code != 200:
                # This should fail the test immediately but the failure is
                # reported after all of the setup and the test are attempted
                self.setup_failures.append(
                    f"Failed to get /debugger/init: expected status code: 200, actual status code: {response.status_code}"
                )

    def method_and_language_to_line_number(self, method: str, language: str) -> list:
        """method_and_language_to_line_number returns the respective line number given the method and language"""
        definitions: dict[str, dict[str, list[int]]] = {
            "Budgets": {"java": [138], "dotnet": [136], "python": [142]},
            "Expression": {"java": [71], "dotnet": [74], "python": [72], "nodejs": [82]},
            # The `@exception` variable is not available in the context of line probes.
            "ExpressionException": {},
            "ExpressionOperators": {"java": [82], "dotnet": [90], "python": [87], "nodejs": [90]},
            "StringOperations": {"java": [87], "dotnet": [97], "python": [96], "nodejs": [96]},
            "CollectionOperations": {"java": [114], "dotnet": [114], "python": [123], "nodejs": [120]},
            "Nulls": {"java": [130], "dotnet": [127], "python": [136], "nodejs": [126]},
        }

        return definitions.get(method, {}).get(language, [])

    ###### set #####
    def set_probes(self, probes: list[dict]) -> None:
        def _enrich_probes(probes: list[dict]):
            def __get_probe_type(probe_id: str):
                if probe_id.startswith("log"):
                    return "LOG_PROBE"
                if probe_id.startswith("metric"):
                    return "METRIC_PROBE"
                if probe_id.startswith("span"):
                    return "SPAN_PROBE"
                if probe_id.startswith("decor"):
                    return "SPAN_DECORATION_PROBE"

                return "not_supported"

            language = self.get_tracer()["language"]

            for probe in probes:
                probe["language"] = language
                probe["evaluateAt"] = "EXIT"

                # PHP validates that the segments field is present.
                if "segments" not in probe:
                    probe["segments"] = []

                if probe["where"]["typeName"] == "ACTUAL_TYPE_NAME":
                    if language == "dotnet":
                        probe["where"]["typeName"] = "weblog.DebuggerController"
                    elif language == "java":
                        probe["where"]["typeName"] = "DebuggerController"
                        probe["where"]["methodName"] = (
                            probe["where"]["methodName"][0].lower() + probe["where"]["methodName"][1:]
                        )
                    elif language == "python":
                        probe["where"]["typeName"] = "debugger_controller"
                        probe["where"]["methodName"] = re.sub(
                            r"([a-z])([A-Z])", r"\1_\2", probe["where"]["methodName"]
                        ).lower()
                    elif language == "ruby":
                        probe["where"]["typeName"] = "DebuggerController"
                        probe["where"]["methodName"] = re.sub(
                            r"([a-z])([A-Z])", r"\1_\2", probe["where"]["methodName"]
                        ).lower()
                    elif language == "php":
                        probe["where"]["typeName"] = "DebuggerController"
                elif probe["where"]["sourceFile"] == "ACTUAL_SOURCE_FILE":
                    if language == "dotnet":
                        probe["where"]["sourceFile"] = "DebuggerController.cs"
                    elif language == "java":
                        probe["where"]["sourceFile"] = "DebuggerController.java"
                    elif language == "python":
                        probe["where"]["sourceFile"] = "debugger_controller.py"
                    elif language == "ruby":
                        # In docker container the controller will not have the
                        # shared/rails prefix, this is fine because DI will
                        # remove prefixes as part of file matching.
                        probe["where"]["sourceFile"] = "shared/rails/app/controllers/debugger_controller.rb"
                    elif language == "nodejs":
                        if context.weblog_variant == "express4-typescript":
                            probe["where"]["sourceFile"] = "debugger/index.ts"
                        else:
                            probe["where"]["sourceFile"] = "debugger/index.js"
                    elif language == "php":
                        probe["where"]["sourceFile"] = "debugger.php"
                probe["type"] = __get_probe_type(probe["id"])

            return probes

        def _extract_probe_ids(probes: list[dict]):
            return [probe["id"] for probe in probes]

        self.probe_definitions = _enrich_probes(probes)
        self.probe_ids = _extract_probe_ids(probes)

    ###### send #####
    _rc_version = 0

    def send_rc_probes(self, *, reset: bool = True) -> None:
        BaseDebuggerTest._rc_version += 1

        if reset:
            self.rc_states = []

        self.rc_states.append(
            remote_config.send_debugger_command(probes=self.probe_definitions, version=BaseDebuggerTest._rc_version)
        )

        # PHP tracer requires a request to /debugger/* to start logging the probe information.
        if context.library == "php":
            weblog.get("/debugger/init")

    def send_rc_apm_tracing(
        self,
        dynamic_instrumentation_enabled: bool | None = None,
        exception_replay_enabled: bool | None = None,
        live_debugging_enabled: bool | None = None,
        code_origin_enabled: bool | None = None,
        dynamic_sampling_enabled: bool | None = None,
        *,
        reset: bool = True,
    ) -> None:
        BaseDebuggerTest._rc_version += 1

        if reset:
            self.rc_states = []

        self.rc_states.append(
            remote_config.send_apm_tracing_command(
                dynamic_instrumentation_enabled=dynamic_instrumentation_enabled,
                exception_replay_enabled=exception_replay_enabled,
                live_debugging_enabled=live_debugging_enabled,
                code_origin_enabled=code_origin_enabled,
                dynamic_sampling_enabled=dynamic_sampling_enabled,
                version=BaseDebuggerTest._rc_version,
            )
        )

    def send_rc_symdb(self, *, reset: bool = True) -> None:
        BaseDebuggerTest._rc_version += 1
        if reset:
            self.rc_states = []

        self.rc_states.append(remote_config.send_symdb_command(BaseDebuggerTest._rc_version))

    def send_weblog_request(self, request_path: str, *, reset: bool = True) -> None:
        if reset:
            self.weblog_responses = []

        self.weblog_responses.append(weblog.get(request_path))

    ###### wait for #####
    _last_read = 0

    def wait_for_all_probes(self, statuses: list[str], timeout: int = 30) -> bool:
        self._wait_successful = False
        interfaces.agent.wait_for(lambda data: self._wait_for_all_probes(data, statuses=statuses), timeout=timeout)
        return self._wait_successful

    def _wait_for_all_probes(self, data: dict, statuses: list[str]):
        found_ids = set()

        def _check_all_probes_status(probe_diagnostics: dict, statuses: list[str]):
            statuses = statuses + ["ERROR"]
            logger.debug(f"Waiting for these probes to be in {statuses}: {self.probe_ids}")

            for expected_id in self.probe_ids:
                if expected_id not in probe_diagnostics:
                    continue

                probe_status = probe_diagnostics[expected_id]["status"]
                logger.debug(f"Probe {expected_id} observed status is {probe_status}")

                if probe_status in statuses:
                    found_ids.add(expected_id)
                    continue

                if self.get_tracer()["language"] == "dotnet" and statuses[0] == "INSTALLED":
                    probe = next(p for p in self.probe_definitions if p["id"] == expected_id)
                    # EMITTING is not implemented for dotnet span probe
                    if probe["type"] == "SPAN_PROBE":
                        found_ids.add(expected_id)
                        continue

            return set(self.probe_ids).issubset(found_ids)

        log_filename_found = re.search(r"/(\d+)__", data["log_filename"])
        if not log_filename_found:
            return False

        log_number = int(log_filename_found.group(1))
        if log_number >= BaseDebuggerTest._last_read:
            BaseDebuggerTest._last_read = log_number

        if data["path"] in [_DEBUGGER_PATH, _LOGS_PATH]:
            probe_diagnostics = self._process_diagnostics_data([data])
            logger.debug(probe_diagnostics)

            if not probe_diagnostics:
                logger.debug("Probes diagnostics is empty")
                return False

            self._wait_successful = _check_all_probes_status(probe_diagnostics, statuses)

        return self._wait_successful

    _exception_message = None
    _snapshot_found = False

    def wait_for_exception_snapshot_received(self, exception_message: str, timeout: int) -> bool:
        self._exception_message = exception_message
        self._snapshot_found = False

        interfaces.agent.wait_for(self._wait_for_snapshot_received, timeout=timeout)
        return self._snapshot_found

    def _wait_for_snapshot_received(self, data: dict):
        if data["path"] in [_LOGS_PATH, _DEBUGGER_PATH]:
            logger.debug("Reading " + data["log_filename"] + ", looking for '" + self._exception_message + "'")
            contents = data["request"].get("content", []) or []

            for content in contents:
                snapshot = content.get("debugger", {}).get("snapshot") or content.get("debugger.snapshot")

                if not snapshot or "probe" not in snapshot:
                    logger.debug("Snapshot doesn't have pobe")
                    continue

                if "exceptionId" not in snapshot:
                    logger.debug("Snapshot doesnt't have exception")
                    continue

                exception_message = self.get_exception_message(snapshot)

                logger.debug(f"Found exception message is {exception_message}")

                if self._exception_message and self._exception_message in exception_message:
                    self._snapshot_found = True
                    break

        logger.debug(f"Snapshot found: {self._snapshot_found}")
        return self._snapshot_found

    _no_capture_reason_span_found = False

    def wait_for_no_capture_reason_span(self, error_message: str, timeout: int) -> bool:
        self._error_message = error_message
        self._no_capture_reason_span_found = False

        interfaces.agent.wait_for(self._wait_for_no_capture_reason_span, timeout=timeout)
        return self._no_capture_reason_span_found

    def _wait_for_no_capture_reason_span(self, data: dict):
        if data["path"] == _TRACES_PATH:
            logger.debug(
                "Reading "
                + data["log_filename"]
                + ", looking for '_dd.debug.error.no_capture_reason' with error message '"
                + self._error_message
                + "'"
            )
            content = data["request"]["content"]

            if content:
                for payload in content["tracerPayloads"]:
                    for chunk in payload["chunks"]:
                        for span in chunk["spans"]:
                            meta = span.get("meta", {})

                            if "_dd.debug.error.no_capture_reason" in meta:
                                error_msg = meta.get("error.msg", "").lower()

                                logger.debug(
                                    f"Found span with _dd.debug.error.no_capture_reason: {meta['_dd.debug.error.no_capture_reason']}, error.msg: {error_msg}"
                                )

                                if self._error_message == error_msg:
                                    logger.debug(f"Error message '{self._error_message}' matches span error")

                                    self._no_capture_reason_span_found = True
                                    return True

        logger.debug(f"No capture reason span found: {self._no_capture_reason_span_found}")
        return self._no_capture_reason_span_found

    def wait_for_code_origin_span(self, timeout: int = 5) -> bool:
        self._span_found = False

        interfaces.agent.wait_for(self._wait_for_code_origin_span, timeout=timeout)
        return self._span_found

    _last_read_span = 0

    def _wait_for_code_origin_span(self, data: dict):
        if data["path"] == _TRACES_PATH:
            log_filename_found = re.search(r"/(\d+)__", data["log_filename"])
            if not log_filename_found:
                return False

            log_number = int(log_filename_found.group(1))
            if log_number >= BaseDebuggerTest._last_read_span:
                BaseDebuggerTest._last_read_span = log_number

                content = data["request"]["content"]
                if content:
                    for payload in content["tracerPayloads"]:
                        for chunk in payload["chunks"]:
                            for span in chunk["spans"]:
                                resource, resource_type = span.get("resource"), span.get("type")

                                if resource == "GET /healthcheck" and resource_type == "web":
                                    code_origin_type = span["meta"].get("_dd.code_origin.type", "")

                                    if code_origin_type == "entry":
                                        self._span_found = True
                                        return True

        return False

    def wait_for_telemetry(self, telemetry_type: str, timeout: int = 5) -> dict | None:
        self._telemetry: dict | None = None
        interfaces.agent.wait_for(
            lambda data: self._wait_for_telemetry(data, telemetry_type=telemetry_type), timeout=timeout
        )
        return self._telemetry

    def _wait_for_telemetry(self, data: dict, telemetry_type: str) -> bool:
        if data["path"] != _TELEMETRY_PATH:
            return False

        content = data.get("request", {}).get("content", {})
        payload = content.get("payload")

        if content.get("request_type") == telemetry_type:
            if payload["configuration"]:
                self._telemetry = payload
                return True

        if content.get("request_type") == "message-batch":
            for item in payload:
                if item.get("request_type") == telemetry_type:
                    self._telemetry = item
                    return True

        return False

    ###### collect #####
    def collect(self) -> None:
        self.get_tracer()

        self._collect_probe_diagnostics()
        self._collect_snapshots()
        self._collect_spans()
        self._collect_symbols()

    def _collect_probe_diagnostics(self):
        def _read_data():
            if context.library == "java":
                if context.library.version > "1.27.0":
                    path = _DEBUGGER_PATH
                else:
                    path = _LOGS_PATH
            elif context.library == "dotnet":
                if context.library.version > "2.49.0":
                    path = _DEBUGGER_PATH
                else:
                    path = _LOGS_PATH
            elif context.library in ("python", "ruby", "nodejs", "php"):
                path = _DEBUGGER_PATH
            else:
                path = _LOGS_PATH  # TODO: Should the default not be _DEBUGGER_PATH?

            logger.debug(f"Reading data from {path}")
            return list(interfaces.agent.get_data(path))

        all_data = _read_data()
        self.probe_diagnostics = self._process_diagnostics_data(all_data)

    def _process_diagnostics_data(self, datas: list[dict]):
        probe_diagnostics: dict = {}

        def _should_update_status(current_status: str, new_status: str):
            transitions = {
                "RECEIVED": True,
                "INSTALLED": new_status in ["INSTALLED", "EMITTING"],
                "EMITTING": new_status == "EMITTING",
            }
            return transitions.get(current_status, False)

        def _process_debugger(debugger: dict, query: str):
            if "diagnostics" in debugger:
                diagnostics = debugger["diagnostics"]
                probe_id = diagnostics["probeId"]
                status = diagnostics["status"]

                logger.debug(f"Processing probe diagnostics: {probe_id} - {status}")
                if probe_id in probe_diagnostics:
                    current_status = probe_diagnostics[probe_id]["status"]
                    if _should_update_status(current_status, status):
                        probe_diagnostics[probe_id]["status"] = status
                else:
                    probe_diagnostics[probe_id] = diagnostics

                probe_diagnostics[probe_id]["query"] = parse_qs(query)

        for data in datas:
            logger.debug(f"Processing data: {data['log_filename']}")
            contents = data["request"].get("content", []) or []  # Ensures contents is a list

            for content in contents:
                if "content" in content and isinstance(content["content"], list):
                    # content["content"] may be a dict, and not a list ?
                    for d_content in content["content"]:
                        assert isinstance(d_content, dict), f"Unexpected content: {json.dumps(content, indent=2)}"
                        _process_debugger(d_content["debugger"], data["query"])
                elif "debugger" in content:
                    _process_debugger(content["debugger"], data["query"])

        return probe_diagnostics

    def _collect_snapshots(self):
        def _get_snapshot_hash():
            # Collect snapshots from both the logs and debugger endpoints for compatibility for when we switched
            # snapshots to the debugger endpoint.
            agent_logs_endpoint_requests = list(interfaces.agent.get_data(_LOGS_PATH))
            agent_logs_endpoint_requests += list(interfaces.agent.get_data(_DEBUGGER_PATH))
            snapshot_hash: dict = {}

            for request in agent_logs_endpoint_requests:
                content = request["request"]["content"]
                if content:
                    for item in content:
                        snapshot = item.get("debugger", {}).get("snapshot") or item.get("debugger.snapshot")
                        item["query"] = parse_qs(request["query"])
                        if snapshot:
                            probe_id = snapshot["probe"]["id"]
                            if probe_id in snapshot_hash:
                                snapshot_hash[probe_id].append(item)
                            else:
                                snapshot_hash[probe_id] = [item]

            return snapshot_hash

        self.probe_snapshots = _get_snapshot_hash()

    def _collect_spans(self):
        def _get_spans_hash():
            agent_logs_endpoint_requests = list(interfaces.agent.get_data(_TRACES_PATH))
            span_hash: dict[str, list[dict]] = {}

            span_decoration_line_key = None
            if self.get_tracer()["language"] == "dotnet" or self.get_tracer()["language"] == "python":
                span_decoration_line_key = "_dd.di.SpanDecorationArgsAndLocals.probe_id"
            else:
                span_decoration_line_key = "_dd.di.spandecorationargsandlocals.probe_id"

            for request in agent_logs_endpoint_requests:
                content = request["request"]["content"]
                if content:
                    for payload in content["tracerPayloads"]:
                        for chunk in payload["chunks"]:
                            for span in chunk["spans"]:
                                self.all_spans.append(span)

                                is_span_decoration_method = span["name"] == "dd.dynamic.span"
                                if is_span_decoration_method:
                                    probe_id = span["meta"]["debugger.probeid"]
                                    if probe_id not in span_hash:
                                        span_hash[probe_id] = []
                                    span_hash[probe_id].append(span)
                                    continue

                                is_span_decoration_line = span_decoration_line_key in span["meta"]
                                if is_span_decoration_line:
                                    probe_id = span["meta"][span_decoration_line_key]
                                    if probe_id not in span_hash:
                                        span_hash[probe_id] = []
                                    span_hash[probe_id].append(span)
                                    continue

                                has_exception_id = "_dd.debug.error.exception_id" in span["meta"]
                                if has_exception_id:
                                    exception_id = span["meta"]["_dd.debug.error.exception_id"]
                                    if exception_id not in span_hash:
                                        span_hash[exception_id] = []
                                    span_hash[exception_id].append(span)
                                    continue

                                has_exception_capture_id = "_dd.debug.error.exception_capture_id" in span["meta"]
                                if has_exception_capture_id:
                                    if self.get_tracer()["language"] == "python":
                                        has_stack_trace = any(
                                            key.startswith("_dd.debug.error.") and key.endswith(".file")
                                            for key in span["meta"]
                                        )

                                        if has_stack_trace:
                                            for key in span["meta"]:
                                                if key.startswith("_dd.debug.error.") and key.endswith(".snapshot_id"):
                                                    snapshot_id = span["meta"][key]
                                                    if snapshot_id not in span_hash:
                                                        span_hash[snapshot_id] = []
                                                    span_hash[snapshot_id].append(span)
                                            continue
                                    else:
                                        capture_id = span["meta"]["_dd.debug.error.exception_capture_id"]
                                        if capture_id not in span_hash:
                                            span_hash[capture_id] = []
                                        span_hash[capture_id].append(span)
                                    continue

                                has_no_capture_reason = "_dd.debug.error.no_capture_reason" in span["meta"]
                                if has_no_capture_reason:
                                    error_msg = span["meta"].get("error.msg", "")
                                    if error_msg not in span_hash:
                                        span_hash[error_msg] = []
                                    span_hash[error_msg].append(span)
                                    continue

                                # For Python, we need to look for spans with stack trace information

            return span_hash

        self.probe_spans = _get_spans_hash()

    def _collect_symbols(self):
        def _get_symbols():
            result: list[dict] = []
            raw_data = list(interfaces.library.get_data(_SYMBOLS_PATH))

            if len(raw_data) == 0:
                logger.info(f"No request has been sent to {_SYMBOLS_PATH}")
                return result

            for data in raw_data:
                logger.debug(f"Processing data: {data['log_filename']}")
                if isinstance(data, dict) and "request" in data:
                    contents = data["request"].get("content", [])
                    for content in contents:
                        if isinstance(content, dict) and "system-tests-filename" in content:
                            result.append(content)

            return result

        self.symbols = _get_symbols()

    def get_tracer(self) -> dict[str, str]:
        if not BaseDebuggerTest.tracer:
            BaseDebuggerTest.tracer = {
                "language": context.library.name,
                "tracer_version": str(context.library.version),
            }

        return BaseDebuggerTest.tracer

    def assert_setup_ok(self) -> None:
        if self.setup_failures:
            assert "\n".join(self.setup_failures) is None

    def get_exception_message(self, snapshot: dict) -> str:
        if self.get_tracer()["language"] == "python":
            return next(iter(snapshot["captures"]["lines"].values()))["throwable"]["message"].lower()
        else:
            return snapshot["captures"]["return"]["throwable"]["message"].lower()

    ###### assert #####
    def assert_rc_state_not_error(self) -> None:
        assert self.rc_states, "RC states are empty"

        errors = []
        for entry in self.rc_states:
            for state in entry.configs.values():
                if "id" not in state:
                    continue

                rc_id = state["id"]
                logger.debug(f"Checking RC state for: {rc_id}")

                apply_state = state.get("apply_state")
                logger.debug(f"RC state for {rc_id} is {apply_state}")

                if apply_state == ApplyState.ERROR:
                    errors.append(f"State for {rc_id} is error: {state.get('apply_error')}")

        assert not errors, "\n".join(errors)

    def assert_all_probes_are_emitting(self) -> None:
        expected = self.probe_ids
        received = extract_probe_ids(self.probe_diagnostics)

        assert set(expected) <= set(
            received
        ), f"Not all probes were received. Missing ids: {', '.join(set(expected) - set(received))}"

        errors = {}
        for probe_id in self.probe_ids:
            status = self.probe_diagnostics[probe_id]["status"]

            if status == "EMITTING":
                continue

            if self.get_tracer()["language"] == "dotnet" and status == "INSTALLED":
                probe = next(p for p in self.probe_definitions if p["id"] == probe_id)
                # EMITTING is not implemented for dotnet span probe
                if probe["type"] == "SPAN_PROBE":
                    continue

            errors[probe_id] = status

        assert not errors, f"The following probes are not emitting: {errors}"

    def assert_all_weblog_responses_ok(self, expected_code: int = 200) -> None:
        assert len(self.weblog_responses) > 0, "No responses available."

        for respone in self.weblog_responses:
            assert respone.status_code == expected_code

    ###### assert #####

    def _get_path(self, test_name: str, suffix: str) -> str:
        filename = test_name + "_" + self.get_tracer()["language"] + "_" + suffix + ".json"
        return os.path.join(_CUR_DIR, "approvals", filename)

    def write_approval(self, data: list, test_name: str, suffix: str) -> None:
        with open(self._get_path(test_name, suffix), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def read_approval(self, test_name: str, suffix: str) -> dict:
        with open(self._get_path(test_name, suffix), "r", encoding="utf-8") as f:
            return json.load(f)
