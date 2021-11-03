# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Test format specifications"""

from utils import BaseTestCase, interfaces, bug


class Test_Library(BaseTestCase):
    @bug(library="java", reason="APPSEC-1697")
    @bug(library="dotnet", reason="APPSEC-1698")
    @bug(library="golang")
    @bug(library="ruby")
    def test_library_format(self):
        """Libraries's payload are valid regarding schemas"""

        # send some requests to be sure to trigger events
        self.weblog_get("/waf", params={"key": "\n :"})  # rules.http_protocol_violation.crs_921_160

        interfaces.library.assert_schemas()


class Test_Agent(BaseTestCase):
    @bug(library="java", reason="APPSEC-1697")
    @bug(library="dotnet", reason="APPSEC-1698")
    @bug(library="golang")
    @bug(library="ruby")
    def test_agent_format(self):
        """Agents's payload are valid regarding schemas"""

        # send some requests to be sure to trigger events
        self.weblog_get("/waf", params={"key": "\n :"})  # rules.http_protocol_violation.crs_921_160

        interfaces.agent.assert_schemas()
