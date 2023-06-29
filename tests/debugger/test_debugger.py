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

LINE_PROBES = ["logProbe-installed", "metricProbe-installed", "spanProbe-installed", "spanDecorationProbe-installed"]


def check_probe_statuses(expected_data):
    check_info_endpoint()

    agent_logs = list(interfaces.agent.get_data(path_filters="/api/v2/logs"))
    for expected_probe in expected_data:
        check_probe_status(expected_probe, agent_logs)


def check_probe_status(expected_id, agent_logs):
    expected_status = expected_id.split("-")[1].upper()

    for agent_log in agent_logs:
        actual_probe_id = agent_log["request"]["content"][0]["debugger"]["diagnostics"]["probeId"]

        if actual_probe_id == expected_id:
            actual_status = agent_log["request"]["content"][0]["debugger"]["diagnostics"]["status"]

            if actual_status == expected_status:
                return
            else:
                raise ValueError(
                    "Received probe " + expected_id + " with status " + actual_status + ", but expected for "+ expected_status
                )

    raise ValueError("Probe " + expected_id + " was not received")


def check_info_endpoint():
    """ Check that agent exposes /v0.7/config endpoint """
    for data in interfaces.library.get_data("/info"):
        for endpoint in data["response"]["content"]["endpoints"]:
            if endpoint == "/v0.7/config":
                return

    raise ValueError("Agent did not provide /v0.7/config endpoint")


@released(cpp="?", golang="?", dotnet="2.33.0", java="?", php_appsec="?", python="?", ruby="?", nodejs="?")
@scenarios.debugger_method_probes_status
class Test_Debugger_Method_Probe_Statuses:
    def test_method_probe_status(self):
        check_probe_statuses(METHOD_PROBES)


@released(cpp="?", golang="?", dotnet="2.33.0", java="?", php_appsec="?", python="?", ruby="?", nodejs="?")
@scenarios.debugger_line_probes_status
class Test_Debugger_Line_Probe_Statuses:
    def test_line_probe_status(self):
        check_probe_statuses(LINE_PROBES)
