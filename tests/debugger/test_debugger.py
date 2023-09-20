# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import (
    scenarios,
    context,
    interfaces,
    missing_feature,
    irrelevant,
    weblog,
)


def validate_data(expected_probes, expected_snapshots, expected_traces):
    check_info_endpoint()

    log_map = get_debugger_log_map()
    for expected_probe in expected_probes:
        check_probe_status(expected_probe, log_map["probes"])

    for expected_snapshot in expected_snapshots:
        check_snapshot(expected_snapshot, log_map["snapshots"])

    trace_map = get_debugger_tracer_map()
    for expected_trace in expected_traces:
        check_trace(expected_trace, trace_map)


def get_debugger_log_map():
    agent_logs_endpoint_requests = list(interfaces.agent.get_data(path_filters="/api/v2/logs"))
    log_hash = {"probes": {}, "snapshots": {}}

    for request in agent_logs_endpoint_requests:
        content = request["request"]["content"]
        if content is not None:
            for content in content:
                debugger = content["debugger"]

                if "diagnostics" in debugger:
                    probe_id = debugger["diagnostics"]["probeId"]
                    log_hash["probes"][probe_id] = debugger["diagnostics"]
                elif "snapshot" in debugger:
                    probe_id = debugger["snapshot"]["probe"]["id"]
                    log_hash["snapshots"][probe_id] = debugger["snapshot"]

    return log_hash


def get_debugger_tracer_map():
    agent_logs_endpoint_requests = list(interfaces.agent.get_data(path_filters="/api/v0.2/traces"))
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


def check_trace(expected_id, trace_map):
    if expected_id not in trace_map:
        raise ValueError("Trace " + expected_id + " was not received.")


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
@missing_feature(context.library == "python", reason="not implemented yet")
@irrelevant(library="golang")
@irrelevant(library="nodejs")
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
        validate_data(expected_data, [], [])


@missing_feature(
    context.library == "java" and context.weblog_variant not in ["spring-boot", "uds-spring-boot"],
    reason="not supported",
)
@missing_feature(context.library == "python", reason="not implemented yet")
@irrelevant(library="golang")
@irrelevant(library="nodejs")
@scenarios.debugger_line_probes_status
class Test_Debugger_Line_Probe_Statuses:
    def test_line_probe_status(self):
        expected_data = ["logProbe-installed", "metricProbe-installed", "spanDecorationProbe-installed"]
        validate_data(expected_data, [], [])


class _Base_Debugger_Snapshot_Test:
    remote_config_is_sent = False
    probe_installed = False

    def wait_for_remote_config(self, data):
        if data["path"] == "/v0.7/config":
            if "client_configs" in data.get("response", {}).get("content", {}):
                self.remote_config_is_sent = True
                return True
        return False

    def wait_for_probe(self, data):
        if data["path"] == "/api/v2/logs":
            contents = data.get("request", {}).get("content", {})

            if contents is None:
                return False

            for content in contents:
                debuggerData = content["debugger"]
                if "diagnostics" in debuggerData:
                    if debuggerData["diagnostics"]["status"] == "INSTALLED":
                        self.probe_installed = True
                        return True
        return False


@missing_feature(
    context.library == "java" and context.weblog_variant not in ["spring-boot", "uds-spring-boot"],
    reason="not supported",
)
@missing_feature(context.library == "python", reason="not implemented yet")
@irrelevant(library="golang")
@irrelevant(library="nodejs")
@scenarios.debugger_method_probes_snapshot
class Test_Debugger_Method_Probe_Snaphots(_Base_Debugger_Snapshot_Test):
    log_probe_response = None
    metric_probe_response = None
    span_probe_response = None
    span_decoration_probe_response = None

    def setup_method_probe_snaphots(self):
        interfaces.library.wait_for(self.wait_for_remote_config, timeout=30)
        interfaces.agent.wait_for(self.wait_for_probe, timeout=30)
        self.log_probe_response = weblog.get("/debugger/log")
        self.metric_probe_response = weblog.get("/debugger/metric/1")
        self.span_probe_response = weblog.get("/debugger/span")
        self.span_decoration_probe_response = weblog.get("/debugger/span-decoration/asd/1")

    def test_method_probe_snaphots(self):
        assert self.remote_config_is_sent is True
        assert self.probe_installed is True

        assert self.log_probe_response.status_code == 200
        assert self.metric_probe_response.status_code == 200
        assert self.span_probe_response.status_code == 200
        assert self.span_decoration_probe_response.status_code == 200

        expected_probes = [
            "logProbe-installed",
            "metricProbe-installed",
            "spanProbe-installed",
            "spanDecorationProbe-installed",
        ]
        expected_snapshots = ["logProbe-installed"]
        expected_traces = ["spanProbe-installed", "spanDecorationProbe-installed"]

        validate_data(expected_probes, expected_snapshots, expected_traces)


@missing_feature(
    context.library == "java" and context.weblog_variant not in ["spring-boot", "uds-spring-boot"],
    reason="not supported",
)
@missing_feature(context.library == "python", reason="not implemented yet")
@irrelevant(library="golang")
@irrelevant(library="nodejs")
@scenarios.debugger_line_probes_snapshot
class Test_Debugger_Line_Probe_Snaphots(_Base_Debugger_Snapshot_Test):
    log_probe_response = None
    metric_probe_response = None
    span_decoration_probe_response = None

    def setup_line_probe_snaphots(self):
        interfaces.library.wait_for(self.wait_for_remote_config, timeout=30)
        interfaces.agent.wait_for(self.wait_for_probe, timeout=30)
        self.log_probe_response = weblog.get("/debugger/log")
        self.metric_probe_response = weblog.get("/debugger/metric/1")
        self.span_decoration_probe_response = weblog.get("/debugger/span-decoration/asd/1")

    def test_line_probe_snaphots(self):
        assert self.remote_config_is_sent is True
        assert self.probe_installed is True

        assert self.log_probe_response.status_code == 200
        assert self.metric_probe_response.status_code == 200
        assert self.span_decoration_probe_response.status_code == 200

        expected_probes = [
            "logProbe-installed",
            "metricProbe-installed",
            "spanDecorationProbe-installed",
        ]
        expected_snapshots = ["logProbe-installed"]
        expected_traces = ["spanDecorationProbe-installed"]

        validate_data(expected_probes, expected_snapshots, expected_traces)
