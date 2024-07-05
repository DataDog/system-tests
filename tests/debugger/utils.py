# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import json
import re
import os
import os.path
import uuid

from packaging import version

from utils import interfaces
from utils.tools import logger
from utils.dd_constants import RemoteConfigApplyState as ApplyState

_CONFIG_PATH = "/v0.7/config"
_DEBUGGER_PATH = "/api/v2/debugger"
_LOGS_PATH = "/api/v2/logs"
_TRACES_PATH = "/api/v0.2/traces"

_CUR_DIR = os.path.dirname(os.path.abspath(__file__))


def get_tracer():
    config = list(interfaces.library.get_data(_CONFIG_PATH))

    if config:
        return config[0]["request"]["content"]["client"]["client_tracer"]
    else:
        logger.error("Config was not found")
        return {"language": "not_defined", "tracer_version": "v0.0.0"}


def read_probes(test_name: str):
    with open(os.path.join(_CUR_DIR, "probes/", test_name + ".json"), "r", encoding="utf-8") as f:
        return json.load(f)


def generate_probe_id(probe_type: str):
    return probe_type + str(uuid.uuid4())[len(probe_type) :]


def extract_probe_ids(probes):
    return [probe["id"] for probe in probes]


def read_diagnostic_data():
    tracer = get_tracer()

    tracer_version = version.parse(re.sub(r"[^0-9.].*$", "", tracer["tracer_version"]))
    if tracer["language"] == "java":
        if tracer_version > version.parse("1.27.0"):
            path = _DEBUGGER_PATH
        else:
            path = _LOGS_PATH
    elif tracer["language"] == "dotnet":
        if tracer_version > version.parse("2.49.0"):
            path = _DEBUGGER_PATH
        else:
            path = _LOGS_PATH
    elif tracer["language"] == "python":
        path = _DEBUGER_PATH
    else:
        path = _DEBUGGER_PATH

    return list(interfaces.agent.get_data(path))


def get_probes_map(data_set):
    probe_hash = {}

    def _process_debugger(debugger):
        if "diagnostics" in debugger:
            diagnostics = debugger["diagnostics"]

            probe_id = diagnostics["probeId"]
            status = diagnostics["status"]

            if probe_id in probe_hash:
                current_status = probe_hash[probe_id]["status"]
                if current_status == "RECEIVED":
                    probe_hash[probe_id]["status"] = status
                elif current_status == "INSTALLED" and status in ["INSTALLED", "EMITTING"]:
                    probe_hash[probe_id]["status"] = status
                elif current_status == "EMITTING" and status == "EMITTING":
                    probe_hash[probe_id]["status"] = status
            else:
                probe_hash[probe_id] = diagnostics

    for data in data_set:
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

    return probe_hash


class _Base_Debugger_Test:
    weblog_responses = []
    expected_probe_ids = []
    rc_state = None
    installed_ids = set()
    all_probes_installed = False

    def wait_for_all_probes_installed(self, data):
        def _all_probes_installed(self, probes_map):
            if not probes_map:
                logger.debug("Probes map is empty")
                return False

            logger.debug(f"Look for these probes: {self.expected_probe_ids}")
            for expected_id in self.expected_probe_ids:
                if expected_id in probes_map:
                    status = probes_map[expected_id]["status"]

                    logger.debug(f"Probe {expected_id} observed status is {status}")
                    if status == "INSTALLED":
                        self.installed_ids.add(expected_id)

            if set(self.expected_probe_ids).issubset(self.installed_ids):
                logger.debug(f"Succes: found all probes")
                return True

            return False

        if not self.all_probes_installed:
            if data["path"] == _DEBUGGER_PATH or data["path"] == _LOGS_PATH:
                self.all_probes_installed = _all_probes_installed(self, get_probes_map([data]))

        return self.all_probes_installed

    def assert_all_probes_are_installed(self):
        if not self.all_probes_installed:
            missing_probes = set(self.expected_probe_ids) - set(self.installed_ids)
            assert not missing_probes, f"Not all probes are installed. Missing ids: {', '.join(missing_probes)}"

    def assert_all_weblog_responses_ok(self, expected_code=200):
        assert len(self.weblog_responses) > 0, "No responses available."

        for respone in self.weblog_responses:
            logger.debug(f"Response is {respone.text}")
            assert respone.status_code == expected_code

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
