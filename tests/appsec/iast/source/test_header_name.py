# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, coverage, bug
from .._test_iast_fixtures import BaseSourceTest


@coverage.basic
class TestHeaderName(BaseSourceTest):
    """Verify that request headers name are tainted"""

    source_name = "User" if context.library.library == "python" else "user"

    endpoint = "/iast/source/headername/test"
    requests_kwargs = [{"method": "GET", "headers": {"user": "unused"}}]
    source_type = "http.request.header.name"
    source_value = None

    @bug(library="nodejs", reason="not reported correctly")
    def test_source_reported(self):
        super().test_source_reported()

    @bug(library="java", reason="Not working as expected")
    def test_telemetry_metric_instrumented_source(self):
        super().test_telemetry_metric_instrumented_source()

    @bug(library="java", reason="Not working as expected")
    def test_telemetry_metric_executed_source(self):
        super().test_telemetry_metric_executed_source()
