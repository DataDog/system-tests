# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Test format specifications"""

from utils import BaseTestCase, interfaces, context, skipif


class Test_Library(BaseTestCase):
    @skipif(context.library <= "java@0.87.0", reason="missing feature")
    @skipif(context.library > "java@0.87.0", reason="known bug: APPSEC-1697")
    @skipif(context.library == "dotnet", reason="known bug: APPSEC-1698")
    def test_library_format(self):
        """Libraries's payload are valid regarding schemas"""
        interfaces.library.assert_schemas()


class Test_Agent(BaseTestCase):
    @skipif(context.library <= "java@0.87.0", reason="missing feature")
    @skipif(context.library > "java@0.87.0", reason="known bug: APPSEC-1697")
    @skipif(context.library == "dotnet", reason="known bug: APPSEC-1698")
    def test_agent_format(self):
        """Agents's payload are valid regarding schemas"""
        interfaces.agent.assert_schemas()
