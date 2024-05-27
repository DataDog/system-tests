# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, missing_feature, features
from ..utils import BaseSinkTest


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
        "nodejs": {"express4": "iast/index.js", "express4-typescript": "iast.ts"},
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
