# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, missing_feature, features, rfc, weblog
from ..utils import BaseSinkTest, validate_stack_traces


@features.iast_sink_insecure_auth_protocol
class Test_InsecureAuthProtocol(BaseSinkTest):
    """Test Insecure Auth Protocol detection."""

    vulnerability_type = "INSECURE_AUTH_PROTOCOL"
    http_method = "GET"
    insecure_endpoint = "/iast/insecure-auth-protocol/test"
    secure_endpoint = "/iast/insecure-auth-protocol/test"
    data = {}
    insecure_headers = {
        "Authorization": 'Digest username="WATERFORD", realm="Users", nonce="c5rcvu346qavqf3hnmsrnqj5up", uri="/api/partner/validate", response="57c8d9f11ec7a2f1ab13c5e166b2c505"'
    }

    @missing_feature(library="java", reason="Not implemented yet")
    @missing_feature(library="dotnet", reason="Not implemented yet")
    def test_telemetry_metric_instrumented_sink(self):
        super().test_telemetry_metric_instrumented_sink()

    @missing_feature(library="java", reason="Not implemented yet")
    def test_telemetry_metric_executed_sink(self):
        super().test_telemetry_metric_executed_sink()


@rfc(
    "https://docs.google.com/document/d/1ga7yCKq2htgcwgQsInYZKktV0hNlv4drY9XzSxT-o5U/edit?tab=t.0#heading=h.d0f5wzmlfhat"
)
@features.iast_stack_trace
class Test_InsecureAuthProtocol_StackTrace:
    """Validate stack trace generation """

    def setup_stack_trace(self):
        self.r = weblog.get(
            "/iast/insecure-auth-protocol/test_insecure",
            headers={
                "Authorization": 'Digest username="WATERFORD", realm="Users", nonce="c5rcvu346qavqf3hnmsrnqj5up", uri="/api/partner/validate", response="57c8d9f11ec7a2f1ab13c5e166b2c505"'
            },
        )

    @missing_feature(library="java", reason="Not implemented yet")
    def test_stack_trace(self):
        validate_stack_traces(self.r)
