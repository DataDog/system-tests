# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import re
import os
import tests.debugger.utils as debugger
import time
from pathlib import Path
from packaging import version
from utils import scenarios, features, bug, context, flaky, irrelevant, missing_feature, logger


def get_env_bool(env_var_name, *, default=False) -> bool:
    value = os.getenv(env_var_name, str(default)).lower()
    return value in {"true", "True", "1"}


_OVERRIDE_APROVALS = get_env_bool("DI_OVERRIDE_APPROVALS")
_STORE_NEW_APPROVALS = get_env_bool("DI_STORE_NEW_APPROVALS")
_SKIP_SCRUB = get_env_bool("DI_SKIP_SCRUB")

_max_retries = 2
_timeout_first = 5
_timeout_next = 30


@features.debugger_exception_replay
@scenarios.debugger_exception_replay
@missing_feature(context.library == "php", reason="Not yet implemented", force_skip=True)
@missing_feature(context.library == "ruby", reason="Not yet implemented", force_skip=True)
@missing_feature(context.library == "nodejs", reason="Not yet implemented", force_skip=True)
@missing_feature(context.library == "golang", reason="Not yet implemented", force_skip=True)
@irrelevant(context.library <= "dotnet@3.28.0", reason="DEBUG-4582")
class Test_Debugger_Exception_Replay(debugger.BaseDebuggerTest):
    snapshots: dict = {}
    spans: dict = {}

    ############ setup ############
    def _setup(self, request_path, exception_message):
        self.weblog_responses = []

        retries = 0
        timeout = _timeout_first
        snapshot_found = False

        while not snapshot_found and retries < _max_retries:
            logger.debug(f"Waiting for snapshot, retry #{retries}")

            self.send_weblog_request(request_path, reset=False)
            snapshot_found = self.wait_for_snapshot_received(exception_message, timeout)
            timeout = _timeout_next

            retries += 1

    ############ assert ############
    def _assert(self, test_name, expected_exception_messages):
        def __filter_contents_by_message():
            filtered_contents = []

            for contents in self.probe_snapshots.values():
                for content in contents:
                    for expected_exception_message in expected_exception_messages:
                        exception_message = self.get_exception_message(content["debugger"]["snapshot"])
                        if expected_exception_message in exception_message:
                            filtered_contents.append((exception_message, content))

            def get_sort_key(content_tuple):
                message, content = content_tuple
                snapshot = content["debugger"]["snapshot"]

                method_name = snapshot.get("probe", {}).get("location", {}).get("method", "")
                line_number = snapshot.get("probe", {}).get("location", {}).get("lines", [])

                if "recursion" in message.lower():
                    args = snapshot.get("captures", {}).get("return", {}).get("arguments", {})
                    if "currentDepth" in args:
                        current_depth = args["currentDepth"].get("value")
                    else:
                        current_depth = "-1"
                    return (message, method_name, line_number, current_depth)
                else:
                    return (message, method_name, line_number)

            filtered_contents.sort(key=get_sort_key)

            return [snapshot for _, snapshot in filtered_contents]

        def __filter_spans_by_snapshot_id(snapshots):
            filtered_spans = {}

            for snapshot in snapshots:
                snapshot_id = snapshot["id"]
                for spans in self.probe_spans.values():
                    for span in spans:
                        snapshot_ids_in_span = {
                            key: value for key, value in span["meta"].items() if key.endswith("snapshot_id")
                        }.values()

                        if snapshot_id in snapshot_ids_in_span:
                            filtered_spans[snapshot_id] = span
                            break

            return filtered_spans

        def __filter_spans_by_span_id(contents):
            filtered_spans = {}
            for content in contents:
                span_id = content.get("dd", {}).get("span_id") or content.get("dd.span_id")
                snapshot_id = content["debugger"]["snapshot"]["id"]

                for spans_list in self.probe_spans.values():
                    for span in spans_list:
                        if span.get("spanID") == span_id:
                            filtered_spans[snapshot_id] = span
                            break

            return filtered_spans

        self.collect()
        self.assert_all_weblog_responses_ok(expected_code=500)

        contents = __filter_contents_by_message()
        snapshots = [content["debugger"]["snapshot"] for content in contents]

        self._validate_exception_replay_snapshots(test_name, snapshots)

        if self.get_tracer()["language"] in ["python", "java"]:
            spans = __filter_spans_by_span_id(contents)
        else:
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
                        scrubbed_value = scrub_language(key, value, data)
                        if scrubbed_value is not None:
                            scrubbed_data[key] = scrubbed_value

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

        def __scrub_dotnet(key, value, parent):  # noqa: ARG001
            if key == "Id":
                return "<scrubbed>"
            elif key == "StackTrace" and isinstance(value, dict):
                value["value"] = "<scrubbed>"
                return value
            elif key == "function":
                if "lambda_" in value:
                    value = re.sub(r"(lambda_method)\d+", r"\1<scrubbed>", value)
                if re.search(r"<[^>]+>", value):
                    value = re.sub(r"(.*>)(.*)", r"\1<scrubbed>", value)
                return value
            elif key in ["stacktrace", "stack"]:
                scrubbed = []
                for entry in value:
                    # skip inner runtime methods from stack traces since they are not relevant to debugger
                    if entry["function"].startswith(("Microsoft", "System", "Unknown")):
                        continue

                    scrubbed.append(__scrub(entry))

                scrubbed.append({"<runtime>": "<scrubbed>"})
                return scrubbed
            return __scrub(value)

        def __scrub_python(key, value, parent):  # noqa: ARG001
            if key == "@exception":
                value["fields"] = "<scrubbed>"
                return value

            elif key in ("exception-id", "staticFields"):
                return "<scrubbed>"

            elif key in ["stacktrace", "stack"]:
                scrubbed = []
                for entry in value:
                    # skip inner runtime methods from stack traces since they are not relevant to debugger
                    if entry["fileName"] != "/app/exception_replay_controller.py":
                        continue

                    scrubbed.append(__scrub(entry))

                scrubbed.append({"<runtime>": "<scrubbed>"})
                return scrubbed

            elif key == "type" and value == "er_snapshot":
                return None

            return __scrub(value)

        def __scrub_none(key, value, parent):  # noqa: ARG001
            return __scrub(value)

        if self.get_tracer()["language"] == "java":
            scrub_language = __scrub_java
        elif self.get_tracer()["language"] == "dotnet":
            scrub_language = __scrub_dotnet
        elif self.get_tracer()["language"] == "python":
            scrub_language = __scrub_python
        else:
            scrub_language = __scrub_none

        def __approve(snapshots):
            self._write_approval(snapshots, test_name, "snapshots_received")

            if _OVERRIDE_APROVALS or _STORE_NEW_APPROVALS:
                self._write_approval(snapshots, test_name, "snapshots_expected")

            expected_snapshots = self._read_approval(test_name, "snapshots_expected")
            assert expected_snapshots == snapshots
            assert all(
                "exceptionId" in snapshot for snapshot in snapshots
            ), "One or more snapshots don't have 'exceptionId' field"

        assert snapshots, "Snapshots not found"

        if not _SKIP_SCRUB:
            snapshots = [__scrub(snapshot) for snapshot in snapshots]

        self.snapshots = snapshots
        __approve(snapshots)

    def _validate_spans(self, test_name: str, spans):
        def __scrub(data):
            def scrub_span(key, value):
                if key in {"traceID", "spanID", "parentID", "start", "duration", "metrics"}:
                    return "<scrubbed>"

                if key == "meta" and isinstance(value, dict):
                    keys_to_remove = []
                    for meta_key, meta_value in value.items():
                        # These keys are present in some library versions but not others,
                        # but are unrelated to the functionality under test
                        if meta_key in {
                            "_dd.appsec.fp.http.endpoint",
                            "_dd.appsec.fp.http.header",
                            "_dd.appsec.fp.http.network",
                            "_dd.appsec.fp.session",
                        }:
                            keys_to_remove.append(meta_key)
                        elif meta_key.endswith(("id", "hash", "version")) or meta_key in {
                            "http.request.headers.user-agent",
                            "http.useragent",
                            "thread.name",
                            "network.client.ip",
                            "http.client_ip",
                        }:
                            value[meta_key] = "<scrubbed>"
                        elif meta_key == "error.stack":
                            value[meta_key] = meta_value[:128] + "<scrubbed>"

                    for k in keys_to_remove:
                        value.pop(k, None)

                    return dict(sorted(value.items()))

                return value

            scrubbed_spans = {}

            spans = [{k: scrub_span(k, v) for k, v in span.items()} for span in data.values()]
            sorted_spans = sorted(spans, key=lambda x: x["meta"]["error.type"])

            # Assign scrubbed spans with unique snapshot labels
            for span_number, span in enumerate(sorted_spans):
                scrubbed_spans[f"snapshot_{span_number}"] = dict(sorted(span.items()))

            return scrubbed_spans

        def __approve(spans):
            self._write_approval(spans, test_name, "spans_received")

            if _OVERRIDE_APROVALS or _STORE_NEW_APPROVALS:
                self._write_approval(spans, test_name, "spans_expected")

            expected = self._read_approval(test_name, "spans_expected")
            assert expected == spans

            missing_keys_dict = {}

            for guid, element in spans.items():
                missing_keys = []

                if "_dd.debug.error.exception_hash" not in element["meta"]:
                    missing_keys.append("_dd.debug.error.exception_hash")

                if not any("error.type" for key in element["meta"]):
                    missing_keys.append("error.type")

                if not any(key in element["meta"] for key in ["error.msg", "error.message"]):
                    missing_keys.append("error.type and either msg or message")

                if missing_keys:
                    missing_keys_dict[guid] = missing_keys

            assert not missing_keys_dict, f"Missing keys detected: {missing_keys_dict}"

        assert spans, "Spans not found"

        if not _SKIP_SCRUB:
            spans = __scrub(spans)

        self.spans = spans
        __approve(spans)

    def _validate_recursion_snapshots(self, snapshots, limit):
        assert (
            len(snapshots) == limit + 1
        ), f"Expected {limit + 1} snapshots for recursion limit {limit}, got {len(snapshots)}"

        entry_method = "exceptionReplayRecursion"
        helper_method = "exceptionReplayRecursionHelper"

        def get_frames(snapshot):
            if self.get_tracer()["language"] in ["java", "dotnet"]:
                method = snapshot.get("probe", {}).get("location", {}).get("method", None)
                if method:
                    return [{"function": method}]

            return snapshot.get("stack", [])

        found_top = False
        found_lowest = False

        def check_frames(frames):
            nonlocal found_top, found_lowest

            for frame in frames:
                if "<runtime>" in frame:
                    continue
                if entry_method == frame["function"]:
                    found_top = True
                if helper_method == frame["function"]:
                    found_lowest = True
                if found_top and found_lowest:
                    break

        for snapshot in snapshots:
            check_frames(get_frames(snapshot))

            if found_top and found_lowest:
                break

        assert found_top, "Top layer snapshot not found"
        assert found_lowest, "Lowest layer snapshot not found"

    def _validate_no_capture_reason(self, exception_key: str, expected_reason: str):
        """Validate no_capture_reason field from collected spans."""
        spans_with_no_capture_reason = self.probe_spans.get(exception_key, [])
        assert (
            spans_with_no_capture_reason
        ), f"No spans with _dd.debug.error.no_capture_reason found for {exception_key}"

        found_expected_reason = False
        actual_reasons = []

        for span in spans_with_no_capture_reason:
            meta = span.get("meta", {})
            actual_reason = meta["_dd.debug.error.no_capture_reason"]
            actual_reasons.append(actual_reason)

            logger.debug(f"Found _dd.debug.error.no_capture_reason: {actual_reason}")

            if actual_reason == expected_reason:
                found_expected_reason = True
                logger.debug(f"Expected reason '{expected_reason}' matches actual reason '{actual_reason}'")
            else:
                logger.warning(f"Expected reason '{expected_reason}' but got '{actual_reason}'")

        assert (
            found_expected_reason
        ), f"Expected no_capture_reason '{expected_reason}' not found. Actual reasons: {actual_reasons}"

    ############ Approvals ############

    def _get_approval_version(self) -> str:
        """Get the version to use for approvals.
        - If STORE_NEW_APPROVALS: use current version (creates new folder)
        - Otherwise: use maximum compatible version (assumes folders exist)
        """
        current_version = self.get_tracer()["tracer_version"]
        current_version = re.sub(r"[^0-9.].*$", "", current_version)

        if _STORE_NEW_APPROVALS:
            return current_version

        language = self.get_tracer()["language"]
        approvals_dir = Path(__file__).parent / "approvals"
        language_dir = approvals_dir / language

        current_ver = version.parse(current_version)
        compatible_versions = []

        for item in language_dir.iterdir():
            if item.is_dir():
                item_ver = version.parse(item.name)
                if item_ver <= current_ver:
                    compatible_versions.append(item.name)

        compatible_versions.sort(key=lambda x: version.parse(x), reverse=True)
        return compatible_versions[0]

    def _write_approval(self, data: list, test_name: str, suffix: str) -> None:
        """Write approval data to version-aware path."""
        version = self._get_approval_version()
        debugger.write_approval(data, test_name, suffix, version)

    def _read_approval(self, test_name: str, suffix: str) -> dict:
        """Read approval data from version-aware path."""
        version = self._get_approval_version()
        return debugger.read_approval(test_name, suffix, version)

    ########### test ############
    ########### Simple ############
    def setup_exception_replay_simple(self):
        self._setup("/exceptionreplay/simple", "simple exception")

    @bug(context.library < "dotnet@3.10.0", reason="DEBUG-2799")
    @bug(context.library < "java@1.46.0", reason="DEBUG-3285")
    def test_exception_replay_simple(self):
        self._assert("exception_replay_simple", ["simple exception"])

    ########### Recursion ############
    def setup_exception_replay_recursion_3(self):
        self._setup("/exceptionreplay/recursion?depth=3", "recursion exception depth 3")

    @bug(context.library < "dotnet@3.10.0", reason="DEBUG-2799")
    @bug(context.library < "java@1.46.0", reason="DEBUG-3285")
    def test_exception_replay_recursion_3(self):
        self._assert("exception_replay_recursion_3", ["recursion exception depth 3"])
        self._validate_recursion_snapshots(self.snapshots, 4)

    def setup_exception_replay_recursion_5(self):
        self._setup("/exceptionreplay/recursion?depth=5", "recursion exception depth 5")

    @bug(context.library < "dotnet@3.10.0", reason="DEBUG-2799")
    @bug(context.library == "dotnet", reason="DEBUG-3283")
    @bug(context.library < "java@1.46.0", reason="DEBUG-3285")
    def test_exception_replay_recursion_5(self):
        self._assert("exception_replay_recursion_5", ["recursion exception depth 5"])
        self._validate_recursion_snapshots(self.snapshots, 6)

    def setup_exception_replay_recursion_20(self):
        self._setup("/exceptionreplay/recursion?depth=20", "recursion exception depth 20")

    @bug(context.library < "dotnet@3.10.0", reason="DEBUG-2799")
    @bug(context.library == "dotnet", reason="DEBUG-3283")
    @bug(context.library < "java@1.46.0", reason="DEBUG-3285")
    @bug(context.library == "java", reason="DEBUG-3390")
    def test_exception_replay_recursion_20(self):
        self._assert("exception_replay_recursion_20", ["recursion exception depth 20"])
        self._validate_recursion_snapshots(self.snapshots, 9)

    def setup_exception_replay_recursion_inlined(self):
        self._setup("/exceptionreplay/recursion_inline?depth=4", "recursion exception depth 4")

    @irrelevant(context.library != "dotnet", reason="Test for specific bug in dotnet")
    @bug(context.library == "dotnet", reason="DEBUG-3447")
    def test_exception_replay_recursion_inlined(self):
        self._assert("exception_replay_recursion_4", ["recursion exception depth 4"])
        self._validate_recursion_snapshots(self.snapshots, 4)

    ############ Inner ############
    def setup_exception_replay_inner(self):
        self._setup("/exceptionreplay/inner", "outer exception")

    @bug(context.library < "dotnet@3.10.0", reason="DEBUG-2799")
    @bug(context.library < "java@1.46.0", reason="DEBUG-3285")
    def test_exception_replay_inner(self):
        self._assert("exception_replay_inner", ["outer exception"])

    ############ Rock Paper Scissors ############
    def setup_exception_replay_rockpaperscissors(self):
        self.weblog_responses = []

        retries = 0
        timeout = _timeout_first

        shapes: dict[str, bool] = {"rock": False, "paper": False, "scissors": False}

        while not all(shapes.values()) and retries < _max_retries:
            for shape, shape_found in shapes.items():
                logger.debug(f"{shape} found: {shape_found}, retry #{retries}")

                if shape_found:
                    continue

                logger.debug(f"Waiting for snapshot for shape: {shape}, retry #{retries}")
                self.send_weblog_request(f"/exceptionreplay/rps?shape={shape}", reset=False)

                shapes[shape] = self.wait_for_snapshot_received(shape, timeout)
                if self.get_tracer()["language"] == "python":
                    time.sleep(1)

                timeout = _timeout_next

            retries += 1

    @bug(context.library < "dotnet@3.10.0", reason="DEBUG-2799")
    @bug(context.library < "java@1.46.0", reason="DEBUG-3285")
    def test_exception_replay_rockpaperscissors(self):
        self._assert("exception_replay_rockpaperscissors", ["rock", "paper", "scissors"])

    ############ Multiple Stack Frames ############
    def setup_exception_replay_multiframe(self):
        self._setup("/exceptionreplay/multiframe", "multiple stack frames exception")

    @bug(context.library < "dotnet@3.10.0", reason="DEBUG-2799")
    @bug(context.library < "java@1.46.0", reason="DEBUG-3285")
    def test_exception_replay_multiframe(self):
        self._assert("exception_replay_multiframe", ["multiple stack frames exception"])

    ############ Async ############
    def setup_exception_replay_async(self):
        self._setup("/exceptionreplay/async", "async exception")

    @flaky(context.library == "dotnet", reason="DEBUG-3281")
    @bug(context.library < "java@1.46.0", reason="DEBUG-3285")
    def test_exception_replay_async(self):
        self._assert("exception_replay_async", ["async exception"])

    ############ No capture reason ############
    no_capture_reason_span_found = False

    def _setup_no_capture_exception(self, exception_key: str):
        self.send_weblog_request(f"/exceptionreplay/{exception_key}")
        self.wait_for_no_capture_reason_span(exception_key, _timeout_next)

    def _test_no_capture_exception(self, exception_key: str, expected_reason: str):
        self.collect()
        self.assert_all_weblog_responses_ok(expected_code=500)
        self._validate_no_capture_reason(exception_key, expected_reason)

    ############ dotnet OutOfMemoryException Test ############
    def setup_exception_replay_outofmemory(self):
        self._setup_no_capture_exception("outofmemory")

    @missing_feature(context.library != "dotnet", reason="Implemented only for dotnet", force_skip=True)
    def test_exception_replay_outofmemory(self):
        self._test_no_capture_exception("outofmemory", "NonSupportedExceptionType")

    ############ .NET StackOverflowException Test ############
    def setup_exception_replay_stackoverflow(self):
        self._setup_no_capture_exception("stackoverflow")

    @missing_feature(context.library != "dotnet", reason="Implemented only for dotnet", force_skip=True)
    @bug(context.library == "dotnet", reason="DEBUG-3999")
    def test_exception_replay_stackoverflow(self):
        self._test_no_capture_exception("stackoverflow", "NonSupportedExceptionType")

    ############ .NET First Hit Exception Test ############
    def setup_exception_replay_firsthit(self):
        self._setup_no_capture_exception("firsthit")

    @missing_feature(context.library != "dotnet", reason="Implemented only for dotnet", force_skip=True)
    def test_exception_replay_firsthit(self):
        self._test_no_capture_exception("firsthit", "FirstOccurrence")
