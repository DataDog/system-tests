# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, missing_feature, features
from ..utils import BaseSinkTest


@features.iast_sink_path_traversal
class TestPathTraversal(BaseSinkTest):
    """Test path traversal detection."""

    vulnerability_type = "PATH_TRAVERSAL"
    http_method = "POST"
    insecure_endpoint = "/iast/path_traversal/test_insecure"
    secure_endpoint = "/iast/path_traversal/test_secure"
    data = {"path": "/var/log"}
    location_map = {
        "java": "com.datadoghq.system_tests.iast.utils.PathExamples",
        "nodejs": {"express4": "iast/index.js", "express4-typescript": "iast.ts"},
        "python": {"flask-poc": "app.py", "django-poc": "app/urls.py"},
    }

    @missing_feature(context.library < "java@1.9.0", reason="Metrics not implemented")
    @missing_feature(library="dotnet", reason="Not implemented yet")
    def test_telemetry_metric_instrumented_sink(self):
        super().test_telemetry_metric_instrumented_sink()

    @missing_feature(context.library < "java@1.11.0", reason="Metrics not implemented")
    def test_telemetry_metric_executed_sink(self):
        super().test_telemetry_metric_executed_sink()

    @missing_feature(library="java", reason="Endpoint not implemented")
    @missing_feature(library="nodejs", reason="Endpoint not implemented")
    def test_secure(self):
        return super().test_secure()
