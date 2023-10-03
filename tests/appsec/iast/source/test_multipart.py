# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import coverage, weblog, bug
from .._test_iast_fixtures import SourceFixture


@coverage.basic
class TestMultipart:
    """Verify that multipart parameter is tainted"""

    source_fixture = SourceFixture(
        http_method="POST",
        endpoint="/iast/source/multipart/test",
        request_kwargs={"files": {"file1": ("file1", "bsldhkuqwgervf")}},
        source_type="http.request.multipart.parameter",
        source_name="Content-Disposition",
        source_value=None,
    )

    def test_source_reported(self):
        self.source_fixture.test()

    def setup_telemetry_metric_instrumented_source(self):
        self.source_fixture.setup_telemetry_metric_instrumented_source()

    @bug(library="java", reason="Not working as expected")
    def test_telemetry_metric_instrumented_source(self):
        self.source_fixture.test_telemetry_metric_instrumented_source()

    def setup_telemetry_metric_executed_source(self):
        self.source_fixture.setup_telemetry_metric_executed_source()

    @bug(library="java", reason="Not working as expected")
    def test_telemetry_metric_executed_source(self):
        self.source_fixture.test_telemetry_metric_executed_source()
