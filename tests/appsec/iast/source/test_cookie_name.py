# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features
from tests.appsec.iast.utils import BaseSourceTest


@features.iast_source_cookie_name
class TestCookieName(BaseSourceTest):
    """Verify that request cookies are tainted"""

    endpoint = "/iast/source/cookiename/test"
    requests_kwargs = [{"method": "GET", "cookies": {"table": "unused"}}]
    source_type = "http.request.cookie.name"
    source_names = ["table"]
    source_value = "table"

    def test_telemetry_metric_instrumented_source(self):
        super().test_telemetry_metric_instrumented_source()

    def test_telemetry_metric_executed_source(self):
        super().test_telemetry_metric_executed_source()
