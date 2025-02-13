# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, missing_feature, features
from tests.appsec.iast.utils import BaseSourceTest


@features.iast_source_cookie_value
class TestCookieValue(BaseSourceTest):
    """Verify that request cookies are tainted"""

    endpoint = "/iast/source/cookievalue/test"
    requests_kwargs = [{"method": "GET", "cookies": {"table": "user"}}]
    source_type = "http.request.cookie.value"
    source_names = ["table"]
    source_value = "user"

    @missing_feature(library="dotnet", reason="Not implemented")
    @missing_feature(context.library < "java@1.17.0", reason="Metrics not implemented")
    @missing_feature(
        context.library < "java@1.22.0" and "spring-boot" not in context.weblog_variant,
        reason="Metrics not implemented",
    )
    def test_telemetry_metric_instrumented_source(self):
        super().test_telemetry_metric_instrumented_source()

    @missing_feature(context.library < "java@1.17.0", reason="Metrics not implemented")
    @missing_feature(
        context.library < "java@1.22.0" and "spring-boot" not in context.weblog_variant,
        reason="Metrics not implemented",
    )
    def test_telemetry_metric_executed_source(self):
        super().test_telemetry_metric_executed_source()
