# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, coverage, missing_feature, bug, features
from .._test_iast_fixtures import BaseSourceTest


@coverage.basic
@features.iast_source_request_parameter_value
class TestParameterValue(BaseSourceTest):
    """Verify that request parameters are tainted"""

    endpoint = "/iast/source/parameter/test"
    requests_kwargs = [
        {"method": "GET", "params": {"table": "user"}},
        {"method": "POST", "data": {"table": "user"}},
    ]
    # In test case in node, the value is redacted
    source_value = None if context.library.library == "nodejs" else "user"
    source_type = (
        "http.request.body"
        if context.library.library == "nodejs" or context.library.library == "dotnet"
        else "http.request.parameter"
    )
    source_names = ["table"]

    def test_source_reported(self):
        # overwrite the base test, to handle the source_type spcial use case in node
        ...

    setup_source_post_reported = BaseSourceTest.setup_source_reported

    @bug(weblog_variant="jersey-grizzly2", reason="name field of source not set")
    @bug(
        library="python", reason="Python frameworks need a header, if not, 415 status code",
    )
    def test_source_post_reported(self):
        self.validate_request_reported(self.requests["POST"])

    setup_source_get_reported = BaseSourceTest.setup_source_reported

    @bug(weblog_variant="jersey-grizzly2", reason="name field of source not set")
    def test_source_get_reported(self):
        self.validate_request_reported(self.requests["GET"], source_type="http.request.parameter")

    @missing_feature(context.library < "java@1.13.0", reason="Not implemented")
    @missing_feature(
        context.library == "java" and not context.weblog_variant.startswith("spring-boot"), reason="Not implemented",
    )
    @missing_feature(library="dotnet", reason="Not implemented")
    def test_telemetry_metric_instrumented_source(self):
        super().test_telemetry_metric_instrumented_source()

    @missing_feature(context.library < "java@1.13.0", reason="Not implemented")
    @missing_feature(
        context.library == "java" and not context.weblog_variant.startswith("spring-boot"), reason="Not implemented",
    )
    def test_telemetry_metric_executed_source(self):
        super().test_telemetry_metric_executed_source()
