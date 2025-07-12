# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, missing_feature, features, rfc, weblog
from tests.appsec.iast.utils import (
    BaseSinkTest,
    validate_extended_location_data,
    validate_stack_traces,
    get_nodejs_iast_file_paths,
)


@features.iast_sink_command_injection
class TestCommandInjection(BaseSinkTest):
    """Test command injection detection."""

    vulnerability_type = "COMMAND_INJECTION"
    http_method = "POST"
    insecure_endpoint = "/iast/cmdi/test_insecure"
    secure_endpoint = "/iast/cmdi/test_secure"
    data = {"cmd": "ls"}
    location_map = {
        "java": "com.datadoghq.system_tests.iast.utils.CmdExamples",
        "nodejs": get_nodejs_iast_file_paths(),
        "python": {"flask-poc": "app.py", "django-poc": "app/urls.py"},
    }

    @missing_feature(library="nodejs", reason="Endpoint not implemented")
    @missing_feature(library="java", reason="Endpoint not implemented")
    def test_secure(self):
        super().test_secure()

    @missing_feature(context.library < "java@1.9.0", reason="Metrics not implemented")
    @missing_feature(library="dotnet", reason="Not implemented yet")
    def test_telemetry_metric_instrumented_sink(self):
        super().test_telemetry_metric_instrumented_sink()

    @missing_feature(context.library < "java@1.9.0", reason="Metrics not implemented")
    def test_telemetry_metric_executed_sink(self):
        super().test_telemetry_metric_executed_sink()


@rfc(
    "https://docs.google.com/document/d/1ga7yCKq2htgcwgQsInYZKktV0hNlv4drY9XzSxT-o5U/edit?tab=t.0#heading=h.d0f5wzmlfhat"
)
@features.iast_stack_trace
class TestCommandInjection_StackTrace:
    """Validate stack trace generation"""

    def setup_stack_trace(self):
        self.r = weblog.post("/iast/cmdi/test_insecure", data={"cmd": "ls"})

    def test_stack_trace(self):
        validate_stack_traces(self.r)


@rfc("https://docs.google.com/document/d/1R8AIuQ9_rMHBPdChCb5jRwPrg1WvIz96c_WQ3y8DWk4")
@features.iast_extended_location
class TestCommandInjection_ExtendedLocation:
    """Test extended location data"""

    vulnerability_type = "COMMAND_INJECTION"

    def setup_extended_location_data(self):
        self.r = weblog.post("/iast/cmdi/test_insecure", data={"cmd": "ls"})

    def test_extended_location_data(self):
        validate_extended_location_data(self.r, self.vulnerability_type)
