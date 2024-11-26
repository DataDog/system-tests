# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
from utils import context, missing_feature, flaky, features, weblog, rfc
from ..utils import BaseSinkTest, validate_stack_traces


@features.weak_cipher_detection
class TestWeakCipher(BaseSinkTest):
    """Verify weak cipher detection."""

    vulnerability_type = "WEAK_CIPHER"
    http_method = "GET"
    insecure_endpoint = "/iast/insecure_cipher/test_insecure_algorithm"
    secure_endpoint = "/iast/insecure_cipher/test_secure_algorithm"
    data = None
    location_map = {
        "java": "com.datadoghq.system_tests.iast.utils.CryptoExamples",
        "nodejs": {"express4": "iast/index.js", "express4-typescript": "iast.ts"},
    }
    evidence_map = {"nodejs": "des-ede-cbc", "java": "Blowfish"}

    @flaky(context.library == "dotnet@3.3.1", reason="APMRP-360")
    def test_secure(self):
        super().test_secure()

    @missing_feature(context.library < "java@1.9.0", reason="Metrics not implemented")
    @missing_feature(library="dotnet", reason="Not implemented yet")
    def test_telemetry_metric_instrumented_sink(self):
        super().test_telemetry_metric_instrumented_sink()

    @missing_feature(context.library < "java@1.11.0", reason="Metrics not implemented")
    def test_telemetry_metric_executed_sink(self):
        super().test_telemetry_metric_executed_sink()


@rfc(
    "https://docs.google.com/document/d/1ga7yCKq2htgcwgQsInYZKktV0hNlv4drY9XzSxT-o5U/edit?tab=t.0#heading=h.d0f5wzmlfhat"
)
@features.iast_stack_trace
class TestWeakCipher_StackTrace:
    """Validate stack trace generation """

    def setup_stack_trace(self):
        self.r = weblog.get("/iast/insecure_cipher/test_insecure_algorithm")

    def test_stack_trace(self):
        validate_stack_traces(self.r)
