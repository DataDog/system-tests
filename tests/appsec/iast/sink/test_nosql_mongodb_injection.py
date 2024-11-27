# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, missing_feature, scenarios, features, rfc, weblog
from ..utils import BaseSinkTest, validate_stack_traces


@scenarios.integrations
@features.iast_sink_mongodb_injection
class TestNoSqlMongodbInjection(BaseSinkTest):
    """Verify NoSQL injection detection in mongodb database."""

    vulnerability_type = "NOSQL_MONGODB_INJECTION"
    http_method = "POST"
    insecure_endpoint = "/iast/mongodb-nosql-injection/test_insecure"
    secure_endpoint = "/iast/mongodb-nosql-injection/test_secure"
    data = {"key": "somevalue"}
    location_map = {"nodejs": {"express4": "iast/index.js", "express5": "iast/index.js", "express4-typescript": "iast.ts"}}

    @missing_feature(context.library < "java@1.13.0", reason="Not implemented yet")
    @missing_feature(library="python", reason="Not implemented yet")
    @missing_feature(library="dotnet", reason="Not implemented yet")
    def test_telemetry_metric_instrumented_sink(self):
        super().test_telemetry_metric_instrumented_sink()

    @missing_feature(context.library < "java@1.13.0", reason="Not implemented yet")
    @missing_feature(library="python", reason="Not implemented yet")
    def test_telemetry_metric_executed_sink(self):
        super().test_telemetry_metric_executed_sink()


@rfc(
    "https://docs.google.com/document/d/1ga7yCKq2htgcwgQsInYZKktV0hNlv4drY9XzSxT-o5U/edit?tab=t.0#heading=h.d0f5wzmlfhat"
)
@features.iast_stack_trace
class TestNoSqlMongodbInjection_StackTrace:
    """Validate stack trace generation """

    def setup_stack_trace(self):
        self.r = weblog.post("/iast/mongodb-nosql-injection/test_insecure", data={"key": "somevalue"})

    def test_stack_trace(self):
        validate_stack_traces(self.r)
