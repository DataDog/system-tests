# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, coverage, bug, missing_feature
from .._test_iast_fixtures import SourceFixture


@coverage.basic
class TestHeaderValue:
    """Verify that request headers are tainted"""

    source_name = "table"
    if context.library.library == "python" and context.weblog_variant == "django-poc":
        source_name = "HTTP_TABLE"

    source_fixture = SourceFixture(
        http_method="GET",
        endpoint="/iast/source/header/test",
        request_kwargs={"headers": {"table": "user"}},
        source_type="http.request.header",
        source_name=source_name,
        source_value="user",
    )

    def setup_source_reported(self):
        self.source_fixture.setup()

    @bug(context.weblog_variant == "jersey-grizzly2", reason="name field of source not set")
    def test_source_reported(self):
        self.source_fixture.test()

    def setup_telemetry_metric_instrumented_source(self):
        self.source_fixture.setup_telemetry_metric_instrumented_source()

    @missing_feature(
        context.library < "java@1.13.0"
        or (context.library.library == "java" and not context.weblog_variant.startswith("spring-boot")),
        reason="Not implemented",
    )
    def test_telemetry_metric_instrumented_source(self):
        self.source_fixture.test_telemetry_metric_instrumented_source()

    def setup_telemetry_metric_executed_source(self):
        self.source_fixture.setup_telemetry_metric_executed_source()

    @bug(library="java", reason="Not working as expected")
    def test_telemetry_metric_executed_source(self):
        self.source_fixture.test_telemetry_metric_executed_source()
