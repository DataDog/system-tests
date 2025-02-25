# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, missing_feature, bug, features
from tests.appsec.iast.utils import BaseSourceTest


@features.iast_source_request_parameter_name
class TestParameterName(BaseSourceTest):
    """Verify that request parameters are tainted"""

    endpoint = "/iast/source/parametername/test"
    requests_kwargs = [
        {"method": "GET", "params": {"user": "unused"}},
        {"method": "POST", "data": {"user": "unused"}},
    ]
    source_type = "http.request.parameter.name"
    source_names = ["user"]
    source_value = None

    setup_source_post_reported = BaseSourceTest.setup_source_reported

    @missing_feature(
        context.library == "nodejs" and context.weblog_variant in ["express4", "express5"],
        reason="Tainted as request body",
    )
    @bug(weblog_variant="resteasy-netty3", reason="APPSEC-55687")
    @missing_feature(library="dotnet", reason="Tainted as request body")
    def test_source_post_reported(self):
        """For use case where only one is reported, we want to keep a test on the one reported"""
        self.validate_request_reported(self.requests["POST"])

    setup_source_get_reported = BaseSourceTest.setup_source_reported

    @bug(
        context.library < "java@1.40.0" and context.weblog_variant == "jersey-grizzly2",
        reason="APPSEC-55387",
    )
    @bug(weblog_variant="resteasy-netty3", reason="APPSEC-55687")
    def test_source_get_reported(self):
        """For use case where only one is reported, we want to keep a test on the one reported"""
        self.validate_request_reported(self.requests["GET"])

    @missing_feature(
        context.library == "nodejs" and context.weblog_variant in ["express4", "express5"],
        reason="Tainted as request body",
    )
    @bug(
        context.library < "java@1.40.0" and context.weblog_variant == "jersey-grizzly2",
        reason="APPSEC-55387",
    )
    @bug(weblog_variant="resteasy-netty3", reason="APPSEC-55687")
    @missing_feature(library="dotnet", reason="Tainted as request body")
    def test_source_reported(self):
        super().test_source_reported()

    @missing_feature(library="dotnet", reason="Not implemented")
    @missing_feature(context.library < "java@1.16.0", reason="Metrics not implemented")
    @missing_feature(
        context.library < "java@1.22.0" and "spring-boot" not in context.weblog_variant,
        reason="Metrics not implemented",
    )
    @missing_feature(
        context.weblog_variant in ("akka-http", "jersey-grizzly2", "resteasy-netty3", "vertx4"),
        reason="Metrics not implemented",
    )
    def test_telemetry_metric_instrumented_source(self):
        super().test_telemetry_metric_instrumented_source()

    @missing_feature(context.library < "java@1.16.0", reason="Metrics not implemented")
    @missing_feature(
        context.library < "java@1.22.0" and "spring-boot" not in context.weblog_variant,
        reason="Metrics not implemented",
    )
    @missing_feature(
        context.weblog_variant in ("akka-http", "jersey-grizzly2", "resteasy-netty3", "vertx4"),
        reason="Metrics not implemented",
    )
    def test_telemetry_metric_executed_source(self):
        super().test_telemetry_metric_executed_source()
