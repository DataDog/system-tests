# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import tests.debugger.utils as base
import json, os
from utils import scenarios, interfaces, weblog, features, bug
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
            for content in contents:
                snapshot = content.get("debugger", {}).get("snapshot") or content.get("debugger.snapshot")

                if not snapshot:
                    continue

                if (
                    "probe" not in snapshot
                    or "location" not in snapshot["probe"]
                    or "method" not in snapshot["probe"]["location"]
                ):
                    continue

                method = snapshot["probe"]["location"]["method"]

                if not isinstance(method, str):
                    continue

                method = method.lower().replace("_", "")

                if method == self.method:
                    self.snapshot = snapshot

                    logger.debug("Snapshot received")
                    return True

        return False

    def setup_exception_replay_simple(self):
        self._setup("/debugger/expression/exception", "expressionexception")

    @bug(library="dotnet", reason="DEBUG-2787")
    def test_exception_replay_simple(self):
        self.assert_all_weblog_responses_ok(expected_code=500)
        assert self.snapshot, "Snapshot not found"
        self._validate_exception_replay_snapshots(test_name="exception_replay_simple")
        self._validate_tags(test_name="exception_replay_simple", number_of_frames=1)

    def __get_path(self, test_name, suffix):
        if self.tracer is None:
            self.tracer = base.get_tracer()
        filename = test_name + "_" + self.tracer["language"] + "_" + suffix + ".json"
        path = os.path.join(base._CUR_DIR, "approvals", filename)
        return path

    def __write(self, data, test_name, suffix):
        with open(self.__get_path(test_name, suffix), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def __read(self, test_name, suffix):
        with open(self.__get_path(test_name, suffix), "r", encoding="utf-8") as f:
            return json.load(f)

    def _validate_exception_replay_snapshots(self, test_name: str, override_aprovals: bool = False):
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
            self.__write(snapshot, test_name, "received")

            if override_aprovals:
                self.__write(snapshot, test_name, "expected")

                expected = self.__read(test_name, "expected")
                assert expected == snapshot

        __approve(self.snapshot)

    def _validate_tags(self, test_name: str, number_of_frames: int, override_aprovals: bool = False):
        def __get_tags():
            debugger_tags = {}

            traces = list(interfaces.agent.get_data(base._TRACES_PATH))
            for trace in traces:
                content = trace["request"]["content"]
                if content:
                    for payload in content["tracerPayloads"]:
                        for payload in content["tracerPayloads"]:
                            for chunk in payload["chunks"]:
                                for span in chunk["spans"]:
                                    meta = span.get("meta", {})
                                    if meta.get("_dd.debug.error.0.snapshot_id") == self.snapshot["id"]:
                                        for key, value in meta.items():
                                            if key.startswith("_dd.debug.error"):
                                                if key.endswith("id"):
                                                    debugger_tags[key] = "<scrubbed>"
                                                else:
                                                    debugger_tags[key] = value

                                        return debugger_tags

            return debugger_tags

        def __approve(tags):
            self.__write(tags, test_name, "tags_received")

            if override_aprovals:
                self.__write(tags, test_name, "tags_expected")

            expected = self.__read(test_name, "tags_expected")
            assert expected == tags

            # Check for the existence of specific keys
            assert "_dd.debug.error.exception_id" in tags, "Missing '_dd.debug.error.exception_id' in tags"
            assert "_dd.debug.error.exception_hash" in tags, "Missing '_dd.debug.error.exception_hash' in tags"
            for i in range(number_of_frames):
                assert f"_dd.debug.error.{i}.snapshot_id" in tags, f"Missing '_dd.debug.error.{i}.snapshot_id' in tags"

        __approve(__get_tags())
