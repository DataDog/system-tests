# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, coverage, missing_feature
from .._test_iast_fixtures import BaseSinkTest


@coverage.basic
class TestLDAPInjection(BaseSinkTest):
    """Test LDAP injection detection."""

    vulnerability_type = "LDAP_INJECTION"
    http_method = "POST"
    insecure_endpoint = "/iast/ldapi/test_insecure"
    secure_endpoint = "/iast/ldapi/test_secure"
    data = {"username": "ssam", "password": "sammy"}
    location_map = {
        "java": "com.datadoghq.system_tests.iast.utils.LDAPExamples",
        "nodejs": "iast/index.js",
    }

    @missing_feature(context.library < "java@1.13.0", reason="Not implemented yet")
    @missing_feature(library="dotnet", reason="Not implemented yet")
    def test_telemetry_metric_instrumented_sink(self):
        super().test_telemetry_metric_instrumented_sink()

    @missing_feature(context.library < "java@1.13.0", reason="Not implemented yet")
    def test_telemetry_metric_executed_sink(self):
        super().test_telemetry_metric_executed_sink()
