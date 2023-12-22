# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, coverage, missing_feature, features
from .._test_iast_fixtures import BaseSinkTest


@coverage.basic
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
        "nodejs": "iast/index.js",
        "python": {"flask-poc": "app.py", "django-poc": "app/urls.py"},
    }

    @missing_feature(context.library < "java@1.13.0", reason="Not implemented yet")
    @missing_feature(library="nodejs", reason="Not implemented yet")
    @missing_feature(library="python", reason="Not implemented yet")
    @missing_feature(library="dotnet", reason="Not implemented yet")
    def test_telemetry_metric_instrumented_sink(self):
        super().test_telemetry_metric_instrumented_sink()

    @missing_feature(context.library < "java@1.13.0", reason="Not implemented yet")
    @missing_feature(library="nodejs", reason="Not implemented yet")
    def test_telemetry_metric_executed_sink(self):
        super().test_telemetry_metric_executed_sink()
