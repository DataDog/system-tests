# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, coverage, bug, missing_feature, features
from .._test_iast_fixtures import BaseSourceTest


@coverage.basic
@features.iast_source_header_value
class TestHeaderValue(BaseSourceTest):
    """Verify that request headers are tainted"""

    source_name = (
        "HTTP_TABLE" if context.library.library == "python" and context.weblog_variant == "django-poc" else "table"
    )

    endpoint = "/iast/source/header/test"
    requests_kwargs = [{"method": "GET", "headers": {"table": "user"}}]
    source_type = "http.request.header"
    source_value = "user"

    @bug(
        context.weblog_variant == "jersey-grizzly2", reason="name field of source not set",
    )
    def test_source_reported(self):
        super().test_source_reported()

    @missing_feature(
        context.library < "java@1.13.0"
        or (context.library.library == "java" and not context.weblog_variant.startswith("spring-boot")),
        reason="Not implemented",
    )
    @missing_feature(library="dotnet", reason="Not implemented")
    def test_telemetry_metric_instrumented_source(self):
        super().test_telemetry_metric_instrumented_source()

    @bug(library="java", reason="Not working as expected")
    def test_telemetry_metric_executed_source(self):
        super().test_telemetry_metric_executed_source()
