# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, missing_feature, features
from tests.appsec.iast.utils import BaseSourceTest


@features.iast_source_header_value
class TestHeaderValue(BaseSourceTest):
    """Verify that request headers are tainted"""

    source_name = (
        "HTTP_TABLE" if context.library.name == "python" and context.weblog_variant == "django-poc" else "table"
    )

    endpoint = "/iast/source/header/test"
    requests_kwargs = [{"method": "GET", "headers": {"table": "user"}}]
    source_type = "http.request.header"
    source_value = "user"

    @missing_feature(context.library < "java@1.9.0", reason="Metrics not implemented")
    @missing_feature(library="dotnet", reason="Not implemented")
    def test_telemetry_metric_instrumented_source(self):
        super().test_telemetry_metric_instrumented_source()

    @missing_feature(context.library < "java@1.16.0", reason="Metrics not implemented")
    @missing_feature(
        context.library < "java@1.22.0" and "spring-boot" not in context.weblog_variant,
        reason="Metrics not implemented",
    )
    def test_telemetry_metric_executed_source(self):
        super().test_telemetry_metric_executed_source()
