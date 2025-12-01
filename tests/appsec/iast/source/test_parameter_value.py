# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, missing_feature, irrelevant, features, flaky, bug
from tests.appsec.iast.utils import BaseSourceTest


@features.iast_source_request_parameter_value
class TestParameterValue(BaseSourceTest):
    """Verify that request parameters are tainted"""

    endpoint = "/iast/source/parameter/test"
    requests_kwargs = [
        {"method": "GET", "params": {"table": "user"}},
        {"method": "POST", "data": {"table": "user"}},
    ]
    # In test case in node, the value is redacted
    source_value = None if context.library.name == "nodejs" else "user"
    source_type = "http.request.body" if context.library.name in ("nodejs", "dotnet") else "http.request.parameter"
    source_names = ["table"]

    # remove the base test, to handle the source_type spcial use case in node
    @irrelevant()
    def test_source_reported(self): ...

    setup_source_post_reported = BaseSourceTest.setup_source_reported

    @irrelevant(
        library="python",
        reason="Flask and Django need a header; otherwise, they return a 415 status code."
        "TODO: When FastAPI implements POST body source, verify if it does too.",
    )
    @flaky(context.weblog_variant == "resteasy-netty3", reason="APPSEC-56007")
    @bug(context.weblog_variant == "play", reason="APPSEC-58349")
    def test_source_post_reported(self):
        self.validate_request_reported(self.requests["POST"])

    setup_source_get_reported = BaseSourceTest.setup_source_reported

    @bug(context.weblog_variant == "play", reason="APPSEC-58349")
    def test_source_get_reported(self):
        self.validate_request_reported(self.requests["GET"], source_type="http.request.parameter")

    @missing_feature(context.library < "java@1.9.0", reason="Not implemented")
    @missing_feature(
        context.library < "java@1.22.0" and "spring-boot" not in context.weblog_variant,
        reason="Metrics not implemented",
    )
    @missing_feature(library="dotnet", reason="Not implemented")
    def test_telemetry_metric_instrumented_source(self):
        super().test_telemetry_metric_instrumented_source()

    @missing_feature(context.library < "java@1.11.0", reason="Not implemented")
    @missing_feature(
        context.library < "java@1.22.0" and "spring-boot" not in context.weblog_variant,
        reason="Metrics not implemented",
    )
    def test_telemetry_metric_executed_source(self):
        super().test_telemetry_metric_executed_source()
