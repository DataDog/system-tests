# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import tests.debugger.utils as debugger
import re
from utils import scenarios, features, bug
from utils.tools import logger

_OVERRIDE_APROVALS = True
_SCRUB_VALUES = True


@features.debugger_exception_replay
@scenarios.debugger_exception_replay
class Test_Debugger_Exception_Replay(debugger._Base_Debugger_Test):
    ############ setup ############
    def _setup(self, request_path, method_name):
        self.weblog_responses = []

        retries = 0
        max_retries = 60
        snapshot_found = False

        while not snapshot_found and retries < max_retries:
            logger.debug(f"Waiting for snapshot, retry #{retries}")

            self.send_weblog_request(request_path, reset=False)
            snapshot_found = self.wait_for_snapshot_received(method_name)

            retries += 1

    ############ assert ############
    def _assert(self, test_name, method_name):
        def __filter_snapshots_by_method():
            filtered_snapshots = []

            for contents in self.probe_snapshots.values():
                for content in contents:
                    if content["debugger"]["snapshot"]["probe"]["location"]["method"].lower() == method_name:
                        filtered_snapshots.append(content["debugger"]["snapshot"])

            return filtered_snapshots

        def __filter_spans_by_snapshot_id(snapshots):
            filtered_spans = {}

            for span in self.probe_spans.values():
                snapshot_ids_in_span = {
                    key: value for key, value in span["meta"].items() if key.endswith("snapshot_id")
                }.values()
                for snapshot in snapshots:
                    if snapshot["id"] in snapshot_ids_in_span:
                        filtered_spans[snapshot["id"]] = span

            return filtered_spans

        self.collect()
        self.assert_all_weblog_responses_ok(expected_code=500)

        snapshots = __filter_snapshots_by_method()
        self._validate_exception_replay_snapshots(test_name, snapshots)

        spans = __filter_spans_by_snapshot_id(snapshots)
        self._validate_spans(test_name, spans)

    def _validate_exception_replay_snapshots(self, test_name, snapshots):
        def __scrub(data):
            if isinstance(data, dict):
                scrubbed_data = {}
                for key, value in data.items():
                    if key in ["timestamp", "id", "exceptionId", "duration"]:
                        scrubbed_data[key] = "<scrubbed>"
                    else:
                        scrubbed_data[key] = scrub_language(key, value, data)

                return scrubbed_data
            elif isinstance(data, list):
                return [__scrub(item) for item in data]
            else:
                return data

        def __scrub_java(key, value, parent):
            runtime = ("jdk.", "org.", "java")

            def skip_runtime(value, skip_condition, del_filename=None):
                scrubbed = []

                for entry in value:
                    # skip inner runtime methods from stack traces since they are not relevant to debugger
                    if skip_condition(entry):
                        continue

                    # filenames in stacktraces are unreliable due to potential data races during retransformation.
                    if del_filename and del_filename(entry):
                        del entry["fileName"]

                    scrubbed.append(__scrub(entry))

                scrubbed.append({"<runtime>": "<scrubbed>"})

                return scrubbed

            if key == "elements":
                if parent.get("type") in ["long[]", "short[]", "int[]"]:
                    return "<scrubbed>"

                if parent["type"] == "java.lang.Object[]":
                    return skip_runtime(value, lambda e: "value" in e and e["value"].startswith(runtime))

                if parent["type"] == "java.lang.StackTraceElement[]":
                    return skip_runtime(value, lambda e: e["fields"]["declaringClass"]["value"].startswith(runtime))

                return __scrub(value)

            elif key == "moduleVersion":
                return "<scrubbed>"
            elif key in ["stacktrace", "stack"]:
                return skip_runtime(
                    value, lambda e: "function" in e and e["function"].startswith(runtime), lambda e: "fileName" in e
                )

            return __scrub(value)

        def __scrub_dotnet(key, value, parent):
            if key == "StackTrace" and isinstance(value, dict):
                value["value"] = "<scrubbed>"
                return value
            elif key in ["stacktrace", "stack"]:
                scrubbed = []
                for entry in value:
                    # skip inner runtime methods from stack traces since they are not relevant to debugger
                    if entry["function"].startswith(("Microsoft", "System")):
                        continue

                    if "lambda_" in entry["function"]:
                        return re.sub(r"(lambda_method)\d+", r"\1<scrubbed>", entry["function"])

                    scrubbed.append(__scrub(entry))

                scrubbed.append({"<runtime>": "<scrubbed>"})
                return scrubbed
            return __scrub(value)

        def __scrub_none(key, value, parent):
            return __scrub(value)

        scrub_language = None
        if self.get_tracer()["language"] == "java":
            scrub_language = __scrub_java
        elif self.get_tracer()["language"] == "dotnet":
            scrub_language = __scrub_dotnet
        else:
            scrub_language = __scrub_none

        def __approve(snapshots):
            debugger.write_approval(snapshots, test_name, "snapshots_received")

            if _OVERRIDE_APROVALS:
                debugger.write_approval(snapshots, test_name, "snapshots_expected")

            expected_snapshots = debugger.read_approval(test_name, "snapshots_expected")
            assert expected_snapshots == snapshots
            # assert all(
            #     "exceptionId" in snapshot for snapshot in snapshots
            # ), "One or more snapshots don't have 'exceptionId' field"

        assert snapshots, "Snapshots not found"

        if _SCRUB_VALUES:
            snapshots = [__scrub(snapshot) for snapshot in snapshots]

        __approve(snapshots)

    def _validate_spans(self, test_name: str, spans):
        def __scrub(data):
            scrubbed_spans = {}
            span_number = 0

            for span in data.values():
                for key, value in span.items():
                    if key in ["traceID", "spanID", "parentID", "start", "duration", "metrics"]:
                        span[key] = "<scrubbed>"
                        continue

                    if key == "meta":
                        for meta_key in value.keys():
                            if meta_key.endswith("id"):
                                value[meta_key] = "<scrubbed>"
                                continue

                            if meta_key.endswith("hash"):
                                value[meta_key] = "<scrubbed>"
                                continue

                            if meta_key.endswith("version"):
                                value[meta_key] = "<scrubbed>"
                                continue

                            if meta_key in [
                                "http.request.headers.user-agent",
                                "http.useragent",
                                "thread.name",
                                "network.client.ip",
                                "http.client_ip",
                            ]:
                                value[meta_key] = "<scrubbed>"
                                continue

                            if meta_key == "error.stack":
                                value[meta_key] = value[meta_key][:128] + "<scrubbed>"
                                continue

                        span[key] = dict(sorted(value.items()))

                scrubbed_spans[f"snapshot_{span_number}"] = dict(sorted(span.items()))
                span_number += 1

            return scrubbed_spans

        def __approve(spans):
            assert spans, "Spans not found"

            debugger.write_approval(spans, test_name, "spans_received")

            if _OVERRIDE_APROVALS:
                debugger.write_approval(spans, test_name, "spans_expected")

            expected = debugger.read_approval(test_name, "spans_expected")
            assert expected == spans

            missing_keys_dict = {}
            snapshot_id_pattern = re.compile(r"_dd\.debug\.error\.\d+\.snapshot_id")

            for guid, element in spans.items():
                missing_keys = []

                if "_dd.debug.error.exception_hash" not in element["meta"]:
                    missing_keys.append("_dd.debug.error.exception_hash")

                if not any(snapshot_id_pattern.match(key) for key in element["meta"]):
                    missing_keys.append("_dd.debug.error.{n}.snapshot_id")

                if missing_keys:
                    missing_keys_dict[guid] = missing_keys

            assert not missing_keys_dict, f"Missing keys detected: {missing_keys_dict}"

        assert spans, "Spans not found"

        if _SCRUB_VALUES:
            spans = __scrub(spans)

        __approve(spans)

    ############ test ############
    ############ Simple ############
    def setup_exception_replay_simple(self):
        self._setup("/exceptionreplay/simple", "exceptionreplaysimple")

    def test_exception_replay_simple(self):
        self._assert("exception_replay_simple", "exceptionreplaysimple")

    ############ Recursion ############
    def setup_exception_replay_recursion_20(self):
        self._setup("/exceptionreplay/recursion?depth=20", "exceptionreplayrecursion")

    def test_exception_replay_recursion_20(self):
        self._assert("exception_replay_recursion_20", "exceptionreplayrecursion")

    ############ Inner ############
    def setup_exception_replay_inner(self):
        self._setup("/exceptionreplay/inner", "exceptionreplayinner")

    def test_exception_replay_inner(self):
        self._assert("exception_replay_inner", "exceptionreplayinner")

    ############ Rock Paper Scissors ############
    def setup_exception_replay_rockpaperscissors(self):
        self.weblog_responses = []

        retries = 0
        max_retries = 60

        shapes = {"rock": False, "paper": False, "scissors": False}

        while not all(shapes.values()) and retries < max_retries:
            for shape in shapes.keys():
                shape_found = shapes[shape]
                logger.debug(f"{shape} found: {shape_found}, retry #{retries}")

                if shape_found:
                    continue

                logger.debug(f"Waiting for snapshot for shape: {shape}, retry #{retries}")
                self.send_weblog_request(f"/exceptionreplay/rps?shape={shape}", reset=False)

                shapes[shape] = self.wait_for_snapshot_received(
                    method_name="exceptionreplayrockpaperscissors", exception_message=shape
                )

            retries += 1

    def test_exception_replay_rockpaperscissors(self):
        self._assert("exception_replay_rockpaperscissors", "exceptionreplayrockpaperscissors")
