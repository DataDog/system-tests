# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import scenarios, interfaces, weblog, features
from utils.tools import logger


def validate_probes(expected_probes):
    def get_probes_map():
        agent_logs_endpoint_requests = list(interfaces.agent.get_data(path_filters="/api/v2/logs"))
        probe_hash = {}

        for request in agent_logs_endpoint_requests:
            content = request["request"]["content"]
            if content is not None:
                for content in content:
                    debugger = content["debugger"]
                    if "diagnostics" in debugger:
                        probe_id = debugger["diagnostics"]["probeId"]
                        probe_hash[probe_id] = debugger["diagnostics"]

        return probe_hash

    def check_probe_status(expected_id, expected_status, probe_status_map):
        if expected_id not in probe_status_map:
            raise ValueError("Probe " + expected_id + " was not received.")

        actual_status = probe_status_map[expected_id]["status"]
        if actual_status != expected_status:
            raise ValueError(
                "Received probe "
                + expected_id
                + " with status "
                + actual_status
                + ", but expected for "
                + expected_status
            )

    probe_map = get_probes_map()
    for expected_id, expected_status in expected_probes.items():
        check_probe_status(expected_id, expected_status, probe_map)


def validate_snapshots(expected_snapshots):
    def get_snapshot_map():
        agent_logs_endpoint_requests = list(interfaces.agent.get_data(path_filters="/api/v2/logs"))
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

    def check_trace(expected_id, trace_map):
        if expected_id not in trace_map:
            raise ValueError("Trace " + expected_id + " was not received.")

    span_map = get_span_map()
    for expected_trace in expected_spans:
        check_trace(expected_trace, span_map)


@features.debugger
@scenarios.debugger_probes_status
class Test_Debugger_Probe_Statuses:
    def test_method_probe_status(self):
        expected_probes = {
            "loga0cf2-meth-45cf-9f39-591received": "RECEIVED",
            "loga0cf2-meth-45cf-9f39-59installed": "INSTALLED",
            "metricf2-meth-45cf-9f39-591received": "RECEIVED",
            "metricf2-meth-45cf-9f39-59installed": "INSTALLED",
            "span0cf2-meth-45cf-9f39-591received": "RECEIVED",
            "span0cf2-meth-45cf-9f39-59installed": "INSTALLED",
            "decorcf2-meth-45cf-9f39-591received": "RECEIVED",
            "decorcf2-meth-45cf-9f39-59installed": "INSTALLED",
        }

        validate_probes(expected_probes)

    def test_line_probe_status(self):
        expected_probes = {
            "loga0cf2-line-45cf-9f39-59installed": "INSTALLED",
            "metricf2-line-45cf-9f39-59installed": "INSTALLED",
            "decorcf2-line-45cf-9f39-59installed": "INSTALLED",
        }

        validate_probes(expected_probes)


class _Base_Debugger_Snapshot_Test:
    expected_probe_ids = []

    def assert_remote_config_is_sent(self):
        for data in interfaces.library.get_data("/v0.7/config"):
            logger.debug(f"Found config in {data['log_filename']}")
            if "client_configs" in data.get("response", {}).get("content", {}):
                return

        raise ValueError("I was expecting a remote config")

    def _is_all_probes_installed(self, data):
        contents = data.get("request", {}).get("content", [])

        if contents is None:
            return False

        installed_ids = set()
        for content in contents:
            diagnostics = content.get("debugger", {}).get("diagnostics", {})
            if diagnostics.get("status") == "INSTALLED":
                installed_ids.add(diagnostics.get("probeId"))

        logger.debug(f"Found probes in {data['log_filename']}:\n    {installed_ids}")

        if set(self.expected_probe_ids).issubset(installed_ids):
            logger.debug(f"Succes: found probes {installed_ids}")
            return True

        missings_ids = set(self.expected_probe_ids) - set(installed_ids)

        logger.debug(f"Found some probes, but not all of them. Missing probes are {missings_ids}")

    def assert_all_probes_are_installed(self):
        logger.debug(f"Checking if I found all my probes:\n    {self.expected_probe_ids}")
        for data in interfaces.agent.get_data("/api/v2/logs"):
            if self._is_all_probes_installed(data):
                return

        raise ValueError("At least one probe is missing")

    def wait_for_all_probes_installed(self, data):
        if data["path"] == "/api/v2/logs":
            if self._is_all_probes_installed(data):
                return True

        return False


