# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, bug, missing_feature, features
from tests.appsec.iast.utils import BaseSourceTest


@features.iast_source_cookie_name
class TestCookieName(BaseSourceTest):
    """Verify that request cookies are tainted"""

    endpoint = "/iast/source/cookiename/test"
    requests_kwargs = [{"method": "GET", "cookies": {"table": "unused"}}]
    source_type = "http.request.cookie.name"
    source_names = ["table"]
    source_value = "table"

    @missing_feature(library="dotnet", reason="Not implemented")
    @missing_feature(context.library < "java@1.9.0", reason="Metrics not implemented")
    @missing_feature(
        context.library < "java@1.22.0" and "spring-boot" not in context.weblog_variant,
        reason="Metrics not implemented",
    )
    @bug(context.library >= "java@1.16.0" and context.library < "java@1.22.0", reason="APMRP-360")
    @missing_feature(weblog_variant="akka-http", reason="Not working as expected")
    def test_telemetry_metric_instrumented_source(self):
        super().test_telemetry_metric_instrumented_source()

    @missing_feature(context.library < "java@1.22.0", reason="Metrics not implemented")
    @missing_feature(weblog_variant="akka-http", reason="Not working as expected")
    def test_telemetry_metric_executed_source(self):
        super().test_telemetry_metric_executed_source()
