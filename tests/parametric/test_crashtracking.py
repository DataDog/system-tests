"""Test the crashtracking (RC) feature of the APM libraries."""

import pytest
import json
import base64

from utils import bug, context, features, scenarios
from utils.tools import logger


@scenarios.parametric
@features.crashtracking
class Test_Crashtracking:
    @bug(context.library >= "ruby@2.7.2-dev", reason="APMLP-335")
    @pytest.mark.parametrize("library_env", [{"DD_CRASHTRACKING_ENABLED": "true"}])
    def test_report_crash(self, test_agent, test_library):
        test_library.crash()

        event = test_agent.wait_for_telemetry_event("logs", wait_loops=400)
        self.assert_crash_report(test_library, event)

    @pytest.mark.parametrize("library_env", [{"DD_CRASHTRACKING_ENABLED": "false"}])
    def test_disable_crashtracking(self, test_agent, test_library):
        test_library.crash()

        requests = test_agent.raw_telemetry(clear=True)

        for req in requests:
            event = json.loads(base64.b64decode(req["body"]))

            if event["request_type"] == "logs":
                with pytest.raises(AssertionError):
                    self.assert_crash_report(test_library, event)

    @bug(library="java", reason="APMLP-302")
    @pytest.mark.parametrize("library_env", [{"DD_CRASHTRACKING_ENABLED": "true"}])
    def test_telemetry_timeout(self, test_agent, test_library, apm_test_server):
        test_agent.set_trace_delay(60)

        test_library.crash()

        try:
            # container.wait will throw if the application doesn't exit in time
            apm_test_server.container.wait(timeout=10)
        finally:
            test_agent.set_trace_delay(0)

    def assert_crash_report(self, test_library, event):
        assert isinstance(event.get("payload"), list), event.get("payload")
        assert event["payload"], event["payload"]
        assert isinstance(event["payload"][0], dict), event["payload"][0]
        assert "tags" in event["payload"][0]

        tags = event["payload"][0]["tags"]
        logger.debug(f"tags: {tags}")
        tags_dict = dict(item.split(":") for item in tags.split(","))
        logger.debug(f"tags_dict: {tags_dict}")

        # Until the crash tracking RFC is out, there is no standard way to identify crash reports.
        # Most client libraries are using libdatadog so tesing signum tag would work,
        # but Java isn't so we end up with testing for severity tag.
        if test_library.lang == "java":
            assert "severity" in tags_dict, tags_dict
            assert tags_dict["severity"] == "crash", tags_dict
        else:
            # According to the RFC, si_signo should be set to 11 for SIGSEGV
            assert "signum" in tags_dict or ("si_signo" in tags_dict and tags_dict["si_signo"] == "11"), tags_dict
