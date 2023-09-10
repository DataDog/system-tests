# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
import json
from collections import defaultdict

from utils import (
    ValidationError,
    scenarios,
    context,
    coverage,
    interfaces,
    missing_feature,
    released,
    rfc,
    bug,
    irrelevant,
    weblog,
)
from utils.tools import logger


def validate_data(expected_probes, expected_snapshots):
    check_info_endpoint()

    debugger_map = get_debugger_map()
    for expected_probe in expected_probes:
        check_probe_status(expected_probe, debugger_map["probes"])

    for expected_snapshot in expected_snapshots:
        check_snapshot(expected_snapshot, debugger_map["snapshots"])


def get_debugger_map():
    agent_logs_endpoint_requests = list(interfaces.agent.get_data(path_filters="/api/v2/logs"))
    hash = {"probes": {}, "snapshots": {}}

    for request in agent_logs_endpoint_requests:
        for content in request["request"]["content"]:
            debugger = content["debugger"]

            if "diagnostics" in debugger:
                probe_id = debugger["diagnostics"]["probeId"]
                hash["probes"][probe_id] = debugger["diagnostics"]

            if "snapshot" in debugger:
                probe_id = debugger["snapshot"]["probe"]["id"]
                hash["snapshots"][probe_id] = debugger["snapshot"]

    return hash


def check_probe_status(expected_id, probe_status_map):
    expected_status = expected_id.split("-")[1].upper()

    if expected_id not in probe_status_map:
        raise ValueError("Probe " + expected_id + " was not received.")

    actual_status = probe_status_map[expected_id]["status"]
    if actual_status != expected_status:
        raise ValueError(
            "Received probe " + expected_id + " with status " + actual_status + ", but expected for " + expected_status
        )


def check_snapshot(expected_id, snapshot_status_map):
    if expected_id not in snapshot_status_map:
        raise ValueError("Snapshot " + expected_id + " was not received.")


def check_info_endpoint():
    """ Check that agent exposes /v0.7/config endpoint """
    for data in interfaces.library.get_data("/info"):
        for endpoint in data["response"]["content"]["endpoints"]:
            if endpoint == "/v0.7/config":
                return

    raise ValueError("Agent did not provide /v0.7/config endpoint")


@missing_feature(
    context.library == "java" and context.weblog_variant not in ["spring-boot", "uds-spring-boot"],
    reason="not supported",
)
@irrelevant(library="golang")
@irrelevant(library="python")
@irrelevant(library="ruby")
@irrelevant(library="php")
@irrelevant(library="nodejs")
@irrelevant(library="cpp")
@scenarios.debugger_method_probes_status
class Test_Debugger_Method_Probe_Statuses:
    def test_method_probe_status(self):
        expected_data = [
            "logProbe-received",
            "logProbe-installed",
            "metricProbe-received",
            "metricProbe-installed",
            "spanProbe-received",
            "spanProbe-installed",
            "spanDecorationProbe-received",
            "spanDecorationProbe-installed",
        ]
        validate_data(expected_data, [])


@missing_feature(
    context.library == "java" and context.weblog_variant not in ["spring-boot", "uds-spring-boot"],
    reason="not supported",
)
@irrelevant(library="golang")
@irrelevant(library="python")
@irrelevant(library="ruby")
@irrelevant(library="php")
@irrelevant(library="nodejs")
@irrelevant(library="cpp")
@scenarios.debugger_line_probes_status
class Test_Debugger_Line_Probe_Statuses:
    def test_line_probe_status(self):
        expected_data = ["logProbe-installed", "metricProbe-installed", "spanDecorationProbe-installed"]
        validate_data(expected_data, [])


@missing_feature(
    context.library == "java" and context.weblog_variant not in ["spring-boot", "uds-spring-boot"],
    reason="not supported",
)
@irrelevant(library="golang")
@irrelevant(library="python")
@irrelevant(library="ruby")
@irrelevant(library="php")
@irrelevant(library="nodejs")
@irrelevant(library="cpp")
@scenarios.debugger_method_probes_snapshot
class Test_Debugger_Method_Probe_Snaphots:
    remote_config_is_sent = False
    probe_installed = False
    logProbeResponse = None

    def setup_method_probe_snaphots(self):
        def wait_for_remote_config(data):
            if data["path"] == "/v0.7/config":
                if "client_configs" in data.get("response", {}).get("content", {}):
                    self.remote_config_is_sent = True
                    return True
            return False

        def wait_for_probe(data):
            if data["path"] == "/api/v2/logs":
                contents = data.get("request", {}).get("content", {})
                for content in contents:
                    debuggerData = content["debugger"]
                    if "diagnostics" in debuggerData:
                        if debuggerData["diagnostics"]["status"] == "INSTALLED":
                            self.probe_installed = True
                            return True
            return False

        interfaces.library.wait_for(wait_for_remote_config, timeout=30)
        interfaces.agent.wait_for(wait_for_probe, timeout=30)
        self.logProbeResponse = weblog.get("/debugger/log")

    def test_method_probe_snaphots(self):
        assert self.remote_config_is_sent == True
        assert self.probe_installed == True
        assert self.logProbeResponse.status_code == 200

        expected_data = ["logProbe-installed"]
        validate_data(expected_data, expected_data)
