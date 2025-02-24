# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, missing_feature, features, bug, rfc, weblog
from tests.appsec.iast.utils import BaseSinkTest, validate_extended_location_data, validate_stack_traces


@features.iast_sink_sql_injection
class TestSqlInjection(BaseSinkTest):
    """Verify SQL injection detection."""

    vulnerability_type = "SQL_INJECTION"
    http_method = "POST"
    insecure_endpoint = "/iast/sqli/test_insecure"
    secure_endpoint = "/iast/sqli/test_secure"
    data = {"username": "shaquille_oatmeal", "password": "123456"}
    location_map = {
        "java": "com.datadoghq.system_tests.iast.utils.SqlExamples",
        "nodejs": {"express4": "iast/index.js", "express4-typescript": "iast.ts", "express5": "iast/index.js"},
        "python": {"flask-poc": "app.py", "django-poc": "app/urls.py"},
    }

    @bug(context.library < "nodejs@5.3.0", weblog_variant="express4-typescript", reason="APMRP-360")
    def test_insecure(self):
        super().test_insecure()

    @missing_feature(context.library < "java@1.9.0", reason="Metrics not implemented")
    @missing_feature(
        context.weblog_variant in ("fastapi", "flask-poc", "uwsgi-poc", "uds-flask"), reason="Not implemented yet"
    )
    @missing_feature(library="dotnet", reason="Not implemented yet")
    def test_telemetry_metric_instrumented_sink(self):
        super().test_telemetry_metric_instrumented_sink()

    @missing_feature(context.library < "java@1.11.0", reason="Metrics not implemented")
    def test_telemetry_metric_executed_sink(self):
        super().test_telemetry_metric_executed_sink()

    @missing_feature(context.weblog_variant == "jersey-grizzly2", reason="Endpoint responds 500")
    def test_secure(self):
        super().test_secure()


@rfc(
    "https://docs.google.com/document/d/1ga7yCKq2htgcwgQsInYZKktV0hNlv4drY9XzSxT-o5U/edit?tab=t.0#heading=h.d0f5wzmlfhat"
)
@features.iast_stack_trace
class TestSqlInjection_StackTrace:
    """Validate stack trace generation"""

    def setup_stack_trace(self):
        self.r = weblog.post("/iast/sqli/test_insecure", data={"username": "shaquille_oatmeal", "password": "123456"})

    def test_stack_trace(self):
        validate_stack_traces(self.r)


@rfc("https://docs.google.com/document/d/1R8AIuQ9_rMHBPdChCb5jRwPrg1WvIz96c_WQ3y8DWk4")
@features.iast_extended_location
class TestSqlInjection_ExtendedLocation:
    """Test extended location data"""

    vulnerability_type = "SQL_INJECTION"

    def setup_extended_location_data(self):
        self.r = weblog.post("/iast/sqli/test_insecure", data={"username": "shaquille_oatmeal", "password": "123456"})

    def test_extended_location_data(self):
        validate_extended_location_data(self.r, self.vulnerability_type)
