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
    last_read = 0

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
        snapshot_found = False

        if data["path"] == base._LOGS_PATH:

            log_number = int(re.search(r"/(\d+)__", data["log_filename"]).group(1))
            logger.debug("Reading " + data["log_filename"] + ", looking for " + self.method)
            logger.debug(f"Last read is {Test_Debugger_Exception_Replay.last_read}")

            if log_number > Test_Debugger_Exception_Replay.last_read:
                Test_Debugger_Exception_Replay.last_read = log_number

                logger.debug("Reading " + data["log_filename"] + ", looking for " + self.method)
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
                        snapshot_found = True

        logger.debug(f"Snapshot found: {snapshot_found}")
        return snapshot_found

    ############ Simple ############
    def setup_exception_replay_simple(self):
        self._setup("/debugger/exceptionreplay/simple", "exceptionreplaysimple")

    @bug(library="java", reason="DEBUG-3053")
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

    @bug(library="java", reason="DEBUG-3053")
    @bug(library="dotnet", reason="DEBUG-2799")
    def test_exception_replay_recursion_5(self):
        self.assert_all_weblog_responses_ok(expected_code=500)
        self._validate_exception_replay_snapshots(test_name="exception_replay_recursion_5")
        self._validate_tags(test_name="exception_replay_recursion_5", number_of_frames=5)

    def setup_exception_replay_recursion_20(self):
        self._setup("/debugger/exceptionreplay/recursion20", "exceptionreplayrecursion20")

    @bug(library="java", reason="DEBUG-3053")
    @bug(library="dotnet", reason="DEBUG-2799")
    def test_exception_replay_recursion_20(self):
        self.assert_all_weblog_responses_ok(expected_code=500)
        self._validate_exception_replay_snapshots(test_name="exception_replay_recursion_20")
        self._validate_tags(test_name="exception_replay_recursion_20", number_of_frames=20)

    ############ Inner ############
    def setup_exception_replay_inner(self):
        self._setup("/debugger/exceptionreplay/inner", "exceptionreplayinner")

    @bug(library="java", reason="DEBUG-3053")
    @bug(library="dotnet", reason="DEBUG-2799")
    def test_exception_replay_inner(self):
        self.assert_all_weblog_responses_ok(expected_code=500)
        self._validate_exception_replay_snapshots(test_name="exception_replay_inner")
        self._validate_tags(test_name="exception_replay_inner", number_of_frames=2)

    ############ Rock Paper Scissors ############
    def setup_exception_replay_rockpaperscissors(self):
        self.snapshots = []
        self.weblog_responses = []
        self.method = "exceptionreplayrockpaperscissors"

        retries = 0
        max_retries = 60
        shapes = ["rock", "paper", "scissors"]

        while len(self.snapshots) < len(shapes) and retries < max_retries:
            for shape in shapes:
                logger.debug(f"Waiting for snapshot for shape: {shape}, retry #{retries}")

                self.weblog_responses.append(weblog.get(f"/debugger/exceptionreplay/rps?shape={shape}"))
                interfaces.agent.wait_for(self._wait_for_snapshot_received, timeout=1)

            retries += 1

    @bug(library="java", reason="DEBUG-3053")
    @bug(library="dotnet", reason="DEBUG-2799")
    def test_exception_replay_rockpaperscissors(self):
        self.assert_all_weblog_responses_ok(expected_code=500)
        self._validate_exception_replay_snapshots(test_name="exception_replay_rockpaperscissors")
        self._validate_tags(test_name="exception_replay_rockpaperscissors", number_of_frames=2)

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
                        elif key == "elements" and data.get("type") in ["long[]", "short[]", "int[]"]:
                            scrubbed_data[key] = "<scrubbed>"
                        elif key == "moduleVersion":
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
            snapshot_tags = {}
            debugger_tags = {}
            tag_number = 0
            snapshot_ids = [snapshot["id"] for snapshot in self.snapshots]
            logger.debug("Snapshot ids are %s", snapshot_ids)

            traces = list(interfaces.agent.get_data(base._TRACES_PATH))
            for trace in traces:
                logger.debug("Looking for tags in %s", trace["log_filename"])

                content = trace["request"]["content"]
                if content:
                    for payload in content["tracerPayloads"]:
                        for chunk in payload["chunks"]:
                            for span in chunk["spans"]:
                                meta = span.get("meta", {})

                                for snapshot_id in snapshot_ids:
                                    if any(
                                        meta.get(key) == snapshot_id
                                        for key in meta.keys()
                                        if re.search(r"_dd\.debug\.error\.\d+\.snapshot_id", key)
                                    ):
                                        logger.debug("Found tags in %s", trace["log_filename"])

                                        for key, value in meta.items():
                                            if key.startswith("_dd.debug.error"):
                                                if key.endswith("id"):
                                                    debugger_tags[key] = "<scrubbed>"
                                                else:
                                                    debugger_tags[key] = value

                                        snapshot_tags[f"snapshot_{tag_number}"] = dict(sorted(debugger_tags.items()))
                                        tag_number += 1

            return snapshot_tags

        def __approve(tags):
            self.__write(tags, test_name, "tags_received")

            if _OVERRIDE_APROVALS:
                self.__write(tags, test_name, "tags_expected")

            expected = self.__read(test_name, "tags_expected")
            assert expected == tags

            missing_keys_dict = {}
            snapshot_id_pattern = re.compile(r"_dd\.debug\.error\.\d+\.snapshot_id")

            for guid, element in tags.items():
                missing_keys = []

                if "_dd.debug.error.exception_id" not in element:
                    missing_keys.append("_dd.debug.error.exception_id")

                if "_dd.debug.error.exception_hash" not in element:
                    missing_keys.append("_dd.debug.error.exception_hash")

                if not any(snapshot_id_pattern.match(key) for key in element):
                    missing_keys.append("_dd.debug.error.{n}.snapshot_id")

                if missing_keys:
                    missing_keys_dict[guid] = missing_keys

            assert not missing_keys_dict, f"Missing keys detected: {missing_keys_dict}"

        tags = __get_tags()
        __approve(tags)
