# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Test format specifications"""

from utils import weblog, interfaces, bug, irrelevant, context, scenarios


@scenarios.all_endtoend_scenarios
class Test_library:
    """Libraries's payload are valid regarding schemas"""

    def setup_library_schema_full(self):
        # send some requests to be sure to trigger events
        weblog.get("/waf", params={"key": "\n :"})

    def test_library_schema_full(self):
        interfaces.library.assert_schema_points(
            excluded_points=[
                ("/telemetry/proxy/api/v2/apmtelemetry", "$.payload.configuration[]"),
                ("/telemetry/proxy/api/v2/apmtelemetry", "$.payload"),  # APPSEC-52845
            ]
        )

    @bug(context.library >= "nodejs@2.27.1", reason="APPSEC-52805")
    def test_library_schema_telemetry_conf_value(self):
        interfaces.library.assert_schema_point("/telemetry/proxy/api/v2/apmtelemetry", "$.payload.configuration[]")

    @bug(context.library < "python@v2.9.0.dev", reason="APPSEC-52845")
    def test_library_schema_telemetry_job_object(self):
        interfaces.library.assert_schema_point("/telemetry/proxy/api/v2/apmtelemetry", "$.payload")


@scenarios.all_endtoend_scenarios
class Test_Agent:
    """Agents's payload are valid regarding schemas"""

    def setup_agent_schema_full(self):
        # send some requests to be sure to trigger events
        weblog.get("/waf", params={"key": "\n :"})

    def test_agent_schema_full(self):
        interfaces.agent.assert_schema_points(
            excluded_points=[
                ("/api/v2/apmtelemetry", "$.payload.configuration[]"),
                ("/api/v2/apmtelemetry", "$.payload"),  # APPSEC-52845
            ]
        )

    @bug(context.library >= "nodejs@2.27.1", reason="APPSEC-52805")
    @irrelevant(context.scenario is scenarios.crossed_tracing_libraries, reason="APPSEC-52805")
    @irrelevant(context.scenario is scenarios.graphql_appsec, reason="APPSEC-52805")
    def test_agent_schema_telemetry_conf_value(self):
        interfaces.agent.assert_schema_point("/api/v2/apmtelemetry", "$.payload.configuration[]")

    @bug(context.library < "python@v2.9.0.dev", reason="APPSEC-52845")
    @irrelevant(context.scenario is scenarios.crossed_tracing_libraries, reason="APPSEC-52805")
    def test_agent_schema_telemetry_job_object(self):
        interfaces.agent.assert_schema_point("/api/v2/apmtelemetry", "$.payload")
