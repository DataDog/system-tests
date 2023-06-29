# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import pytest
from utils import context, coverage, released, missing_feature, bug
from ..iast_fixtures import SinkFixture

if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@coverage.basic
@released(dotnet="?", golang="?", php_appsec="?", ruby="?")
@released(
    python={"django-poc": "1.12.0", "flask-poc": "1.12.0", "uds-flask": "?", "uwsgi-poc": "?", "pylons": "?",}
)
@released(
    java={
        "spring-boot": "1.1.0",
        "spring-boot-jetty": "1.1.0",
        "spring-boot-openliberty": "1.1.0",
        "spring-boot-payara": "1.1.0",
        "spring-boot-wildfly": "1.1.0",
        "spring-boot-undertow": "1.1.0",
        "resteasy-netty3": "1.11.0",
        "jersey-grizzly2": "1.11.0",
        "vertx3": "1.12.0",
        "*": "?",
    }
)
@released(nodejs={"express4": "3.11.0", "*": "?"})
class TestSqlInjection:
    """Verify SQL injection detection."""

    sink_fixture = SinkFixture(
        vulnerability_type="SQL_INJECTION",
        http_method="POST",
        insecure_endpoint="/iast/sqli/test_insecure",
        secure_endpoint="/iast/sqli/test_secure",
        data={"username": "shaquille_oatmeal", "password": "123456"},
        location_map={
            "java": "com.datadoghq.system_tests.iast.utils.SqlExamples",
            "nodejs": "iast/index.js",
            "python": {"flask-poc": "app.py", "django-poc": "app/urls.py"},
        },
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
    @missing_feature(library="nodejs", reason="Not implemented yet")
    @missing_feature(library="python", reason="Not implemented yet")
    @missing_feature(context.weblog_variant == "spring-boot-3-native", reason="GraalVM. Tracing support only")
    def test_telemetry_metric_instrumented_sink(self):
        self.sink_fixture.test_telemetry_metric_instrumented_sink()

    def setup_telemetry_metric_executed_sink(self):
        self.sink_fixture.setup_telemetry_metric_executed_sink()

    @missing_feature(context.library < "java@1.13.0", reason="Not implemented yet")
    @missing_feature(library="nodejs", reason="Not implemented yet")
    @missing_feature(library="python", reason="Not implemented yet")
    @missing_feature(context.weblog_variant == "spring-boot-3-native", reason="GraalVM. Tracing support only")
    def test_telemetry_metric_executed_sink(self):
        self.sink_fixture.test_telemetry_metric_executed_sink()
