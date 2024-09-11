# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import tests.debugger.utils as base
import json
import os
import re
from utils import scenarios, interfaces, weblog, features, bug
from utils.tools import logger

_OVERRIDE_APROVALS = False


@features.debugger_exception_replay
@scenarios.debugger_exception_replay
class Test_Debugger_Exception_Replay(base._Base_Debugger_Test):
    tracer = None
    snapshots = None
    method = None

    def _setup(self, request_path, method):
        self.snapshots = []
        self.weblog_responses = []
        self.method = method

        retries = 0
        max_retries = 60

        while not self.snapshots and retries < max_retries:
            logger.debug(f"Waiting for snapshot, retry #{retries}")

            self.weblog_responses.append(weblog.get(request_path))
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

                logger.debug(f"method is {method}; self method is {self.method}")
                if method == self.method:
                    self.snapshots.append(snapshot)
                    logger.debug("Snapshot found")

        return bool(self.snapshots)

    ############ Simple ############
    def setup_exception_replay_simple(self):
        self._setup("/debugger/exceptionreplay/simple", "exceptionreplaysimple")

    @bug(library="java", reason="DEBUG-2787")
    @bug(library="dotnet", reason="DEBUG-2799")
    def test_exception_replay_simple(self):
        self.assert_all_weblog_responses_ok(expected_code=500)
        self._validate_exception_replay_snapshots(test_name="exception_replay_simple")
        self._validate_tags(test_name="exception_replay_simple", number_of_frames=1)

    def setup_exception_replay_simple(self):
        self._setup("/debugger/exceptionreplay/simple", "exceptionreplaysimple")

    ############ Recursion ############
    def setup_exception_replay_recursion_5(self):
        self._setup("/debugger/exceptionreplay/recursion5", "exceptionreplayrecursion5")

    @bug(library="java", reason="DEBUG-2787")
    @bug(library="dotnet", reason="DEBUG-2799")
    def test_exception_replay_recursion_5(self):
        self.assert_all_weblog_responses_ok(expected_code=500)
        self._validate_exception_replay_snapshots(test_name="exception_replay_recursion_5")
        self._validate_tags(test_name="exception_replay_recursion_5", number_of_frames=5)

    def setup_exception_replay_recursion_20(self):
        self._setup("/debugger/exceptionreplay/recursion20", "exceptionreplayrecursion20")

    @bug(library="java", reason="DEBUG-2787")
    @bug(library="dotnet", reason="DEBUG-2799")
    def test_exception_replay_recursion_20(self):
        self.assert_all_weblog_responses_ok(expected_code=500)
        self._validate_exception_replay_snapshots(test_name="exception_replay_recursion_20")
        self._validate_tags(test_name="exception_replay_recursion_20", number_of_frames=20)

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

    def _validate_exception_replay_snapshots(self, test_name: str):
        def __approve(snapshots):
            def ___scrub(data):
                if isinstance(data, dict):
                    scrubbed_data = {}
                    for key, value in data.items():
                        if key in ["timestamp", "id", "exceptionId", "duration"]:
                            scrubbed_data[key] = "<scrubbed>"
                        # java
                        elif key == "elements" and data.get("type") in ["long[]", "short[]"]:
                            scrubbed_data[key] = "<scrubbed>"
                        # dotnet
                        elif key == "function" and "lambda_" in value:
                            scrubbed_data[key] = re.sub(r"(method)\d+", r"\1<scrubbed>", value)
                        # dotnet
                        elif key == "StackTrace" and isinstance(value, dict):
                            value["value"] = "<scrubbed>"
                            scrubbed_data[key] = value
                        else:
                            scrubbed_data[key] = ___scrub(value)
                    return scrubbed_data
                elif isinstance(data, list):
                    return [___scrub(item) for item in data]
                else:
                    return data

            assert self.snapshots, "Snapshots not found"

            snapshots = [___scrub(snapshot) for snapshot in snapshots]
            self.__write(snapshots, test_name, "snapshots_received")

            if _OVERRIDE_APROVALS:
                self.__write(snapshots, test_name, "snapshots_expected")

            expected_snapshots = self.__read(test_name, "snapshots_expected")
            assert expected_snapshots == snapshots
            assert all(
                "exceptionId" in snapshot for snapshot in snapshots
            ), "One or more snapshots don't have 'exceptionId' field"

        __approve(self.snapshots)

    def _validate_tags(self, test_name: str, number_of_frames: int):
        def __get_tags():
            debugger_tags = {}
            snapshot_ids = [snapshot["id"] for snapshot in self.snapshots]

            traces = list(interfaces.agent.get_data(base._TRACES_PATH))
            for trace in traces:
                logger.debug("Looking for tags in %s", trace["log_filename"])

                content = trace["request"]["content"]
                if content:
                    for payload in content["tracerPayloads"]:
                        for payload in content["tracerPayloads"]:
                            for chunk in payload["chunks"]:
                                for span in chunk["spans"]:
                                    meta = span.get("meta", {})
                                    if any(
                                        meta.get(f"_dd.debug.error.{i}.snapshot_id") in snapshot_ids
                                        for i in range(len(snapshot_ids))
                                    ):
                                        logger.debug(f"Tags were found in %s", trace["log_filename"])

                                        for key, value in meta.items():
                                            if key.startswith("_dd.debug.error"):
                                                if key.endswith("id"):
                                                    debugger_tags[key] = "<scrubbed>"
                                                else:
                                                    debugger_tags[key] = value

                                        return debugger_tags

            logger.debug(f"Tags were not found")
            return debugger_tags

        def __approve(tags):
            tags = dict(sorted(tags.items()))
            self.__write(tags, test_name, "tags_received")

            if _OVERRIDE_APROVALS:
                self.__write(tags, test_name, "tags_expected")

            expected = self.__read(test_name, "tags_expected")

            assert expected == tags

            assert "_dd.debug.error.exception_id" in tags, "Missing '_dd.debug.error.exception_id' in tags"
            assert "_dd.debug.error.exception_hash" in tags, "Missing '_dd.debug.error.exception_hash' in tags"
            assert f"_dd.debug.error.{0}.snapshot_id" in tags, f"Missing '_dd.debug.error.{0}.snapshot_id' in tags"
            if number_of_frames > 1:
                assert (
                    f"_dd.debug.error.{number_of_frames}.snapshot_id" in tags
                ), f"Missing '_dd.debug.error.{number_of_frames}.snapshot_id' in tags"

        __approve(__get_tags())
