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
    @missing_feature(context.library == "java", reason="Not implemented")
    @missing_feature(context.library == "golang", reason="Not implemented")
    @missing_feature(context.library == "nodejs", reason="Not implemented")
    @missing_feature(context.library == "ruby", reason="Not implemented")
    @missing_feature(context.library == "php", reason="Not implemented")
    @missing_feature(context.library == "cpp", reason="Not implemented")
    def test_report_crash(self, test_agent, test_library):
        test_library.crash()

        event = test_agent.wait_for_telemetry_event("logs", wait_loops=400)
        assert self.is_crash_report(event)

    @missing_feature(context.library == "dotnet", reason="Not implemented")
    @missing_feature(context.library == "java", reason="Not implemented")
    @missing_feature(context.library == "golang", reason="Not implemented")
    @missing_feature(context.library == "nodejs", reason="Not implemented")
    @missing_feature(context.library == "ruby", reason="Not implemented")
    @missing_feature(context.library == "php", reason="Not implemented")
    @missing_feature(context.library == "cpp", reason="Not implemented")
    @pytest.mark.parametrize("library_env", [{"DD_CRASHTRACKING_ENABLED": "false"}])
    def test_disable_crashtracking(self, test_agent, test_library):
        test_library.crash()

        requests = test_agent.raw_telemetry(clear=True)

        for req in requests:
            event = json.loads(base64.b64decode(req["body"]))

            if event["request_type"] == "logs":
                assert self.is_crash_report(event) == False

    def is_crash_report(self, event) -> bool:
        message = json.loads(event["payload"][0]["message"])

        if context.library == "python":
            # Need to do this cleaning due to the way the tags get
            # populated in the crashtracking telemetry event
            # by libdatadog==v12.0.0
            raw_tags = message.get("metadata", {}).get("tags", [])
            tags = {tag.split(":")[0]: tag.split(":")[1] for tag in raw_tags}
        else:
            tags = message["tags"]

        if "severity" in tags:
            return tags["severity"] == "crash"
        elif "is_crash" in tags:
            return tags["is_crash"] == True

        return False
