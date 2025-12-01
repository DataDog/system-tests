# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2025 Datadog, Inc.


from utils import features, missing_feature
from tests.appsec.iast.utils import BaseSinkTest


@features.iast_stack_trace
class TestStackTraceLeak(BaseSinkTest):
    """Test stack trace leak detection."""

    vulnerability_type = "STACKTRACE_LEAK"
    http_method = "GET"
    insecure_endpoint = "/iast/stack_trace_leak/test_insecure"
    secure_endpoint = "/iast/stack_trace_leak/test_secure"

    def test_telemetry_metric_executed_sink(self):
        super().test_telemetry_metric_executed_sink()

    @missing_feature(library="python", reason="Not implemented yet")
    def test_telemetry_metric_instrumented_sink(self):
        super().test_telemetry_metric_instrumented_sink()
