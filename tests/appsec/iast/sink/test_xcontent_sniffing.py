# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, missing_feature, features
from .._test_iast_fixtures import BaseSinkTest


@features.iast_sink_xcontentsniffing
class Test_XContentSniffing(BaseSinkTest):
    """Test missing X-Content-Options header detection."""

    vulnerability_type = "XCONTENTTYPE_HEADER_MISSING"
    http_method = "GET"
    insecure_endpoint = "/iast/xcontent-missing-header/test_insecure"
    secure_endpoint = "/iast/xcontent-missing-header/test_secure"
    data = {}

    @missing_feature(context.library < "java@1.22.0", reason="Metrics not implemented")
    def test_telemetry_metric_instrumented_sink(self):
        super().test_telemetry_metric_instrumented_sink()

    @missing_feature(context.library < "java@1.22.0", reason="Metrics not implemented")
    def test_telemetry_metric_executed_sink(self):
        super().test_telemetry_metric_executed_sink()
