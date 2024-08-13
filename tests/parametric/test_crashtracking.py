"""
Test the crashtracking (RC) feature of the APM libraries.
"""

import pytest
import json

from utils import bug, context, features, irrelevant, missing_feature, rfc, scenarios, flaky

# this global mark applies to all tests in this file.
#   DD_TRACE_OTEL_ENABLED=true is required in some tracers (.NET, Python?)
#   CORECLR_ENABLE_PROFILING=1 is required in .NET to enable auto-instrumentation
pytestmark = pytest.mark.parametrize(
    "library_env", [{"CORECLR_ENABLE_PROFILING": "1", "AALD_PRELOAD": "/opt/datadog/continuousprofiler/Datadog.Linux.ApiWrapper.x64.so"}],
)

@scenarios.parametric
@features.crashtracking
class Test_Crashtracking:
    def test_should_fail(self, test_agent, test_library):
        test_library.crash()

        event = test_agent.wait_for_telemetry_event("logs", wait_loops=4000)
        print("*************************************")
        print(event)
        print("*************************************")
        message = json.loads(event["payload"][0]["message"])
        tags = message["tags"]

        if 'severity' in tags:
            assert(tags["severity"] == "crash")
        else:        
            assert(message["is_crash"] == "true")