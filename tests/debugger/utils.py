# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import json
import re
import os
import os.path
import uuid

from packaging import version

from utils import interfaces, remote_config, weblog, context
from utils.tools import logger
from utils.dd_constants import RemoteConfigApplyState as ApplyState


_CONFIG_PATH = "/v0.7/config"
_DEBUGGER_PATH = "/api/v2/debugger"
_LOGS_PATH = "/api/v2/logs"
_TRACES_PATH = "/api/v0.2/traces"

_CUR_DIR = os.path.dirname(os.path.abspath(__file__))


def read_probes(test_name: str):
    with open(os.path.join(_CUR_DIR, "probes/", test_name + ".json"), "r", encoding="utf-8") as f:
        return json.load(f)


def generate_probe_id(probe_type: str):
    return probe_type + str(uuid.uuid4())[len(probe_type) :]


def extract_probe_ids(probes):
    if probes:
        if isinstance(probes, dict):
            return list(probes.keys())

        return [probe["id"] for probe in probes]

    return []


def _get_path(test_name, suffix):
    filename = test_name + "_" + _Base_Debugger_Test.tracer["language"] + "_" + suffix + ".json"
    path = os.path.join(_CUR_DIR, "approvals", filename)
    return path


def write_approval(data, test_name, suffix):
    with open(_get_path(test_name, suffix), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def read_approval(test_name, suffix):
    with open(_get_path(test_name, suffix), "r", encoding="utf-8") as f:
        return json.load(f)


class _Base_Debugger_Test:
    tracer = None

    probe_definitions = []
    probe_ids = []

    probe_diagnostics = {}
    probe_snapshots = {}
    probe_spans = {}

    rc_state = None
    weblog_responses = []

    ###### set #####
    def set_probes(self, probes):
        def _enrich_probes(probes):
            def __get_probe_type(probe_id):
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
                elif probe["where"]["sourceFile"] == "ACTUAL_SOURCE_FILE":
                    if language == "dotnet":
                        probe["where"]["sourceFile"] = "DebuggerController.cs"
                    elif language == "java":
                        probe["where"]["sourceFile"] = "DebuggerController.java"
                    elif language == "python":
                        probe["where"]["sourceFile"] = "debugger_controller.py"
                    elif language == "ruby":
                        probe["where"]["sourceFile"] = "debugger_controller.rb"
                probe["type"] = __get_probe_type(probe["id"])

            return probes

        def _extract_probe_ids(probes):
            return [probe["id"] for probe in probes]

        self.probe_definitions = _enrich_probes(probes)
        self.probe_ids = _extract_probe_ids(probes)

    ###### send #####
    _rc_version = 0

    def send_rc_probes(self):
        _Base_Debugger_Test._rc_version += 1

        self.rc_state = remote_config.send_debugger_command(
            probes=self.probe_definitions, version=_Base_Debugger_Test._rc_version
        )

    def send_weblog_request(self, request_path: str, reset: bool = True):
        if reset:
            self.weblog_responses = []

        self.weblog_responses.append(weblog.get(request_path))

    ###### wait for #####
    _last_read = 0

    def wait_for_all_probes_installed(self, timeout=30):
        interfaces.agent.wait_for(lambda data: self._wait_for_all_probes(data, status="INSTALLED"), timeout=timeout)

    def wait_for_all_probes_emitting(self, timeout=30):
        interfaces.agent.wait_for(lambda data: self._wait_for_all_probes(data, status="EMITTING"), timeout=timeout)

    def _wait_for_all_probes(self, data, status):
        found_ids = set()

        def _check_all_probes_status(probe_diagnostics, status):
            logger.debug(f"Waiting for these probes to be {status}: {self.probe_ids}")

            for expected_id in self.probe_ids:
                if expected_id in probe_diagnostics:
                    probe_status = probe_diagnostics[expected_id]["status"]

                    logger.debug(f"Probe {expected_id} observed status is {probe_status}")
                    if probe_status == status or probe_status == "ERROR":
                        found_ids.add(expected_id)

            if set(self.probe_ids).issubset(found_ids):
                logger.debug(f"Success: all probes are {status}")
                return True

            return False

        all_probes_ready = False

        log_filename_found = re.search(r"/(\d+)__", data["log_filename"])
        if not log_filename_found:
            return False

        log_number = int(log_filename_found.group(1))
        if log_number >= _Base_Debugger_Test._last_read:
            _Base_Debugger_Test._last_read = log_number

        if data["path"] in [_DEBUGGER_PATH, _LOGS_PATH]:
            probe_diagnostics = self._process_diagnostics_data([data])
            logger.debug(probe_diagnostics)

            if not probe_diagnostics:
                logger.debug("Probes diagnostics is empty")
                return False

            all_probes_ready = _check_all_probes_status(probe_diagnostics, status)

        return all_probes_ready

    _method_name = None
    _exception_message = None
    _snapshot_found = False

    def wait_for_snapshot_received(self, method_name, exception_message=None, timeout=1):
        self._method_name = method_name
        self._exception_message = exception_message
        self._snapshot_found = False

        interfaces.agent.wait_for(self._wait_for_snapshot_received, timeout=timeout)
        return self._snapshot_found

    def _wait_for_snapshot_received(self, data):
        # log_number = int(re.search(r"/(\d+)__", data["log_filename"]).group(1))
        # if log_number >= self._last_read:
        #     self._last_read = log_number

        if data["path"] == _LOGS_PATH:
            logger.debug("Reading " + data["log_filename"] + ", looking for " + self._method_name)
            contents = data["request"].get("content", []) or []

            logger.debug("len is")
            logger.debug(len(contents))

            for content in contents:
                snapshot = content.get("debugger", {}).get("snapshot") or content.get("debugger.snapshot")

                if not snapshot:
                    continue

                if (
                    "probe" not in snapshot
                    or "location" not in snapshot["probe"]
                    or "method" not in snapshot["probe"]["location"]
                ):
                    continue

                method = snapshot["probe"]["location"]["method"]

                if not isinstance(method, str):
                    continue

                method = method.lower().replace("_", "")
                logger.debug("Found method " + method)

                if method == self._method_name:
                    if self._exception_message:
                        exception_message = snapshot["captures"]["return"]["throwable"]["message"].lower()
                        logger.debug("Exception message is " + exception_message)
                        logger.debug("Self Exception message is " + self._exception_message)

                        found = re.search(self._exception_message, exception_message)
                        logger.debug(found)

                        if re.search(self._exception_message, exception_message):
                            self._snapshot_found = True
                            break
                    else:
                        self._snapshot_found = True
                        break

        logger.debug(f"Snapshot found: {self._snapshot_found}")
        return self._snapshot_found

    ###### collect #####
    def collect(self):
        self.get_tracer()

        self._collect_probe_diagnostics()
        self._collect_snapshots()
        self._collect_spans()

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
            elif context.library == "python":
                path = _DEBUGGER_PATH
            elif context.library == "ruby":
                path = _DEBUGGER_PATH
            else:
                path = _LOGS_PATH

            return list(interfaces.agent.get_data(path))

        all_data = _read_data()
        self.probe_diagnostics = self._process_diagnostics_data(all_data)

    def _process_diagnostics_data(self, datas):
        probe_diagnostics = {}

        def _process_debugger(debugger):
            if "diagnostics" in debugger:
                diagnostics = debugger["diagnostics"]

                probe_id = diagnostics["probeId"]
                status = diagnostics["status"]

                # update status
                if probe_id in probe_diagnostics:
                    current_status = probe_diagnostics[probe_id]["status"]
                    if current_status == "RECEIVED":
                        probe_diagnostics[probe_id]["status"] = status
                    elif current_status == "INSTALLED" and status in ["INSTALLED", "EMITTING"]:
                        probe_diagnostics[probe_id]["status"] = status
                    elif current_status == "EMITTING" and status == "EMITTING":
                        probe_diagnostics[probe_id]["status"] = status
                # set new status
                else:
                    probe_diagnostics[probe_id] = diagnostics

        for data in datas:
            contents = data["request"].get("content", []) or []  # Ensures contents is a list

            for content in contents:
                if "content" in content:
                    d_contents = content["content"]
                    for d_content in d_contents:
                        if isinstance(d_content, dict):
                            _process_debugger(d_content["debugger"])
                else:
                    if "debugger" in content:
                        if isinstance(content, dict):
                            _process_debugger(content["debugger"])

        return probe_diagnostics

    def _collect_snapshots(self):
        def _get_snapshot_hash():
            agent_logs_endpoint_requests = list(interfaces.agent.get_data(_LOGS_PATH))
            snapshot_hash = {}

            for request in agent_logs_endpoint_requests:
                content = request["request"]["content"]
                if content:
                    for item in content:
                        snapshot = item.get("debugger", {}).get("snapshot") or item.get("debugger.snapshot")
                        if snapshot:
                            probe_id = snapshot["probe"]["id"]
                            if probe_id in snapshot_hash:
                                snapshot_hash[probe_id].append(item)
                            else:
                                snapshot_hash[probe_id] = [item]

            return snapshot_hash

        self.probe_snapshots = _get_snapshot_hash()

    def _collect_spans(self):
        def _get_spans_hash(self):
            agent_logs_endpoint_requests = list(interfaces.agent.get_data(_TRACES_PATH))
            span_hash = {}

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
                                is_span_decoration_method = span["name"] == "dd.dynamic.span"
                                if is_span_decoration_method:
                                    span_hash[span["meta"]["debugger.probeid"]] = span
                                    continue

                                is_span_decoration_line = span_decoration_line_key in span["meta"]
                                if is_span_decoration_line:
                                    span_hash[span["meta"][span_decoration_line_key]] = span
                                    continue

                                is_exception_replay = "_dd.debug.error.exception_id" in span["meta"]
                                if is_exception_replay:
                                    span_hash[span["meta"]["_dd.debug.error.exception_id"]] = span
                                    continue

            return span_hash

        self.probe_spans = _get_spans_hash(self)

    def get_tracer(self):
        if not _Base_Debugger_Test.tracer:
            _Base_Debugger_Test.tracer = {
                "language": str(context.library).split("@")[0],
                "tracer_version": str(context.library.version),
            }

        return _Base_Debugger_Test.tracer

    ###### assert #####
    def assert_rc_state_not_error(self):
        assert self.rc_state, "RC states are empty"

        errors = []
        for probe in self.probe_definitions:
            rc_id = re.sub(r"_([a-z])", lambda match: match.group(1).upper(), probe["type"].lower()) + "_" + probe["id"]

            logger.debug(f"Checking RC state for: {rc_id}")

            if rc_id not in self.rc_state:
                errors.append(f"ID {rc_id} not found in state")
            else:
                apply_state = self.rc_state[rc_id]["apply_state"]
                logger.debug(f"RC stace for {rc_id} is {apply_state}")

                if apply_state == ApplyState.ERROR:
                    errors.append(f"State for {rc_id} is error: {self.rc_state[rc_id]['apply_error']}")

        assert not errors, "\n".join(errors)

    def assert_all_probes_are_installed(self):
        expected = self.probe_ids
        received = extract_probe_ids(self.probe_diagnostics)

        missing_probes = set(expected) - set(received)
        if missing_probes:
            assert not missing_probes, f"Not all probes are installed. Missing ids: {', '.join(missing_probes)}"

    def assert_all_weblog_responses_ok(self, expected_code=200):
        assert len(self.weblog_responses) > 0, "No responses available."

        for respone in self.weblog_responses:
            logger.debug(f"Response is {respone.text}")
            assert respone.status_code == expected_code
