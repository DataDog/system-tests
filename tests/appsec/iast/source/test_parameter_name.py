# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import pytest
from utils import context, coverage, missing_feature, released, bug
from ..iast_fixtures import SourceFixture

if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@coverage.basic
@released(dotnet="?", golang="?", php_appsec="?", python="?", ruby="?")
@released(
    java={
        "spring-boot": "1.5.0",
        "spring-boot-jetty": "1.5.0",
        "spring-boot-openliberty": "1.5.0",
        "spring-boot-payara": "1.5.0",
        "spring-boot-wildfly": "1.5.0",
        "spring-boot-undertow": "1.5.0",
        "vertx3": "1.12.0",
        "akka-http": "1.12.0",
        "*": "?",
    }
)
@released(nodejs="?")
class TestParameterName:
    """Verify that request parameters are tainted"""

    source_post_fixture = SourceFixture(
        http_method="POST",
        endpoint="/iast/source/parametername/test",
        request_kwargs={"data": {"user": "unused"}},
        source_type="http.request.parameter.name",
        source_name="user",
        source_value=None,
    )

    def setup_source_post_reported(self):
        self.source_post_fixture.setup()

    @missing_feature(context.weblog_variant == "express4", reason="Tainted as request body")
    def test_source_post_reported(self):
        self.source_post_fixture.test()

    source_get_fixture = SourceFixture(
        http_method="GET",
        endpoint="/iast/source/parametername/test",
        request_kwargs={"params": {"user": "unused"}},
        source_type="http.request.parameter.name",
        source_name="user",
        source_value=None,
    )

    def setup_source_get_reported(self):
        self.source_get_fixture.setup()

    @missing_feature(context.library.library == "java", reason="Pending to add GET test")
    def test_source_get_reported(self):
        self.source_get_fixture.test()

    def setup_post_telemetry_metric_instrumented_source(self):
        self.source_post_fixture.setup_telemetry_metric_instrumented_source()

    @bug(library="java", reason="Not working as expected")
    def test_post_telemetry_metric_instrumented_source(self):
        self.source_post_fixture.test_telemetry_metric_instrumented_source()

    def setup_post_telemetry_metric_executed_source(self):
        self.source_post_fixture.setup_telemetry_metric_executed_source()

    @bug(library="java", reason="Not working as expected")
    def test_post_telemetry_metric_executed_source(self):
        self.source_post_fixture.test_telemetry_metric_executed_source()

    def setup_get_telemetry_metric_instrumented_source(self):
        self.source_get_fixture.setup_telemetry_metric_instrumented_source()

    @bug(library="java", reason="Not working as expected")
    def test_get_telemetry_metric_instrumented_source(self):
        self.source_get_fixture.test_telemetry_metric_instrumented_source()

    def setup_get_telemetry_metric_executed_source(self):
        self.source_get_fixture.setup_telemetry_metric_executed_source()

    @bug(library="java", reason="Not working as expected")
    def test_get_telemetry_metric_executed_source(self):
        self.source_get_fixture.test_telemetry_metric_executed_source()
