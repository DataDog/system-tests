# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import coverage, missing_feature, features
from .._test_iast_fixtures import BaseSinkTest, DetectionStage


@features.iast_sink_hardcoded_secrets
@coverage.basic
class Test_HardcodedSecrets(BaseSinkTest):
    """Test Hardcoded secrets detection."""

    vulnerability_type = "HARDCODED_SECRET"
    http_method = "GET"
    insecure_endpoint = "/iast/hardcoded_secrets/test_insecure"
    secure_endpoint = "/iast/hardcoded_secrets/test_secure"
    data = {}
    location_map = {"nodejs": "iast/index.js"}
    detection_stage = DetectionStage.STARTUP

    @missing_feature(library="nodejs", reason="Not implemented yet")
    def test_telemetry_metric_instrumented_sink(self):
        super().test_telemetry_metric_instrumented_sink()

    @missing_feature(library="nodejs", reason="Not implemented yet")
    def test_telemetry_metric_executed_sink(self):
        super().test_telemetry_metric_executed_sink()
