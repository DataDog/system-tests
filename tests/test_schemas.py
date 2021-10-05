"""Test format specifications"""

from utils import BaseTestCase, interfaces, context, skipif


class Test_Library(BaseTestCase):
    @skipif(context.library <= "java@0.87.0", reason="missing feature")
    @skipif(context.library > "java@0.87.0", reason="known bug in the http context")
    @skipif(context.library == "dotnet", reason="known bug in the http context")
    def test_library_format(self):
        """Libraries's payload are valid regarding schemas"""
        interfaces.library.assert_schemas()


class Test_Agent(BaseTestCase):
    @skipif(context.library <= "java@0.87.0", reason="missing feature")
    @skipif(context.library > "java@0.87.0", reason="known bug in the http context")
    @skipif(context.library == "dotnet", reason="known bug in the http context")
    def test_agent_format(self):
        """Agents's payload are valid regarding schemas"""
        interfaces.agent.assert_schemas()
