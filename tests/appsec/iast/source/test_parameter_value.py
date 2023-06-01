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
        "spring-boot-wildfly": "1.5.0",
        "spring-boot-undertow": "1.5.0",
        "resteasy-netty3": "1.11.0",
        "jersey-grizzly2": "1.11.0",
        "vertx3": "1.12.0",
        "akka-http": "1.12.0",
        "*": "?",
    }
)
@released(nodejs={"express4": "3.19.0", "*": "?"})
class TestParameterValue:
    """Verify that request parameters are tainted"""

    expected_source_value = "user"
    expected_post_origin = "http.request.parameter"
    if context.library.library == "nodejs":
        expected_post_origin = "http.request.body"
        expected_source_value = None  # In test case in node the value is redacted

    source_post_fixture = SourceFixture(
        http_method="POST",
        endpoint="/iast/source/parameter/test",
        request_kwargs={"data": {"table": "user"}},
        source_type=expected_post_origin,
        source_name="table",
        source_value=expected_source_value,
    )

    def setup_source_post_reported(self):
        self.source_post_fixture.setup()

    @bug(context.weblog_variant == "jersey-grizzly2", reason="name field of source not set")
    def test_source_post_reported(self):
        self.source_post_fixture.test()

    source_get_fixture = SourceFixture(
        http_method="GET",
        endpoint="/iast/source/parameter/test",
        request_kwargs={"params": {"table": "user"}},
        source_type="http.request.parameter",
        source_name="table",
        source_value=expected_source_value,
    )

    def setup_source_get_reported(self):
        self.source_get_fixture.setup()

    @missing_feature(context.library.library == "java", reason="Pending to add GET test")
    def test_source_get_reported(self):
        self.source_get_fixture.test()

    def setup_post_telemetry_metric_instrumented_source(self):
        self.source_post_fixture.setup_telemetry_metric_instrumented_source()

    @missing_feature(context.library < "java@1.13.0", reason="Not implemented")
    @missing_feature(not context.weblog_variant.startswith("spring-boot"), reason="Not implemented")
    @missing_feature(library="nodejs", reason="Not implemented")
    def test_post_telemetry_metric_instrumented_source(self):
        self.source_post_fixture.test_telemetry_metric_instrumented_source()

    def setup_post_telemetry_metric_executed_source(self):
        self.source_post_fixture.setup_telemetry_metric_executed_source()

    @missing_feature(context.library < "java@1.13.0", reason="Not implemented")
    @missing_feature(not context.weblog_variant.startswith("spring-boot"), reason="Not implemented")
    @missing_feature(library="nodejs", reason="Not implemented")
    def test_post_telemetry_metric_executed_source(self):
        self.source_post_fixture.test_telemetry_metric_executed_source()
