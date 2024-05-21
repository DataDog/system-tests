# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, missing_feature, features
from ..utils import BaseSinkTest


@features.iast_sink_insecure_auth_protocol
class Test_InsecureAuthProtocol(BaseSinkTest):
    """Test Insecure Auth Protocol detection."""

    vulnerability_type = "INSECURE_AUTH_PROTOCOL"
    http_method = "GET"
    insecure_endpoint = "/iast/insecure-auth-protocol/test"
    secure_endpoint = "/iast/insecure-auth-protocol/test"
    data = {}
    insecure_headers = {"Authorization": "Basic dGVzd"}

    @missing_feature(library="java", reason="Not implemented yet")
    @missing_feature(library="dotnet", reason="Not implemented yet")
    def test_telemetry_metric_instrumented_sink(self):
        super().test_telemetry_metric_instrumented_sink()

    @missing_feature(library="java", reason="Not implemented yet")
    def test_telemetry_metric_executed_sink(self):
        super().test_telemetry_metric_executed_sink()
