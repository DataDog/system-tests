# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Test format specifications"""

from utils import BaseTestCase, interfaces, bug, context


class Test_Library(BaseTestCase):
    """Libraries's payload are valid regarding schemas"""

    @bug(context.library < "java@0.93.0")
    @bug(context.library < "golang@1.36.1")
    def test_full(self):
        # send some requests to be sure to trigger events
        self.weblog_get("/waf", params={"key": "\n :"})  # rules.http_protocol_violation.crs_921_160

        interfaces.library.assert_schemas()

    def test_non_regression(self):
        """ Non-regression test on shemas """

        # Never skip this test. As a full respect of shemas may be hard, this test ensure that
        # at least the part that was ok stays ok.

        allowed_errors = None
        if context.library == "golang":
            allowed_errors = (
                r"'actor' is a required property on instance \['events'\]\[\d+\]\['context'\]",
                r"'protocol_version' is a required property on instance ",
            )
        elif context.library == "java":
            allowed_errors = (
                r"'appsec' was expected on instance \['events'\]\[\d+\]\['event_type'\]",
                r"'headers' is a required property on instance \['events'\]\[\d+\]\['context'\]\['http'\]\['response'\]",
                r"'idempotency_key' is a required property on instance ",
            )

        interfaces.library.assert_schemas(allowed_errors=allowed_errors)


class Test_Agent(BaseTestCase):
    """Agents's payload are valid regarding schemas"""

    @bug(context.library < "java@0.93.0")
    @bug(context.library < "golang@1.36.1")
    def test_full(self):

        # send some requests to be sure to trigger events
        self.weblog_get("/waf", params={"key": "\n :"})  # rules.http_protocol_violation.crs_921_160

        interfaces.agent.assert_schemas()

    def test_non_regression(self):
        """ Non-regression test on shemas """

        # Never skip this test. As a full respect of shemas may be hard, this test ensure that
        # at least the part that was ok stays ok.

        allowed_errors = None
        if context.library == "golang":
            allowed_errors = (
                r"'actor' is a required property on instance \['events'\]\[\d+\]\['context'\]",
                r"'protocol_version' is a required property on instance ",
            )
        elif context.library == "java":
            allowed_errors = (
                r"'appsec' was expected on instance \['events'\]\[\d+\]\['event_type'\]",
                r"'headers' is a required property on instance \['events'\]\[\d+\]\['context'\]\['http'\]\['response'\]",
                r"'idempotency_key' is a required property on instance ",
            )

        interfaces.agent.assert_schemas(allowed_errors=allowed_errors)
