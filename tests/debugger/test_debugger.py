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

METHOD_PROBES = [
    "logProbe-received",
    "logProbe-installed",
    "metricProbe-received",
    "metricProbe-installed",
    "spanProbe-received",
    "spanProbe-installed",
    "spanDecorationProbe-received",
    "spanDecorationProbe-installed",
]

LINE_PROBES = ["logProbe-installed", "metricProbe-installed", "spanDecorationProbe-installed"]


def check_probe_statuses(expected_data):
    check_info_endpoint()

    probe_status_map = get_probe_status_map()
    for expected_probe in expected_data:
        check_probe_status(expected_probe, probe_status_map)


def get_probe_status_map():
    agent_logs_endpoint_requests = list(interfaces.agent.get_data(path_filters="/api/v2/logs"))
    hash = {}

    for request in agent_logs_endpoint_requests:
        for content in request["request"]["content"]:
            probe_id = content["debugger"]["diagnostics"]["probeId"]
            hash[probe_id] = content["debugger"]["diagnostics"]

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


def check_info_endpoint():
    """ Check that agent exposes /v0.7/config endpoint """
    for data in interfaces.library.get_data("/info"):
        for endpoint in data["response"]["content"]["endpoints"]:
            if endpoint == "/v0.7/config":
                return

    raise ValueError("Agent did not provide /v0.7/config endpoint")


@released(java="1.19.3", php_appsec="?", python="?")
@missing_feature(
    context.library == "java" and context.weblog_variant not in ["spring-boot", "uds-spring-boot"],
    reason="not supported",
)
@scenarios.debugger_method_probes_status
class Test_Debugger_Method_Probe_Statuses:
    def test_method_probe_status(self):
        check_probe_statuses(METHOD_PROBES)


@released(java="1.19.3", php_appsec="?", python="?")
@missing_feature(
    context.library == "java" and context.weblog_variant not in ["spring-boot", "uds-spring-boot"],
    reason="not supported",
)
@scenarios.debugger_line_probes_status
class Test_Debugger_Line_Probe_Statuses:
    def test_line_probe_status(self):
        check_probe_statuses(LINE_PROBES)
