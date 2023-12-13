# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, coverage, bug, missing_feature, features
from .._test_iast_fixtures import BaseSourceTest


@coverage.basic
@features.iast_source_cookie_value
class TestCookieValue(BaseSourceTest):
    """Verify that request cookies are tainted"""

    endpoint = "/iast/source/cookievalue/test"
    requests_kwargs = [{"method": "GET", "cookies": {"table": "user"}}]
    source_type = "http.request.cookie.value"
    source_names = ["table"]
    source_value = "user"

    @bug(context.weblog_variant == "jersey-grizzly2", reason="name field of source not set")
    def test_source_reported(self):
        super().test_source_reported()

    @missing_feature(library="dotnet", reason="Not implemented")
    @bug(library="java", reason="Not working as expected")
    def test_telemetry_metric_instrumented_source(self):
        super().test_telemetry_metric_instrumented_source()

    @bug(library="java", reason="Not working as expected")
    def test_telemetry_metric_executed_source(self):
        super().test_telemetry_metric_executed_source()
