# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Test format specifications"""

from utils import weblog, interfaces, bug, context, scenarios


@scenarios.all_endtoend_scenarios
class Test_library:
    """Libraries's payload are valid regarding schemas"""

    def setup_library_schema_full(self):
        # send some requests to be sure to trigger events
        weblog.get("/waf", params={"key": "\n :"})  # rules.http_protocol_violation.crs_921_160

    def test_library_schema_full(self):
        interfaces.library.assert_schema_points(
            excluded_points=[
                ("/telemetry/proxy/api/v2/apmtelemetry", "$.payload.configuration[]"),
                ("/telemetry/proxy/api/v2/apmtelemetry", "$.payload"),  # APPSEC-52845
            ]
        )

    @bug(context.library >= "nodejs@2.27.1")
    @bug(library="cpp")
    @bug(library="dotnet")
    @bug(library="golang")
    @bug(library="java")
    @bug(library="php")
    @bug(library="python")
    @bug(library="ruby")
    def test_library_schema_telemetry_conf_value(self):
        interfaces.library.assert_schema_point("/telemetry/proxy/api/v2/apmtelemetry", "$.payload.configuration[]")

    @bug(library="python", reason="APPSEC-52845")
    def test_library_schema_telemetry_job_object(self):
        interfaces.library.assert_schema_point("/telemetry/proxy/api/v2/apmtelemetry", "$.payload")

    # @bug(context.library < "golang@1.36.0")
    # @bug(context.library < "java@0.93.0")
    # @bug(context.library >= "dotnet@2.24.0")
    # @bug(
    #     context.library >= "python@1.16.0rc2.dev37"
    #     and context.agent_version >= "7.47.0rc2"
    #     and context.appsec_rules_file is not None,
    #     reason="on /v0.7/config, client.products is an empty array",
    # )
    # def test_full(self):
    #     interfaces.library.assert_schemas()

    # def test_non_regression(self):
    #     """ Non-regression test on shemas """

    #     # Never skip this test. As a full respect of shemas may be hard, this test ensure that
    #     # at least the part that was ok stays ok.

    #     allowed_errors = None
    #     if context.library == "golang":
    #         allowed_errors = (
    #             r"'actor' is a required property on instance \['events'\]\[\d+\]\['context'\]",
    #             r"'protocol_version' is a required property on instance ",
    #         )
    #     elif context.library == "java":
    #         # pylint: disable=line-too-long
    #         allowed_errors = (
    #             r"'appsec' was expected on instance \['events'\]\[\d+\]\['event_type'\]",
    #             r"'headers' is a required property on instance \['events'\]\[\d+\]\['context'\]\['http'\]\['response'\]",
    #             r"'idempotency_key' is a required property on instance ",
    #         )
    #     elif context.library == "dotnet":
    #         allowed_errors = (
    #             # value is missing in configuration object in telemetry payloads
    #             r"'value' is a required property on instance \['payload'\]\['configuration'\]\[\d+\]",
    #         )
    #     elif context.library == "python":
    #         allowed_errors = (r"\[\] is too short on instance \['client'\]\['products'\]",)

    #     interfaces.library.assert_schemas(allowed_errors=allowed_errors)


@scenarios.all_endtoend_scenarios
class Test_Agent:
    """Agents's payload are valid regarding schemas"""

    def setup_agent_schema_full(self):
        # send some requests to be sure to trigger events
        weblog.get("/waf", params={"key": "\n :"})  # rules.http_protocol_violation.crs_921_160

    # @bug(context.library < "golang@1.36.0")
    # @bug(context.library < "java@0.93.0")
    # @bug(context.library >= "dotnet@2.24.0")
    def test_agent_schema_full(self):
        interfaces.agent.assert_schema_points(
            excluded_points=[
                ("/api/v2/apmtelemetry", "$.payload.configuration[]"),
                ("/api/v2/apmtelemetry", "$.payload"),  # APPSEC-52845
            ]
        )

    @bug(context.library >= "nodejs@2.27.1")
    @bug(library="cpp")
    @bug(library="dotnet")
    @bug(library="golang")
    @bug(library="java")
    @bug(library="php")
    @bug(library="python")
    @bug(library="ruby")
    def test_agent_schema_telemetry_conf_value(self):
        interfaces.agent.assert_schema_point("/api/v2/apmtelemetry", "$.payload.configuration[]")

    @bug(library="python", reason="APPSEC-52845")
    def test_library_schema_telemetry_job_object(self):
        interfaces.agent.assert_schema_point("/api/v2/apmtelemetry", "$.payload")

    # def test_non_regression(self):
    #     """ Non-regression test on shemas """

    #     # Never skip this test. As a full respect of shemas may be hard, this test ensure that
    #     # at least the part that was ok stays ok.

    #     allowed_errors = None
    #     if context.library == "golang":
    #         allowed_errors = (
    #             r"'actor' is a required property on instance \['events'\]\[\d+\]\['context'\]",
    #             r"'protocol_version' is a required property on instance ",
    #         )
    #     elif context.library == "java":
    #         # pylint: disable=line-too-long
    #         allowed_errors = (
    #             r"'appsec' was expected on instance \['events'\]\[\d+\]\['event_type'\]",
    #             r"'headers' is a required property on instance \['events'\]\[\d+\]\['context'\]\['http'\]\['response'\]",
    #             r"'idempotency_key' is a required property on instance ",
    #         )
    #     elif context.library == "dotnet":
    #         allowed_errors = (
    #             # value is missing in configuration object in telemetry payloads
    #             r"'value' is a required property on instance \['payload'\]\['configuration'\]\[\d+\]",
    #         )

    #     interfaces.agent.assert_schemas(allowed_errors=allowed_errors)
