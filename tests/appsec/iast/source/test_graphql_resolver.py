# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, missing_feature, bug, features, scenarios
from .._test_iast_fixtures import BaseSourceTest


@scenarios.graphql_appsec
@features.iast_graphql_resolver_argument
class TestGraphqlResolverArgument(BaseSourceTest):
    """Verify that graphql resolver argument is tainted in a request"""

    endpoint = "/graphql"
    requests_kwargs = [
        {
            "method": "POST",
            "json": {
                "query": 'query TestInjection { testInjection(path: "filename") { id name }}',
                "operationName": "TestInjection",
            },
        }
    ]
    source_type = "http.request.body"
    source_names = None
    source_value = None

    def test_source_reported(self):
        super().test_source_reported()

    def test_telemetry_metric_instrumented_source(self):
        super().test_telemetry_metric_instrumented_source()

    def test_telemetry_metric_executed_source(self):
        super().test_telemetry_metric_executed_source()
