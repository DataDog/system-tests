# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import pytest
from utils import context, coverage, released, bug, missing_feature
from ..iast_fixtures import SourceFixture

if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@coverage.basic
@released(dotnet="?", golang="?", nodejs="?", php_appsec="?", python="1.18.0", ruby="?")
@released(
    java={
        "jersey-grizzly2": "1.15.0",
        "resteasy-netty3": "?",
        "vertx3": "1.12.0",
        "vertx4": "1.12.0",
        "akka-http": "1.12.0",
        "ratpack": "?",
        "*": "1.5.0",
    }
)
@missing_feature(weblog_variant="spring-boot-3-native", reason="GraalVM. Tracing support only")
class TestHeaderName:
    """Verify that request headers name are tainted"""

    source_name = "user"
    if context.library.library == "python":
        source_name = "User"

    source_fixture = SourceFixture(
        http_method="GET",
        endpoint="/iast/source/headername/test",
        request_kwargs={"headers": {"user": "unused"}},
        source_type="http.request.header.name",
        source_name=source_name,
        source_value=None,
    )

    def setup_source_reported(self):
        self.source_fixture.setup()

    def test_source_reported(self):
        self.source_fixture.test()

    def setup_telemetry_metric_instrumented_source(self):
        self.source_fixture.setup_telemetry_metric_instrumented_source()

    @bug(library="java", reason="Not working as expected")
    def test_telemetry_metric_instrumented_source(self):
        self.source_fixture.test_telemetry_metric_instrumented_source()

    def setup_telemetry_metric_executed_source(self):
        self.source_fixture.setup_telemetry_metric_executed_source()

    @bug(library="java", reason="Not working as expected")
    def test_telemetry_metric_executed_source(self):
        self.source_fixture.test_telemetry_metric_executed_source()
