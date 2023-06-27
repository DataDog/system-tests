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

with open("tests/debugger/expected_method_probes.json", "r", encoding="utf-8") as f:
    METHOD_PROBES = json.load(f)

with open("tests/debugger/expected_line_probes.json", "r", encoding="utf-8") as f:
    LINE_PROBES = json.load(f)


def check_probe_statuses(expected_data):
    check_info_endpoint()

    agent_logs = list(interfaces.agent.get_data(path_filters="/api/v2/logs"))
    check_logs(agent_logs, expected_data)

    request_number = 0
    for agent_log in agent_logs:
        if request_number < len(expected_data):
            check_probe_status(agent_log, expected_data[request_number])
            request_number += 1


def check_info_endpoint():
    """ Check that agent exposes /v0.7/config endpoint """
    for data in interfaces.library.get_data("/info"):
        for endpoint in data["response"]["content"]["endpoints"]:
            if endpoint == "/v0.7/config":
                return

    raise ValueError("Agent did not provide /v0.7/config endpoint")


def check_logs(logs, data):
    assert logs, "Probe statuses were not recieved"

    if len(data) > len(logs):
        raise ValueError("Received less probe statuses than expected")


def check_probe_status(log, expectedProbeId):
    actualProbeId = log["request"]["content"][0]["debugger"]["diagnostics"]["probeId"]

    if expectedProbeId != actualProbeId:
        raise ValueError("Received probe id " + actualProbeId + ", but expected for " + expectedProbeId)

    expectedStatus = expectedProbeId.split("-")[1].upper()
    actualStatus = log["request"]["content"][0]["debugger"]["diagnostics"]["status"]

    if expectedStatus != actualStatus:
        raise ValueError("Received probe status " + actualStatus + ", but expected for " + expectedStatus)


@released(dotnet="2.15.0")
@scenarios.debugger_method_probes_status
class Test_Debugger_Method_Probe_Statuses:
    def test_method_probe_status(self):
        check_probe_statuses(METHOD_PROBES)


@released(dotnet="2.15.0")
@scenarios.debugger_line_probes_status
class Test_Debugger_Line_Probe_Statuses:
    def test_line_probe_status(self):
        check_probe_statuses(LINE_PROBES)
