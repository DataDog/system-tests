# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, coverage, irrelevant, features, missing_feature
from .._test_iast_fixtures import BaseSinkTest


def _expected_location():
    if context.library.library == "nodejs":
        return "iast/index.js"


@features.iast_sink_header_injection
@coverage.basic
class TestHeaderInjection(BaseSinkTest):
    """Verify Header injection detection"""

    vulnerability_type = "HEADER_INJECTION"
    http_method = "POST"
    insecure_endpoint = "/iast/header_injection/test_insecure"
    secure_endpoint = "/iast/header_injection/test_secure"
    data = {"test": "dummyvalue"}
    location_map = _expected_location()

    @missing_feature(context.library < "java@1.22.0", reason="Metrics not implemented")
    def test_telemetry_metric_instrumented_sink(self):
        super().test_telemetry_metric_instrumented_sink()

    @missing_feature(context.library < "java@1.22.0", reason="Metrics not implemented")
    def test_telemetry_metric_executed_sink(self):
        super().test_telemetry_metric_executed_sink()
