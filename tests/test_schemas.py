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
                ("/telemetry/proxy/api/v2/apmtelemetry", "$.payload.configuration[].value"),  # APMS-12697
            ]
        )

    @bug(context.library >= "nodejs@2.27.1", reason="APPSEC-52805")
    def test_library_schema_telemetry_conf_value(self):
        interfaces.library.assert_schema_point("/telemetry/proxy/api/v2/apmtelemetry", "$.payload.configuration[]")

    @bug(context.library < "python@v2.9.0.dev", reason="APPSEC-52845")
    def test_library_schema_telemetry_job_object(self):
        interfaces.library.assert_schema_point("/telemetry/proxy/api/v2/apmtelemetry", "$.payload")

    @bug(library="golang", reason="APMS-12697")
    def test_library_telenetry_configuration_value(self):
        interfaces.library.assert_schema_point(
            "/telemetry/proxy/api/v2/apmtelemetry", "$.payload.configuration[].value"
        )


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
                ("/api/v2/apmtelemetry", "$"),  # the main payload sent by the agent may be an array i/o an object
                ("/api/v2/apmtelemetry", "$.payload.configuration[].value"),  # APMS-12697
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

    @bug(context.agent_version > "7.53.0", reason="Jira missing")
    def test_agent_schema_telemetry_main_payload(self):
        interfaces.agent.assert_schema_point("/api/v2/apmtelemetry", "$")

    @bug(library="golang", reason="APMS-12697")
    def test_library_telenetry_configuration_value(self):
        interfaces.agent.assert_schema_point("/api/v2/apmtelemetry", "$.payload.configuration[].value")
