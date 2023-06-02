# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
import pytest
from utils import context, missing_feature, coverage, released
from ..iast_fixtures import SinkFixture

if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@coverage.basic
@released(dotnet="?", golang="?", php_appsec="?", python="1.7.0", ruby="?")
@released(nodejs={"express4": "3.6.0", "*": "?"})
@released(
    java={
        "spring-boot": "0.108.0",
        "spring-boot-jetty": "0.108.0",
        "spring-boot-openliberty": "0.108.0",
        "spring-boot-wildfly": "0.108.0",
        "spring-boot-udertow": "0.108.0",
        "resteasy-netty3": "1.11.0",
        "jersey-grizzly2": "1.11.0",
        "vertx3": "1.12.0",
        "akka-http": "1.12.0",
        "*": "?",
    },
)
@missing_feature(context.weblog_variant == "spring-boot-3-native", reason="GraalVM. Tracing support only")
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

    def test_secure(self):
        self.sink_fixture.test_secure()

    def setup_telemetry_metric_instrumented_sink(self):
        self.sink_fixture.setup_telemetry_metric_instrumented_sink()

    @released(dotnet="?", golang="?", java="1.13.0", nodejs="?", php_appsec="?", python="?", ruby="?")
    @missing_feature(context.weblog_variant == "spring-boot-3-native", reason="GraalVM. Tracing support only")
    def test_telemetry_metric_instrumented_sink(self):
        self.sink_fixture.test_telemetry_metric_instrumented_sink()

    def setup_telemetry_metric_executed_sink(self):
        self.sink_fixture.setup_telemetry_metric_executed_sink()

    @released(dotnet="?", golang="?", java="1.13.0", nodejs="?", php_appsec="?", python="?", ruby="?")
    @missing_feature(context.weblog_variant == "spring-boot-3-native", reason="GraalVM. Tracing support only")
    def test_telemetry_metric_executed_sink(self):
        self.sink_fixture.test_telemetry_metric_executed_sink()
