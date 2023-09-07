# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import pytest
from utils import context, coverage, released, missing_feature
from .._test_iast_fixtures import SinkFixture


@coverage.basic
@released(java="1.14.0", php_appsec="?", python="?", ruby="?")
@missing_feature(weblog_variant="spring-boot-3-native", reason="GraalVM. Tracing support only")
@missing_feature(weblog_variant="ratpack", reason="No endpoint implemented")
@missing_feature(weblog_variant="akka-http", reason="No endpoint implemented")
@missing_feature(weblog_variant="vertx4", reason="No endpoint implemented")
class TestSSRF:
    """Test ssrf detection."""

    sink_fixture = SinkFixture(
        vulnerability_type="SSRF",
        http_method="POST",
        insecure_endpoint="/iast/ssrf/test_insecure",
        secure_endpoint="/iast/ssrf/test_secure",
        data={"url": "https://www.datadoghq.com"},
        location_map={"java": "com.datadoghq.system_tests.iast.utils.SsrfExamples", "nodejs": "iast/index.js",},
    )

    def setup_insecure(self):
        self.sink_fixture.setup_insecure()

    def test_insecure(self):
        self.sink_fixture.test_insecure()

    def setup_secure(self):
        self.sink_fixture.setup_secure()

    @missing_feature(library="nodejs", reason="Endpoint not implemented")
    def test_secure(self):
        self.sink_fixture.test_secure()

    def setup_telemetry_metric_instrumented_sink(self):
        self.sink_fixture.setup_telemetry_metric_instrumented_sink()

    def test_telemetry_metric_instrumented_sink(self):
        self.sink_fixture.test_telemetry_metric_instrumented_sink()

    def setup_telemetry_metric_executed_sink(self):
        self.sink_fixture.setup_telemetry_metric_executed_sink()

    def test_telemetry_metric_executed_sink(self):
        self.sink_fixture.test_telemetry_metric_executed_sink()
