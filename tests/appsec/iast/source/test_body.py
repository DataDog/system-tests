# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import coverage, missing_feature, bug, features
from .._test_iast_fixtures import BaseSourceTest


@features.iast_source_body
@coverage.basic
class TestRequestBody(BaseSourceTest):
    """Verify that request json body is tainted"""

    endpoint = "/iast/source/body/test"
    requests_kwargs = [{"method": "POST", "json": {"name": "table", "value": "user"}}]
    source_type = "http.request.body"
    source_names = None
    source_value = None

    @bug(weblog_variant="jersey-grizzly2", reason="Not reported")
    @missing_feature(library="python", reason="Not implemented yet")
    def test_source_reported(self):
        super().test_source_reported()

    @missing_feature(library="java", reason="Not implemented yet")
    @missing_feature(library="dotnet", reason="Not implemented yet")
    def test_telemetry_metric_instrumented_source(self):
        super().test_telemetry_metric_instrumented_source()

    @missing_feature(library="java", reason="Not implemented yet")
    @missing_feature(library="dotnet", reason="Not implemented yet")
    def test_telemetry_metric_executed_source(self):
        super().test_telemetry_metric_executed_source()
