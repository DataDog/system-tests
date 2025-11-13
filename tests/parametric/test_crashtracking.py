"""Test the crashtracking (RC) feature of the APM libraries."""

import base64
import json
import pytest

from utils import bug, features, scenarios, logger
from utils.parametric._library_client import APMLibrary
from utils.docker_fixtures import TestAgentAPI


@scenarios.parametric
@features.crashtracking
class Test_Crashtracking:
    @pytest.mark.parametrize("library_env", [{"DD_CRASHTRACKING_ENABLED": "true"}])
    def test_report_crash(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        test_library.crash()

        while True:
            event = test_agent.wait_for_telemetry_event("logs", wait_loops=400)
            if event is None or "is_crash_ping:true" not in event["payload"][0]["tags"]:
                break
        self.assert_crash_report(test_library, event)

    @pytest.mark.parametrize("library_env", [{"DD_CRASHTRACKING_ENABLED": "false"}])
    def test_disable_crashtracking(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        test_library.crash()

        requests = test_agent.raw_telemetry(clear=True)

        for req in requests:
            event = json.loads(base64.b64decode(req["body"]))

            if event["request_type"] == "logs":
                with pytest.raises(AssertionError):
                    self.assert_crash_report(test_library, event)

    @bug(library="java", reason="APMLP-302")
    @pytest.mark.parametrize("library_env", [{"DD_CRASHTRACKING_ENABLED": "true"}])
    def test_telemetry_timeout(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        test_agent.set_trace_delay(60)

        test_library.crash()

        try:
            # container.wait will throw if the application doesn't exit in time
            test_library._client.container.wait(timeout=10)  # noqa: SLF001
        finally:
            test_agent.set_trace_delay(0)

    def assert_crash_report(self, test_library: APMLibrary, event: dict):
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
