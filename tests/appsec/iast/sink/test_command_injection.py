# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, coverage, released, missing_feature
from .._test_iast_fixtures import SinkFixture


@coverage.basic
@released(dotnet="?", golang="?", php_appsec="?", python="?", ruby="?")
@released(
    java={
        "resteasy-netty3": "1.11.0",
        "jersey-grizzly2": "1.11.0",
        "vertx3": "1.12.0",
        "vertx4": "1.12.0",
        "akka-http": "1.12.0",
        "ratpack": "?",
        "*": "1.1.0",
    }
)
@released(nodejs={"express4": "3.11.0", "*": "?"})
@missing_feature(weblog_variant="spring-boot-3-native", reason="GraalVM. Tracing support only")
class TestCommandInjection:
    """Test command injection detection."""

    sink_fixture = SinkFixture(
        vulnerability_type="COMMAND_INJECTION",
        http_method="POST",
        insecure_endpoint="/iast/cmdi/test_insecure",
        secure_endpoint="/iast/cmdi/test_secure",
        data={"cmd": "ls"},
        location_map={"java": "com.datadoghq.system_tests.iast.utils.CmdExamples", "nodejs": "iast/index.js",},
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

    @missing_feature(context.library < "java@1.13.0", reason="Not implemented yet")
    @missing_feature(library="nodejs", reason="Not implemented yet")
    def test_telemetry_metric_instrumented_sink(self):
        self.sink_fixture.test_telemetry_metric_instrumented_sink()

    def setup_telemetry_metric_executed_sink(self):
        self.sink_fixture.setup_telemetry_metric_executed_sink()

    @missing_feature(context.library < "java@1.13.0", reason="Not implemented yet")
    @missing_feature(library="nodejs", reason="Not implemented yet")
    def test_telemetry_metric_executed_sink(self):
        self.sink_fixture.test_telemetry_metric_executed_sink()
