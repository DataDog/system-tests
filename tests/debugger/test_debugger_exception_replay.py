# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import tests.debugger.utils as base
import time, json, os
from utils import scenarios, interfaces, weblog, features


@features.debugger_exception_replay
@scenarios.debugger_exception_replay
class Test_Debugger_Exception_Replay(base._Base_Debugger_Test):
    tracer = None

    def _setup(self, request_path):
        self.weblog_responses = [weblog.get(request_path)]
        time.sleep(1)
        self.weblog_responses.append(weblog.get(request_path))

    def setup_exception_replay_simple(self):
        self._setup("/debugger/expression/exception")

    def test_exception_replay_simple(self):
        self.assert_all_weblog_responses_ok(excpected_code=500)

        self._validate_exception_replay_snapshots(test_name="exception_replay_simple")

    def _validate_exception_replay_snapshots(self, test_name: str, override_aprovals: bool = False):
        if self.tracer is None:
            tracer = base.get_tracer()

        def __get_path(suffix):
            filename = test_name + "_" + tracer["language"] + "_" + suffix + ".json"
            path = os.path.join(base._CUR_DIR, "approvals", filename)
            return path

        def __write(data, suffix):
            with open(__get_path(suffix), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

        def __read(suffix):
            with open(__get_path(suffix), "r", encoding="utf-8") as f:
                return json.load(f)

        def __approve(snapshot):
            def ___scrub(data):
                if isinstance(data, dict):
                    scrubbed_data = {}
                    for key, value in data.items():
                        if key in ["timestamp", "id", "exceptionId", "duration"]:
                            scrubbed_data[key] = "<scrubbed>"
                        else:
                            scrubbed_data[key] = ___scrub(value)
                    return scrubbed_data
                elif isinstance(data, list):
                    return [___scrub(item) for item in data]
                else:
                    return data

            snapshot = ___scrub(snapshot)
            __write(snapshot, "received")

            if override_aprovals:
                __write(snapshot, "expected")

                expected = __read("expected")
                assert expected == snapshot

        agent_logs_endpoint_requests = list(interfaces.agent.get_data(base._LOGS_PATH))
        
        snapshot_found = False
        for request in agent_logs_endpoint_requests:
            content = request["request"]["content"]
            if content:
                for item in content:
                    snapshot = item.get("debugger", {}).get("snapshot") or item.get("debugger.snapshot")
                    if snapshot:
                        snapshot_found = True
                        __approve(snapshot)

        assert snapshot_found, "Snapshot not found"
        
