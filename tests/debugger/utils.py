# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import json
import re
import os
import os.path

from packaging import version

from utils import interfaces
from utils.tools import logger
from utils.dd_constants import RemoteConfigApplyState as ApplyState

_CONFIG_PATH = "/v0.7/config"
_DEBUGER_PATH = "/api/v2/debugger"
_LOGS_PATH = "/api/v2/logs"
_TRACES_PATH = "/api/v0.2/traces"

_CUR_DIR = os.path.dirname(os.path.abspath(__file__))


def read_probes(test_name: str):
    with open(os.path.join(_CUR_DIR, "probes/", test_name + ".json"), "r", encoding="utf-8") as f:
        return json.load(f)


def extract_probe_ids(probes):
    return [probe["id"] for probe in probes]


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


class _Base_Debugger_Test:
    weblog_responses = []
    expected_probe_ids = []
    rc_state = None
    all_probes_installed = False

    def wait_for_all_probes_installed(self, data):
        def _all_probes_installed(self, probes_map):
            if not probes_map:
                logger.debug("Probes map is empty")
                return False

            installed_ids = set()
            logger.debug(f"Look for these probes: {self.expected_probe_ids}")
            for expected_id in self.expected_probe_ids:
                if expected_id in probes_map:
                    status = probes_map[expected_id]["status"]

                    logger.debug(f"Probe {expected_id} observed status is {status}")
                    if status == "INSTALLED":
                        installed_ids.add(expected_id)

            if set(self.expected_probe_ids).issubset(installed_ids):
                logger.debug(f"Succes: found all probes")
                return True

            missing_probes = set(self.expected_probe_ids) - set(installed_ids)
            logger.debug(f"Found some probes, but not all of them. Missing probes are {missing_probes}")
            return False

        if data["path"] == _DEBUGER_PATH or data["path"] == _LOGS_PATH:
            self.all_probes_installed = _all_probes_installed(self, get_probes_map([data]))

        return self.all_probes_installed

    def assert_all_probes_are_installed(self):
        if not self.all_probes_installed:
            raise ValueError("At least one probe is missing")

    def assert_all_weblog_responses_ok(self):
        assert len(self.weblog_responses) > 0, "No responses available."

        for respone in self.weblog_responses:
            assert respone.status_code == 200

    def assert_all_states_not_error(self):
        def _get_full_id(probe_id):
            if probe_id.startswith("log"):
                prefix = "logProbe"
            elif probe_id.startswith("metric"):
                prefix = "metricProbe"
            elif probe_id.startswith("span"):
                prefix = "spanProbe"
            elif probe_id.startswith("decor"):
                prefix = "spanDecorationProbe"
            else:
                prefix = "notSupported"

            return f"{prefix}_{probe_id}"

        assert self.rc_state is not None, "State cannot be None"

        errors = []
        for id in self.expected_probe_ids:
            full_id = _get_full_id(id)
            logger.debug(f"Checking RC state for: {full_id}")

            if full_id not in self.rc_state:

                errors.append(f"ID {full_id} not found in state")
            else:
                apply_state = self.rc_state[full_id]["apply_state"]
                logger.debug(f"RC stace for {full_id} is {apply_state}")

                if apply_state == ApplyState.ERROR:
                    errors.append(f"State for {full_id} is error: {self.rc_state[full_id]['apply_error']}")

        assert not errors, "\n".join(errors)
