# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, missing_feature, features, bug
from ..utils import BaseSinkTest


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
        "nodejs": {"express4": "iast/index.js", "express4-typescript": "iast.ts"},
        "python": {"flask-poc": "app.py", "django-poc": "app/urls.py"},
    }

    @bug(
        context.library < "nodejs@5.3.0",
        weblog_variant="express4-typescript",
        reason="Incorrect vulnerability location",
    )
    def test_insecure(self):
        super().test_insecure()

    @missing_feature(context.library < "java@1.9.0", reason="Metrics not implemented")
    @missing_feature(library="python", reason="Not implemented yet")
    @missing_feature(library="dotnet", reason="Not implemented yet")
    def test_telemetry_metric_instrumented_sink(self):
        super().test_telemetry_metric_instrumented_sink()

    @missing_feature(context.library < "java@1.11.0", reason="Metrics not implemented")
    def test_telemetry_metric_executed_sink(self):
        super().test_telemetry_metric_executed_sink()

    @missing_feature(library="python", reason="Endpoint responds 500")
    @missing_feature(context.weblog_variant == "jersey-grizzly2", reason="Endpoint responds 500")
    def test_secure(self):
        super().test_secure()
