# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
from utils import context, missing_feature, coverage, flaky
from .._test_iast_fixtures import SinkFixture


@coverage.basic
class TestWeakCipher:
    """Verify weak cipher detection."""

    sink_fixture = SinkFixture(
        vulnerability_type="WEAK_CIPHER",
        http_method="GET",
        insecure_endpoint="/iast/insecure_cipher/test_insecure_algorithm",
        secure_endpoint="/iast/insecure_cipher/test_secure_algorithm",
        data=None,
        location_map={"java": "com.datadoghq.system_tests.iast.utils.CryptoExamples", "nodejs": "iast/index.js",},
        evidence_map={"nodejs": "des-ede-cbc", "java": "Blowfish",},
    )

    def setup_insecure(self):
        self.sink_fixture.setup_insecure()

    def test_insecure(self):
        self.sink_fixture.test_insecure()

    def setup_secure(self):
        self.sink_fixture.setup_secure()

    @flaky(library="python", reason="PATH_TRAVERSAL on Crypto.Cipher.AES is reported, approx 10%")
    def test_secure(self):
        self.sink_fixture.test_secure()

    def setup_telemetry_metric_instrumented_sink(self):
        self.sink_fixture.setup_telemetry_metric_instrumented_sink()

    @missing_feature(context.library < "java@1.13.0", reason="Not implemented yet")
    @missing_feature(library="nodejs", reason="Not implemented yet")
    @missing_feature(library="python", reason="Not implemented yet")
    def test_telemetry_metric_instrumented_sink(self):
        self.sink_fixture.test_telemetry_metric_instrumented_sink()

    def setup_telemetry_metric_executed_sink(self):
        self.sink_fixture.setup_telemetry_metric_executed_sink()

    @missing_feature(context.library < "java@1.13.0", reason="Not implemented yet")
    @missing_feature(library="nodejs", reason="Not implemented yet")
    @missing_feature(library="python", reason="Not implemented yet")
    def test_telemetry_metric_executed_sink(self):
        self.sink_fixture.test_telemetry_metric_executed_sink()
