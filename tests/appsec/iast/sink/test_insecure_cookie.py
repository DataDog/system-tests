# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, coverage, missing_feature, bug, weblog, features
from .._test_iast_fixtures import BaseSinkTest


@features.iast_sink_insecure_cookie
@coverage.basic
class TestInsecureCookie(BaseSinkTest):
    """Test insecure cookie detection."""

    vulnerability_type = "INSECURE_COOKIE"
    http_method = "GET"
    insecure_endpoint = "/iast/insecure-cookie/test_insecure"
    secure_endpoint = "/iast/insecure-cookie/test_secure"
    data = {}
    location_map = {
        "nodejs": {"express4": "iast/index.js", "express4-typescript": "dist/iast.js"}
    }

    @bug(context.library < "java@1.18.3", reason="Incorrect handling of HttpOnly flag")
    def test_secure(self):
        super().test_secure()

    def setup_empty_cookie(self):
        self.request_empty_cookie = weblog.get("/iast/insecure-cookie/test_empty_cookie", data={})

    def test_empty_cookie(self):
        self.assert_no_iast_event(self.request_empty_cookie)

    @missing_feature(context.library < "java@1.22.0", reason="Metrics not implemented")
    @missing_feature(library="python", reason="Metrics not implemented")
    @missing_feature(library="dotnet", reason="Metrics not implemented")
    def test_telemetry_metric_instrumented_sink(self):
        super().test_telemetry_metric_instrumented_sink()

    @missing_feature(context.library < "java@1.22.0", reason="Metrics not implemented")
    @missing_feature(weblog_variant="vertx4", reason="Metrics not implemented")
    def test_telemetry_metric_executed_sink(self):
        super().test_telemetry_metric_executed_sink()
