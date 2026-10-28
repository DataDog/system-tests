"""Test the crashtracking (RC) feature of the APM libraries."""

import base64
import json
import time

from utils import pytest

from utils import features, scenarios, logger
from utils.docker_fixtures import TestAgentAPI, ParametricTestClientApi as APMLibrary


@scenarios.parametric
@features.crashtracking
class Test_Crashtracking:
    @pytest.mark.parametrize("library_env", [{"DD_CRASHTRACKING_ENABLED": "true"}])
    def test_report_crash(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        test_library.crash()

        event = self.wait_for_crash_report(test_agent)

        # Handling both v1 and v2 of the crashtracking payload so that we can
        # update to v2 without breaking the test.
        if isinstance(event.get("payload"), list):
            self.assert_crash_report_v1(test_library, event)
        else:
            self.assert_crash_report_v2(test_library, event)

    def wait_for_crash_report(self, test_agent: TestAgentAPI) -> dict:
        # The crashtracker sends telemetry "logs" events that are not the crash report itself:
        # crash pings (`is_crash_ping:true`) and receiver debug logs (`is_crash_debug:true`, sent
        # when e.g. the stack trace is incomplete). They can be captured before or after the
        # crash report, so the report is selected by scanning all captured "logs" events.
        # The 15s total wait matches the crashtracker receiver's timeout: dd-trace-rb configures
        # 15s (upload_timeout_seconds in its crashtracking component), and the receiver can spend
        # up to that long collecting and uploading the report after the crash. The report usually
        # arrives within a few seconds, so the loop exits well before the budget is spent.
        for _ in range(30):
            for event in test_agent.get_telemetry_events("logs"):
                tags = self.crash_event_tags(event)
                if "is_crash_ping:true" not in tags and "is_crash_debug:true" not in tags:
                    return event
            time.sleep(0.5)
        raise AssertionError("Crash report not found in telemetry logs events")

    def crash_event_tags(self, event: dict) -> str:
        payload = event.get("payload")
        if isinstance(payload, list):
            return payload[0].get("tags", "") if payload else ""
        if isinstance(payload, dict) and payload.get("logs"):
            return payload["logs"][0].get("tags", "")
        return ""

    @pytest.mark.parametrize("library_env", [{"DD_CRASHTRACKING_ENABLED": "false"}])
    def test_disable_crashtracking(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        test_library.crash()

        requests = test_agent.raw_telemetry(clear=True)

        for req in requests:
            event = json.loads(base64.b64decode(req["body"]))

            if event["request_type"] == "logs":
                if isinstance(event.get("payload"), list):
                    with pytest.raises(AssertionError):
                        self.assert_crash_report_v1(test_library, event)
                else:  # If payload is a dict
                    with pytest.raises(AssertionError):
                        self.assert_crash_report_v2(test_library, event)

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
                report for report in self.get_error_tracking_crash_reports(test_agent) if report["error"]["is_crash"]
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

    def assert_crash_report_v1(self, test_library: APMLibrary, event: dict):
        logger.debug(f"event: {json.dumps(event, indent=2)}")

        assert isinstance(event.get("payload"), list), event.get("payload")
        assert event["payload"], event["payload"]
        assert isinstance(event["payload"][0], dict), event["payload"][0]
        assert "tags" in event["payload"][0]

        tags = event["payload"][0]["tags"]
        tags_dict = dict(item.split(":") for item in tags.split(","))
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

    def assert_crash_report_v2(self, test_library: APMLibrary, event: dict):
        logger.debug(f"event: {json.dumps(event, indent=2)}")

        assert isinstance(event.get("payload"), dict), event.get("payload")
        assert isinstance(event["payload"].get("logs"), list), event["payload"].get("logs")
        assert event["payload"]["logs"], event["payload"]["logs"]
        assert isinstance(event["payload"]["logs"][0], dict), event["payload"]["logs"][0]
        assert "tags" in event["payload"]["logs"][0]

        tags = event["payload"]["logs"][0]["tags"]
        tags_dict = dict(item.split(":") for item in tags.split(","))
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
