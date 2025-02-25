# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, missing_feature, scenarios, features, rfc, weblog
from tests.appsec.iast.utils import BaseSinkTest, validate_extended_location_data, validate_stack_traces


@scenarios.integrations
@features.iast_sink_mongodb_injection
class TestNoSqlMongodbInjection(BaseSinkTest):
    """Verify NoSQL injection detection in mongodb database."""

    vulnerability_type = "NOSQL_MONGODB_INJECTION"
    http_method = "POST"
    insecure_endpoint = "/iast/mongodb-nosql-injection/test_insecure"
    secure_endpoint = "/iast/mongodb-nosql-injection/test_secure"
    data = {"key": "somevalue"}
    location_map = {
        "nodejs": {"express4": "iast/index.js", "express4-typescript": "iast.ts", "express5": "iast/index.js"}
    }

    @missing_feature(
        context.weblog_variant == "express5", reason="express-mongo-sanitize is not yet compatible with express5"
    )
    def test_secure(self):
        super().test_secure()

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
@scenarios.integrations
@features.iast_stack_trace
class TestNoSqlMongodbInjection_StackTrace:
    """Validate stack trace generation"""

    def setup_stack_trace(self):
        self.r = weblog.post("/iast/mongodb-nosql-injection/test_insecure", data={"key": "somevalue"})

    def test_stack_trace(self):
        validate_stack_traces(self.r)


@rfc("https://docs.google.com/document/d/1R8AIuQ9_rMHBPdChCb5jRwPrg1WvIz96c_WQ3y8DWk4")
@scenarios.integrations
@features.iast_extended_location
class TestNoSqlMongodbInjection_ExtendedLocation:
    """Test extended location data"""

    vulnerability_type = "NOSQL_MONGODB_INJECTION"

    def setup_extended_location_data(self):
        self.r = weblog.post("/iast/mongodb-nosql-injection/test_insecure", data={"key": "somevalue"})

    def test_extended_location_data(self):
        validate_extended_location_data(self.r, self.vulnerability_type)
