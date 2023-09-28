# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import bug, context, coverage, missing_feature, weblog
from .._test_iast_fixtures import SinkFixture


@coverage.basic
class Test_HstsMissingHeader:
    """Test HSTS missing header detection."""

    sink_fixture = SinkFixture(
        vulnerability_type="HSTS_HEADER_MISSING",
        http_method="GET",
        insecure_endpoint="/iast/hstsmissing/test_insecure",
        secure_endpoint="/iast/hstsmissing/test_secure",
        location_map={"nodejs": "iast/index.js",},
        data={},
    )

    def setup_insecure(self):
        self.sink_fixture.insecure_request = weblog.request(
            method=self.sink_fixture.http_method,
            path=self.sink_fixture.insecure_endpoint,
            data=self.sink_fixture.data,
            headers={"X-Forwarded-Proto": "https"},
        )

    def test_insecure(self):
        self.sink_fixture.test_insecure()

    @bug(library="java", reason="Unrelated bug interferes with this test APPSEC-11353")
    def setup_secure(self):
        self.sink_fixture.secure_request = weblog.request(
            method=self.sink_fixture.http_method,
            path=self.sink_fixture.secure_endpoint,
            data=self.sink_fixture.data,
            headers={"X-Forwarded-Proto": "https"},
        )

    def test_secure(self):
        self.sink_fixture.test_secure()

    def setup_telemetry_metric_instrumented_sink(self):
        self.sink_fixture.setup_telemetry_metric_instrumented_sink()

    @missing_feature(library="nodejs", reason="Metrics implemented")
    @missing_feature(library="java", reason="Metrics implemented")
    def test_telemetry_metric_instrumented_sink(self):
        self.sink_fixture.test_telemetry_metric_instrumented_sink()

    def setup_telemetry_metric_executed_sink(self):
        self.sink_fixture.setup_telemetry_metric_executed_sink()

    @missing_feature(library="nodejs", reason="Metrics implemented")
    @missing_feature(library="java", reason="Metrics implemented")
    def test_telemetry_metric_executed_sink(self):
        self.sink_fixture.test_telemetry_metric_executed_sink()
