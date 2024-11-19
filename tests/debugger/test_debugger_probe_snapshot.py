# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import tests.debugger.utils as base

from utils import scenarios, interfaces, weblog, features, remote_config as rc, bug


@features.debugger
@scenarios.debugger_method_probes_snapshot
class Test_Debugger_Method_Probe_Snapshots(base._Base_Debugger_Test):
    def setup_method_probe_snapshots(self):
        probes = base.read_probes("probe_snapshot_method")
        self.expected_probe_ids = base.extract_probe_ids(probes)
        self.rc_state = rc.send_debugger_command(probes, version=1)

        interfaces.agent.wait_for(self.wait_for_all_probes_installed, timeout=30)
        self.weblog_responses = [
            weblog.get("/debugger/log"),
            weblog.get("/debugger/span"),
            weblog.get("/debugger/span-decoration/asd/1"),
        ]

    @bug(library="python", reason="DEBUG-2708, DEBUG-2709")
    def test_method_probe_snapshots(self):
        self.assert_all_states_not_error()
        self.assert_all_probes_are_installed()
        self.assert_all_weblog_responses_ok()

        expected_snapshots = ["log170aa-acda-4453-9111-1478a6method"]
        expected_spans = ["span70aa-acda-4453-9111-1478a6method", "decor0aa-acda-4453-9111-1478a6method"]

        _validate_snapshots(expected_snapshots)
        _validate_spans(expected_spans)


@features.debugger
@scenarios.debugger_line_probes_snapshot
class Test_Debugger_Line_Probe_Snaphots(base._Base_Debugger_Test):
    def setup_line_probe_snaphots(self):
        probes = base.read_probes("probe_snapshot_line")
        self.expected_probe_ids = base.extract_probe_ids(probes)
        self.rc_state = rc.send_debugger_command(probes, version=1)

        interfaces.agent.wait_for(self.wait_for_all_probes_installed, timeout=30)

        self.weblog_responses = [
            weblog.get("/debugger/log"),
            weblog.get("/debugger/span-decoration/asd/1"),
        ]

    def test_line_probe_snaphots(self):
        self.assert_all_states_not_error()
        self.assert_all_probes_are_installed()
        self.assert_all_weblog_responses_ok()

        expected_snapshots = ["log170aa-acda-4453-9111-1478a697line"]
        expected_spans = ["decor0aa-acda-4453-9111-1478a697line"]

        _validate_snapshots(expected_snapshots)
        _validate_spans(expected_spans)


@features.debugger
@scenarios.debugger_mix_log_probe
class Test_Debugger_Mix_Log_Probe(base._Base_Debugger_Test):
    def setup_mix_probe(self):
        probes = base.read_probes("probe_snapshot_mix_log")
        self.expected_probe_ids = base.extract_probe_ids(probes)
        self.rc_state = rc.send_debugger_command(probes, version=1)

        interfaces.agent.wait_for(self.wait_for_all_probes_installed, timeout=30)
        self.weblog_responses = [weblog.get("/debugger/mix/asd/1")]

    @bug(library="python", reason="DEBUG-2710")
    def test_mix_probe(self):
        self.assert_all_states_not_error()
        self.assert_all_probes_are_installed()
        self.assert_all_weblog_responses_ok()

        expected_snapshots = [
            "logfb5a-1974-4cdb-b1dd-77dba2method",
            "logfb5a-1974-4cdb-b1dd-77dba2f1line",
        ]

        _validate_snapshots(expected_snapshots)


def _validate_snapshots(expected_snapshots):
    def __get_snapshot_map():
        agent_logs_endpoint_requests = list(interfaces.agent.get_data(base._LOGS_PATH))
        snapshot_hash = {}

        for request in agent_logs_endpoint_requests:
            content = request["request"]["content"]
            if content:
                for item in content:
                    snapshot = item.get("debugger", {}).get("snapshot") or item.get("debugger.snapshot")
                    if snapshot:

                        probe_id = snapshot["probe"]["id"]
                        snapshot_hash[probe_id] = snapshot

        return snapshot_hash

    def check_snapshot(expected_id, snapshot_status_map):
        if expected_id not in snapshot_status_map:
            raise ValueError("Snapshot " + expected_id + " was not received.")

    snapshot_map = __get_snapshot_map()
    for expected_snapshot in expected_snapshots:
        check_snapshot(expected_snapshot, snapshot_map)


def _validate_spans(expected_spans):
    def __get_span_map():
        agent_logs_endpoint_requests = list(interfaces.agent.get_data(base._TRACES_PATH))
        span_hash = {}
        for request in agent_logs_endpoint_requests:
            content = request["request"]["content"]
            if content:
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

    span_map = __get_span_map()
    for expected_trace in expected_spans:
        check_trace(expected_trace, span_map)
