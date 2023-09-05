# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, coverage, missing_feature, released, bug
from .._test_iast_fixtures import SourceFixture


@coverage.basic
@released(dotnet="?", php_appsec="?", ruby="?")
@released(
    java={
        "jersey-grizzly2": "1.15.0",
        "vertx3": "1.12.0",
        "vertx4": "1.12.0",
        "akka-http": "1.12.0",
        "ratpack": "?",
        "*": "1.5.0",
    }
)
@released(python={"flask-poc": "?", "uwsgi-poc": "?", "django-poc": "1.18.0", "uds-flask": "?"})
@missing_feature(weblog_variant="spring-boot-3-native", reason="GraalVM. Tracing support only")
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

    @missing_feature(weblog_variant="express4", reason="Tainted as request body")
    @bug(weblog_variant="resteasy-netty3", reason="Not reported")
    @bug(library="python", reason="Python frameworks need a header, if not, 415 status code")
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

    @bug(weblog_variant="jersey-grizzly2", reason="Not reported")
    @bug(weblog_variant="resteasy-netty3", reason="Not reported")
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
