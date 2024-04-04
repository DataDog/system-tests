# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import json
import re

from packaging import version

from utils import interfaces
from utils.tools import logger

_CONFIG_PATH = "/v0.7/config"
_DEBUGER_PATH = "/api/v2/debugger"
_LOGS_PATH = "/api/v2/logs"
_TRACES_PATH = "/api/v0.2/traces"
# dummy change for triggering ci


def read_diagnostic_data():
    tracer = list(interfaces.library.get_data(_CONFIG_PATH))[0]["request"]["content"]["client"]["client_tracer"]

    tracer_version = version.parse(re.sub(r"[^0-9.].*$", "", tracer["tracer_version"]))
    if tracer["language"] == "java":
        if tracer_version > version.parse("1.27.0"):
            path = _DEBUGER_PATH
        else:
            path = _LOGS_PATH
    elif tracer["language"] == "dotnet":
        if tracer_version > version.parse("2.49.0"):
            path = _DEBUGER_PATH
        else:
            path = _LOGS_PATH
    else:
        path = _LOGS_PATH

    return list(interfaces.agent.get_data(path))


def get_probes_map(data_set):
    probe_hash = {}

    def process_debugger(debugger):
        if "diagnostics" in debugger:
            diagnostics = debugger["diagnostics"]
            probe_hash[diagnostics["probeId"]] = diagnostics

    for data in data_set:
        contents = data["request"].get("content", []) or []  # Ensures contents is a list
        for content in contents:
            if "content" in content:
                d_contents = json.loads(content["content"])
                for d_content in d_contents:
                    process_debugger(d_content["debugger"])
            else:
                process_debugger(content["debugger"])

    return probe_hash


def validate_probes(expected_probes):
    def check_probe_status(expected_id, expected_status, probe_status_map):
        if expected_id not in probe_status_map:
            raise ValueError("Probe " + expected_id + " was not received.")

        actual_status = probe_status_map[expected_id]["status"]
        if actual_status != expected_status and not (expected_status == "INSTALLED" and actual_status == "EMITTING"):
            raise ValueError(
                "Received probe "
                + expected_id
                + " with status "
                + actual_status
                + ", but expected for "
                + expected_status
            )

    probe_map = get_probes_map(read_diagnostic_data())
    for expected_id, expected_status in expected_probes.items():
        check_probe_status(expected_id, expected_status, probe_map)


def validate_snapshots(expected_snapshots):
    def get_snapshot_map():
        agent_logs_endpoint_requests = list(interfaces.agent.get_data(_LOGS_PATH))
        snapshot_hash = {}

        for request in agent_logs_endpoint_requests:
            content = request["request"]["content"]
            if content is not None:
                for content in content:
                    debugger = content["debugger"]
                    if "snapshot" in debugger:
                        probe_id = debugger["snapshot"]["probe"]["id"]
                        snapshot_hash[probe_id] = debugger["snapshot"]

        return snapshot_hash

    def check_snapshot(expected_id, snapshot_status_map):
        if expected_id not in snapshot_status_map:
            raise ValueError("Snapshot " + expected_id + " was not received.")

    snapshot_map = get_snapshot_map()
    for expected_snapshot in expected_snapshots:
        check_snapshot(expected_snapshot, snapshot_map)


def validate_spans(expected_spans):
    def get_span_map():
        agent_logs_endpoint_requests = list(interfaces.agent.get_data(_TRACES_PATH))
        span_hash = {}
        for request in agent_logs_endpoint_requests:
            content = request["request"]["content"]
            if content is not None:
                for payload in content["tracerPayloads"]:
                    for chunk in payload["chunks"]:
                        for span in chunk["spans"]:
                            if span["name"] == "dd.dynamic.span":
                                span_hash[span["meta"]["debugger.probeid"]] = span
                            else:
                                for key, value in span["meta"].items():
                                    if key.startswith("_dd.di"):
                                        span_hash[value] = span["meta"][key.split(".")[2]]

        return span_hash

    def check_trace(expected_id, trace_map):
        if expected_id not in trace_map:
            raise ValueError("Trace " + expected_id + " was not received.")

    span_map = get_span_map()
    for expected_trace in expected_spans:
        check_trace(expected_trace, span_map)


class _Base_Debugger_Snapshot_Test:
    expected_probe_ids = []
    all_probes_installed = False

    def assert_remote_config_is_sent(self):
        for data in interfaces.library.get_data(_CONFIG_PATH):
            logger.debug(f"Found config in {data['log_filename']}")
            if "client_configs" in data.get("response", {}).get("content", {}):
                return

        raise ValueError("I was expecting a remote config")

    def _is_all_probes_installed(self, probes_map):
        if probes_map is None:
            return False

        installed_ids = set()
        for expected_id in self.expected_probe_ids:
            if expected_id in probes_map:
                if probes_map[expected_id]["status"] == "INSTALLED":
                    installed_ids.add(expected_id)

        if set(self.expected_probe_ids).issubset(installed_ids):
            logger.debug(f"Succes: found probes {installed_ids}")
            return True

        missings_ids = set(self.expected_probe_ids) - set(installed_ids)

        logger.debug(f"Found some probes, but not all of them. Missing probes are {missings_ids}")

    def wait_for_all_probes_installed(self, data):
        if data["path"] == _DEBUGER_PATH or data["path"] == _LOGS_PATH:
            if self._is_all_probes_installed(get_probes_map([data])):
                self.all_probes_installed = True

        return self.all_probes_installed

    def assert_all_probes_are_installed(self):
        data_debug = interfaces.agent.get_data(_DEBUGER_PATH)
        for data in data_debug:
            self.wait_for_all_probes_installed(data)

        if not self.all_probes_installed:
            raise ValueError("At least one probe is missing")
