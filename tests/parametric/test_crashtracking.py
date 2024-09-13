"""
Test the crashtracking (RC) feature of the APM libraries.
"""

import pytest
import json
import base64

from utils import bug, context, features, irrelevant, missing_feature, rfc, scenarios, flaky


@scenarios.parametric
@features.crashtracking
class Test_Crashtracking:
    @missing_feature(context.library == "golang", reason="Not implemented")
    @missing_feature(context.library == "nodejs", reason="Not implemented")
    @missing_feature(context.library == "ruby", reason="Release in 2.3.0, test to be implemented with HTTP protocol instead of gRPC, see: https://datadoghq.atlassian.net/browse/APMON-1489")
    @missing_feature(context.library == "cpp", reason="Not implemented")
    def test_report_crash(self, test_agent, test_library):
        test_library.crash()

        event = test_agent.wait_for_telemetry_event("logs", wait_loops=400)
        assert self.is_crash_report(test_library, event)

    @missing_feature(context.library == "golang", reason="Not implemented")
    @missing_feature(context.library == "nodejs", reason="Not implemented")
    @missing_feature(context.library == "ruby", reason="Release in 2.3.0, test to be implemented with HTTP protocol instead of gRPC, see: https://datadoghq.atlassian.net/browse/APMON-1489")
    @missing_feature(context.library == "php", reason="Not implemented")
    @missing_feature(context.library == "cpp", reason="Not implemented")
    @pytest.mark.parametrize("library_env", [{"DD_CRASHTRACKING_ENABLED": "false"}])
    def test_disable_crashtracking(self, test_agent, test_library):
        test_library.crash()

        requests = test_agent.raw_telemetry(clear=True)

        for req in requests:
            event = json.loads(base64.b64decode(req["body"]))

            if event["request_type"] == "logs":
                assert self.is_crash_report(test_library, event) == False

    def is_crash_report(self, test_library, event) -> bool:
        tags = event["payload"][0]["tags"]
        print("tags: ", tags)
        tags_dict = dict(item.split(":") for item in tags.split(","))
        print("tags_dict: ", tags_dict)

        # Until the crash tracking RFC is out, there is no standard way to identify crash reports.
        # Most client libraries are using libdatadog so tesing signum tag would work,
        # but Java isn't so we end up with testing for severity tag.
        if test_library.lang == "java":
            return "severity" in tags_dict and tags_dict["severity"] == "crash"

        return "signum" in tags_dict
