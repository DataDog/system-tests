# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, missing_feature, bug, features
from tests.appsec.iast.utils import BaseSourceTest


@features.iast_source_body
class TestRequestBody(BaseSourceTest):
    """Verify that request json body is tainted"""

    endpoint = "/iast/source/body/test"
    requests_kwargs = [{"method": "POST", "json": {"name": "table", "value": "user"}}]
    source_type = "http.request.body"
    source_names = None
    source_value = None

    @bug(weblog_variant="jersey-grizzly2", reason="APPSEC-56007")
    def test_source_reported(self):
        super().test_source_reported()

    @missing_feature(context.library < "java@1.9.0", reason="Metrics not implemented")
    @missing_feature(
        context.library < "java@1.22.0" and "spring-boot" not in context.weblog_variant,
        reason="Metrics not implemented",
    )
    @bug(context.library >= "java@1.13.0" and context.library < "java@1.17.0", reason="APMRP-360")
    @missing_feature(library="dotnet", reason="Not implemented yet")
    def test_telemetry_metric_instrumented_source(self):
        super().test_telemetry_metric_instrumented_source()

    @missing_feature(context.library < "java@1.17.0", reason="Metrics not implemented")
    @missing_feature(
        context.library < "java@1.22.0" and "spring-boot" not in context.weblog_variant,
        reason="Metrics not implemented",
    )
    @missing_feature(library="dotnet", reason="Not implemented yet")
    def test_telemetry_metric_executed_source(self):
        super().test_telemetry_metric_executed_source()
