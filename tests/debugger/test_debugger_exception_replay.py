# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import tests.debugger.utils as base
import json, os
from utils import scenarios, interfaces, weblog, features
from utils.tools import logger


@features.debugger_exception_replay
@scenarios.debugger_exception_replay
class Test_Debugger_Exception_Replay(base._Base_Debugger_Test):
    tracer = None
    snapshot = None
    method = None

    def _setup(self, request_path, method):
        self.snapshot = None
        self.weblog_responses = set()
        self.method = method

        retries = 0
        max_retries = 60

        while not self.snapshot and retries < max_retries:
            logger.debug(f"Waiting for snapshot, retry #{retries}")

            self.weblog_responses.add(weblog.get(request_path))
            interfaces.agent.wait_for(self._wait_for_snapshot_received, timeout=1)

            retries += 1

    def _wait_for_snapshot_received(self, data):
        if data["path"] == base._LOGS_PATH:

            contents = data["request"].get("content", []) or []
            if contents:
                for content in contents:
                    snapshot = content.get("debugger", {}).get("snapshot") or content.get("debugger.snapshot")
                    if snapshot and snapshot["probe"]["location"]["method"].lower().replace("_", "") == self.method:
                        self.snapshot = snapshot

                        logger.debug("Snapshot received")
                        return True

        return False

    def setup_exception_replay_simple(self):
        self._setup("/debugger/expression/exception", "expressionexception")

    def test_exception_replay_simple(self):
        self.assert_all_weblog_responses_ok(expected_code=500)
        assert self.snapshot, "Snapshot not found"
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

        __approve(self.snapshot)
