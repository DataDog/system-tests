# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, missing_feature, features
from tests.appsec.iast.utils import BaseSourceTest


@features.iast_source_header_name
class TestHeaderName(BaseSourceTest):
    """Verify that request headers name are tainted"""

    source_name = "User" if context.library.name == "python" else "user"

    endpoint = "/iast/source/headername/test"
    requests_kwargs = [{"method": "GET", "headers": {"user": "unused"}}]
    source_type = "http.request.header.name"
    source_value = None

    @missing_feature(context.library < "java@1.16.0", reason="Not working as expected")
    @missing_feature(
        context.library < "java@1.22.0" and "spring-boot" not in context.weblog_variant,
        reason="Metrics not implemented",
    )
    @missing_feature(context.weblog_variant in ("jersey-grizzly2", "vertx4"), reason="Metrics not implemented")
    def test_telemetry_metric_instrumented_source(self):
        super().test_telemetry_metric_instrumented_source()

    @missing_feature(context.library < "java@1.16.0", reason="Not working as expected")
    @missing_feature(
        context.library < "java@1.22.0" and "spring-boot" not in context.weblog_variant,
        reason="Metrics not implemented",
    )
    @missing_feature(context.weblog_variant in ("jersey-grizzly2", "vertx4"), reason="Metrics not implemented")
    def test_telemetry_metric_executed_source(self):
        super().test_telemetry_metric_executed_source()
