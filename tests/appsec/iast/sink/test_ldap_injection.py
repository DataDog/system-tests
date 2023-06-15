# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import pytest
from utils import context, coverage, released, missing_feature
from ..iast_fixtures import SinkFixture

if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@coverage.basic
@released(dotnet="?", golang="?", nodejs="?", php_appsec="?", python="?", ruby="?")
@released(
    java={
        "spring-boot": "1.7.0",
        "spring-boot-jetty": "1.7.0",
        "spring-boot-openliberty": "1.7.0",
        "spring-boot-wildfly": "1.7.0",
        "spring-boot-undertow": "1.7.0",
        "resteasy-netty3": "1.11.0",
        "jersey-grizzly2": "1.11.0",
        "vertx3": "1.12.0",
        "akka-http": "1.12.0",
        "*": "?",
    }
)
@missing_feature(context.weblog_variant == "spring-boot-3-native", reason="GraalVM. Tracing support only")
class TestLDAPInjection:
    """Test LDAP injection detection."""

    sink_fixture = SinkFixture(
        vulnerability_type="LDAP_INJECTION",
        http_method="POST",
        insecure_endpoint="/iast/ldapi/test_insecure",
        secure_endpoint="/iast/ldapi/test_secure",
        data={"username": "ssam", "password": "sammy"},
        location_map={"java": "com.datadoghq.system_tests.iast.utils.LDAPExamples",},
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

    @missing_feature(context.library < "java@1.13.0", reason="Not implemented yet")
    @missing_feature(context.weblog_variant == "spring-boot-3-native", reason="GraalVM. Tracing support only")
    def test_telemetry_metric_instrumented_sink(self):
        self.sink_fixture.test_telemetry_metric_instrumented_sink()

    def setup_telemetry_metric_executed_sink(self):
        self.sink_fixture.setup_telemetry_metric_executed_sink()

    @missing_feature(context.library < "java@1.13.0", reason="Not implemented yet")
    @missing_feature(context.weblog_variant == "spring-boot-3-native", reason="GraalVM. Tracing support only")
    def test_telemetry_metric_executed_sink(self):
        self.sink_fixture.test_telemetry_metric_executed_sink()
