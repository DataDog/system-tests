# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, coverage, features
from .._test_iast_fixtures import BaseSinkTestWithoutTelemetry


def _expected_location():
    if context.library.library == "java":
        if context.weblog_variant.startswith("spring-boot"):
            return "com.datadoghq.system_tests.springboot.AppSecIast"
        if context.weblog_variant == "vertx3":
            return "com.datadoghq.vertx3.iast.routes.IastSinkRouteProvider"
        if context.weblog_variant == "vertx4":
            return "com.datadoghq.vertx4.iast.routes.IastSinkRouteProvider"


@features.iast_sink_unvalidatedforward
@coverage.basic
class TestUnvalidatedForward(BaseSinkTestWithoutTelemetry):
    """Verify Unvalidated redirect forward detection."""

    vulnerability_type = "UNVALIDATED_REDIRECT"
    http_method = "POST"
    insecure_endpoint = "/iast/unvalidated_redirect/test_insecure_forward"
    secure_endpoint = "/iast/unvalidated_redirect/test_secure_forward"
    data = {"location": "http://dummy.location.com"}
    location_map = _expected_location()
