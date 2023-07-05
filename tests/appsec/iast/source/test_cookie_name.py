# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import pytest
from utils import context, coverage, released, bug
from ..iast_fixtures import SourceFixture

if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@coverage.basic
@released(dotnet="?", golang="?", nodejs="?", php_appsec="?", python="1.17.0", ruby="?")
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
class TestCookieName:
    """Verify that request cookies are tainted"""

    source_fixture = SourceFixture(
        http_method="GET",
        endpoint="/iast/source/cookiename/test",
        request_kwargs={"cookies": {"user": "unused"}},
        source_type="http.request.cookie.name",
        source_name="user",
        source_value="user",
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
