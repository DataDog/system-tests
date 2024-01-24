# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import coverage, missing_feature, features
from .._test_iast_fixtures import BaseSinkTest


@features.iast_sink_ssrf
@coverage.basic
class TestSSRF(BaseSinkTest):
    """Test ssrf detection."""

    vulnerability_type = "SSRF"
    http_method = "POST"
    insecure_endpoint = "/iast/ssrf/test_insecure"
    secure_endpoint = "/iast/ssrf/test_secure"
    data = {"url": "https://www.datadoghq.com"}
    location_map = {
        "java": "com.datadoghq.system_tests.iast.utils.SsrfExamples",
        "nodejs": {"express4": "iast/index.js", "express4-typescript": "dist/iast.js"},
        "python": {"flask-poc": "app.py", "django-poc": "app/urls.py"},
    }

    @missing_feature(library="nodejs", reason="Endpoint not implemented")
    def test_secure(self):
        super().test_secure()

    @missing_feature(library="python", reason="Endpoint not implemented")
    @missing_feature(library="dotnet", reason="Not implemented yet")
    def test_telemetry_metric_instrumented_sink(self):
        super().test_telemetry_metric_instrumented_sink()