@features.debugger
@scenarios.debugger_method_probes_snapshot
class Test_Debugger_Method_Probe_Snaphots(_Base_Debugger_Snapshot_Test):
    log_probe_response = None
    metric_probe_response = None
    span_probe_response = None
    span_decoration_probe_response = None

    def setup_method_probe_snaphots(self):
        self.expected_probe_ids = [
            "log170aa-acda-4453-9111-1478a6method",
            "metricaa-acda-4453-9111-1478a6method",
            "span70aa-acda-4453-9111-1478a6method",
            "decor0aa-acda-4453-9111-1478a6method",
        ]

        interfaces.library.wait_for_remote_config_request()
        interfaces.agent.wait_for(self.wait_for_all_probes_installed, timeout=30)
        self.log_probe_response = weblog.get("/debugger/log")
        self.metric_probe_response = weblog.get("/debugger/metric/1")
        self.span_probe_response = weblog.get("/debugger/span")
        self.span_decoration_probe_response = weblog.get("/debugger/span-decoration/asd/1")

    def test_method_probe_snaphots(self):
        self.assert_remote_config_is_sent()
        self.assert_all_probes_are_installed()

        assert self.log_probe_response.status_code == 200
        assert self.metric_probe_response.status_code == 200
        assert self.span_probe_response.status_code == 200
        assert self.span_decoration_probe_response.status_code == 200

        expected_probes = {
            "log170aa-acda-4453-9111-1478a6method": "EMITTING",
            "metricaa-acda-4453-9111-1478a6method": "EMITTING",
            "span70aa-acda-4453-9111-1478a6method": "EMITTING",
            "decor0aa-acda-4453-9111-1478a6method": "EMITTING",
        }
        expected_snapshots = ["log170aa-acda-4453-9111-1478a6method"]
        expected_spans = ["span70aa-acda-4453-9111-1478a6method", "decor0aa-acda-4453-9111-1478a6method"]

        validate_probes(expected_probes)
        validate_snapshots(expected_snapshots)
        validate_spans(expected_spans)


@features.debugger
@scenarios.debugger_line_probes_snapshot
class Test_Debugger_Line_Probe_Snaphots(_Base_Debugger_Snapshot_Test):
    log_probe_response = None
    metric_probe_response = None
    span_decoration_probe_response = None

    def setup_line_probe_snaphots(self):
        self.expected_probe_ids = [
            "log170aa-acda-4453-9111-1478a697line",
            "metricaa-acda-4453-9111-1478a697line",
            "decor0aa-acda-4453-9111-1478a697line",
        ]

        interfaces.library.wait_for_remote_config_request()
        interfaces.agent.wait_for(self.wait_for_all_probes_installed, timeout=30)
        self.log_probe_response = weblog.get("/debugger/log")
        self.metric_probe_response = weblog.get("/debugger/metric/1")
        self.span_decoration_probe_response = weblog.get("/debugger/span-decoration/asd/1")

    def test_line_probe_snaphots(self):
        self.assert_remote_config_is_sent()
        self.assert_all_probes_are_installed()

        assert self.log_probe_response.status_code == 200
        assert self.metric_probe_response.status_code == 200
        assert self.span_decoration_probe_response.status_code == 200

        expected_probes = {
            "log170aa-acda-4453-9111-1478a697line": "INSTALLED",
            "metricaa-acda-4453-9111-1478a697line": "INSTALLED",
            "decor0aa-acda-4453-9111-1478a697line": "INSTALLED",
        }
        expected_snapshots = ["log170aa-acda-4453-9111-1478a697line"]
        expected_spans = ["decor0aa-acda-4453-9111-1478a697line"]

        validate_probes(expected_probes)
        validate_snapshots(expected_snapshots)
        validate_spans(expected_spans)


@features.debugger
@scenarios.debugger_mix_log_probe
class Test_Debugger_Mix_Log_Probe(_Base_Debugger_Snapshot_Test):
    multi_probe_response = None

    def setup_mix_probe(self):
        self.expected_probe_ids = [
            "logfb5a-1974-4cdb-b1dd-77dba2method",
            "logfb5a-1974-4cdb-b1dd-77dba2f1line",
        ]

        interfaces.library.wait_for_remote_config_request()
        interfaces.agent.wait_for(self.wait_for_all_probes_installed, timeout=30)
        self.multi_probe_response = weblog.get("/debugger/mix/asd/1")

    def test_mix_probe(self):
        self.assert_remote_config_is_sent()
        self.assert_all_probes_are_installed()

        assert self.multi_probe_response.status_code == 200

        expected_probes = {
            "logfb5a-1974-4cdb-b1dd-77dba2method": "INSTALLED",
            "logfb5a-1974-4cdb-b1dd-77dba2f1line": "INSTALLED",
        }

        expected_snapshots = [
            "logfb5a-1974-4cdb-b1dd-77dba2method",
            "logfb5a-1974-4cdb-b1dd-77dba2f1line",
        ]

        validate_probes(expected_probes)
        validate_snapshots(expected_snapshots)
