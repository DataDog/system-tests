"""Test the crashtracking (RC) feature of the APM libraries."""

import base64
import json
import time
from collections.abc import Iterator
from typing import Any

from utils import pytest

from utils import features, scenarios, logger
from utils.docker_fixtures import TestAgentAPI, ParametricTestClientApi as APMLibrary

# The crashtracker receiver can spend up to 15 s collecting and uploading the report after
# the crash: dd-trace-rb configures 15 s (upload_timeout_seconds in its crashtracking
# component), the largest budget among the tested libraries. The report usually arrives
# within a few seconds, so the wait ends well before this budget is spent.
CRASH_REPORT_WAIT_SECONDS = 15.0
CRASH_REPORT_POLL_INTERVAL_SECONDS = 0.5


def is_crash_report(entry: object) -> bool:
    """Return whether a telemetry log entry is a crash report.

    The crash report is the only crashtracker upload tagged ``is_crash:true``: crash pings
    are tagged ``is_crash_ping:true`` and receiver debug logs ``is_crash_debug:true``.
    """
    return isinstance(entry, dict) and "is_crash:true" in entry.get("tags", "")


@scenarios.parametric
@features.crashtracking
class Test_Crashtracking:
    @pytest.mark.parametrize("library_env", [{"DD_CRASHTRACKING_ENABLED": "true"}])
    def test_report_crash(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        test_library.crash()

        self.assert_crash_report(test_library, self.wait_for_crash_report(test_agent))

    def wait_for_crash_report(self, test_agent: TestAgentAPI) -> dict[str, Any]:
        """Wait for the crash report telemetry log entry and return it.

        The report is selected by its ``is_crash:true`` tag so that the other
        crashtracker uploads, which can be captured before or after the report, never
        misselect: crash pings and receiver debug logs (for example when the stack trace
        is incomplete) carry their own tags without ``is_crash:true``.
        """
        deadline = time.monotonic() + CRASH_REPORT_WAIT_SECONDS
        while True:
            for entry in self.telemetry_log_entries(test_agent):
                if is_crash_report(entry):
                    return entry
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                captured_tags = [
                    entry.get("tags", "") if isinstance(entry, dict) else repr(entry)
                    for entry in self.telemetry_log_entries(test_agent)
                ]
                raise AssertionError(
                    f"Crash report not found in telemetry logs events within {CRASH_REPORT_WAIT_SECONDS:g} s;"
                    f" captured log entry tags: {captured_tags}"
                )
            time.sleep(min(CRASH_REPORT_POLL_INTERVAL_SECONDS, remaining))

    def telemetry_log_entries(self, test_agent: TestAgentAPI) -> Iterator[dict[str, Any]]:
        """Yield every log entry of every captured telemetry "logs" event, oldest first.

        Handling both v1 and v2 of the crashtracking payload so that we can update to
        v2 without breaking the test: v1 payloads are a bare list of log entries, v2
        payloads wrap the entries in a dict under "logs".
        """
        for event in test_agent.get_telemetry_events("logs"):
            payload = event.get("payload")
            if isinstance(payload, list):
                yield from payload
            elif isinstance(payload, dict):
                yield from payload.get("logs", [])

    @pytest.mark.parametrize("library_env", [{"DD_CRASHTRACKING_ENABLED": "false"}])
    def test_disable_crashtracking(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        test_library.crash()

        self.assert_no_crash_report(test_agent)

    def assert_no_crash_report(self, test_agent: TestAgentAPI) -> None:
        """Assert that no crash report appears in the captured telemetry.

        A crash report uploaded by a regression arrives within the crashtracker's
        upload budget, so absence is polled over that budget instead of asserted from a
        single read. Java's crash endpoint leaves the app running when crashtracking is
        disabled, so waiting for the container to exit, as the error-tracking disable
        test does, cannot gate the check here.
        """
        deadline = time.monotonic() + CRASH_REPORT_WAIT_SECONDS
        while True:
            for entry in self.telemetry_log_entries(test_agent):
                assert not is_crash_report(entry), entry.get("tags", "")
            if time.monotonic() >= deadline:
                return
            time.sleep(CRASH_REPORT_POLL_INTERVAL_SECONDS)

    @pytest.mark.parametrize("library_env", [{"DD_CRASHTRACKING_ENABLED": "true"}])
    def test_telemetry_timeout(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        test_agent.set_trace_delay(60)

        test_library.crash()

        try:
            # container.wait will throw if the application doesn't exit in time
            test_library.container.wait(timeout=10)
        finally:
            test_agent.set_trace_delay(0)

    # dd-trace-go sends crash reports to the Error Tracking intake through the
    # Agent EVP proxy instead of telemetry logs, so the telemetry-based tests
    # above cannot cover it.
    @pytest.mark.parametrize("library_env", [{"DD_CRASHTRACKING_ENABLED": "true"}])
    def test_report_crash_error_tracking(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        test_library.crash()

        self.assert_crash_report_error_tracking(self.wait_for_error_tracking_crash_report(test_agent))

    @pytest.mark.parametrize("library_env", [{"DD_CRASHTRACKING_ENABLED": "false"}])
    def test_disable_crashtracking_error_tracking(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        test_library.crash()

        test_library.container.wait(timeout=10)
        assert self.get_error_tracking_crash_reports(test_agent) == []

    def get_error_tracking_crash_reports(self, test_agent: TestAgentAPI) -> list[dict]:
        return [
            json.loads(base64.b64decode(req["body"]))
            for req in test_agent.requests()
            if req["url"].endswith("/evp_proxy/v4/api/v2/errorsintake")
        ]

    def wait_for_error_tracking_crash_report(self, test_agent: TestAgentAPI) -> dict:
        # The crashtracker also sends crash pings to the Error Tracking intake, so the report is
        # selected by its content instead of taking the last request received.
        for _ in range(400):
            reports = [
                report
                for report in self.get_error_tracking_crash_reports(test_agent)
                if report.get("error", {}).get("is_crash")
            ]
            if reports:
                return reports[-1]
            time.sleep(0.01)
        raise AssertionError("Crash report not found in Error Tracking intake requests")

    def assert_crash_report_error_tracking(self, report: dict) -> None:
        logger.debug(f"report: {json.dumps(report, indent=2)}")

        assert report["ddsource"] == "crashtracker"
        assert bool(report["error"]["is_crash"])
        assert "system-tests crash" in report["error"]["message"]

        tags = dict(item.split(":", 1) for item in report["ddtags"].split(",") if ":" in item)
        assert tags["language_name"] == "go", tags
        assert "language_version" in tags, tags
        assert "tracer_version" in tags, tags
        assert "data_schema_version" in tags, tags

    def assert_crash_report(self, test_library: APMLibrary, entry: dict[str, Any]) -> None:
        """Assert that the given telemetry log entry is a valid crash report."""
        logger.debug(f"crash report entry: {json.dumps(entry, indent=2)}")

        assert "tags" in entry, entry

        tags = entry["tags"]
        tags_dict = dict(item.split(":", 1) for item in tags.split(",") if ":" in item)
        logger.debug(f"tags_dict: {json.dumps(tags_dict, indent=2)}")

        # Until the crash tracking RFC is out, there is no standard way to identify crash reports.
        # Most client libraries are using libdatadog so tesing signum tag would work,
        # but Java isn't so we end up with testing for severity tag.
        if test_library.lang == "java":
            assert "severity" in tags_dict, tags_dict
            assert tags_dict["severity"] == "crash", tags_dict
        else:
            # those values are defined in python's module signal. But it's more clear to have this defined here
            SIGABRT = 6  # noqa: N806
            SIGSEGV = 11  # noqa: N806

            # According to the RFC, si_signo should be set to 11 for SIGSEGV
            # though, it's difficult for .NET to simulate a segfault, so SIGABRT is used instead
            expected_signal_value = f"{SIGABRT}" if test_library.lang == "dotnet" else f"{SIGSEGV}"

            if "signum" in tags_dict:
                assert tags_dict["signum"] == expected_signal_value
            elif "si_signo" in tags_dict:
                assert tags_dict["si_signo"] == expected_signal_value
            else:
                raise AssertionError("signum/si_signo not found in tags_dict")
