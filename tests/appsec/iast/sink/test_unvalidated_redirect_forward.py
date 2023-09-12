# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import pytest
from utils import context, coverage, released, missing_feature, irrelevant
from .._test_iast_fixtures import SinkFixture


def _expected_location():
    if context.library.library == "java":
        if context.weblog_variant.startswith("spring-boot"):
            return "com.datadoghq.system_tests.springboot.AppSecIast"
        if context.weblog_variant == "vertx3":
            return "com.datadoghq.vertx3.iast.routes.IastSinkRouteProvider"
        if context.weblog_variant == "vertx4":
            return "com.datadoghq.vertx4.iast.routes.IastSinkRouteProvider"


@coverage.basic
@released(
    java={"vertx4": "1.17.0", "*": "1.16.0",}
)
@irrelevant(weblog_variant="ratpack", reason="No forward")
@irrelevant(weblog_variant="akka-http", reason="No forward")
@irrelevant(weblog_variant="jersey-grizzly2", reason="No forward")
@irrelevant(weblog_variant="resteasy-netty3", reason="No forward")
@missing_feature(weblog_variant="spring-boot-3-native", reason="GraalVM. Tracing support only")
class TestUnvalidatedForward:
    """Verify Unvalidated redirect forward detection."""

    sink_fixture_forward = SinkFixture(
        vulnerability_type="UNVALIDATED_REDIRECT",
        http_method="POST",
        insecure_endpoint="/iast/unvalidated_redirect/test_insecure_forward",
        secure_endpoint="/iast/unvalidated_redirect/test_secure_forward",
        data={"location": "http://dummy.location.com"},
        location_map=_expected_location,
    )

    def setup_insecure_forward(self):
        self.sink_fixture_forward.setup_insecure()

    @missing_feature(library="java", weblog_variant="resteasy-netty3")
    @missing_feature(library="java", weblog_variant="jersey-grizzly2")
    def test_insecure_forward(self):
        self.sink_fixture_forward.test_insecure()

    def setup_secure_forward(self):
        self.sink_fixture_forward.setup_secure()

    @missing_feature(library="java", weblog_variant="resteasy-netty3")
    @missing_feature(library="java", weblog_variant="jersey-grizzly2")
    def test_secure_forward(self):
        self.sink_fixture_forward.test_secure()
