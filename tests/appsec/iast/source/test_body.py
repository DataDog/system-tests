# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import coverage, released, missing_feature, bug
from .._test_iast_fixtures import SourceFixture


@coverage.basic
@released(
    java={
        "jersey-grizzly2": "?",
        "resteasy-netty3": "?",
        "vertx3": "1.12.0",
        "vertx4": "1.12.0",
        "akka-http": "1.12.0",
        "ratpack": "?",
        "*": "1.7.0",
    }
)
@missing_feature(weblog_variant="spring-boot-3-native", reason="GraalVM. Tracing support only")
class TestRequestBody:
    """Verify that request json body is tainted"""

    source_fixture = SourceFixture(
        http_method="POST",
        endpoint="/iast/source/body/test",
        request_kwargs={"json": {"name": "table", "value": "user"}},
        source_type="http.request.body",
        source_name=None,
        source_value=None,
    )

    def setup_source_reported(self):
        self.source_fixture.setup()

    @bug(weblog_variant="jersey-grizzly2", reason="Not reported")
    def test_source_reported(self):
        self.source_fixture.test()

    def setup_telemetry_metric_instrumented_source(self):
        self.source_fixture.setup_telemetry_metric_instrumented_source()

    @missing_feature(library="java", reason="Not implemented yet")
    @missing_feature(library="nodejs", reason="Not implemented yet")
    @missing_feature(library="python", reason="Not implemented yet")
    def test_telemetry_metric_instrumented_source(self):
        self.source_fixture.test_telemetry_metric_instrumented_source()

    def setup_telemetry_metric_executed_source(self):
        self.source_fixture.setup_telemetry_metric_executed_source()

    @missing_feature(library="java", reason="Not implemented yet")
    @missing_feature(library="nodejs", reason="Not implemented yet")
    @missing_feature(library="python", reason="Not implemented yet")
    def test_telemetry_metric_executed_source(self):
        self.source_fixture.test_telemetry_metric_executed_source()
