"""Test format specifications"""

from utils import BaseTestCase, interfaces


class Test_Library(BaseTestCase):
    def test_library_format(self):
        """Libraries's payload are valid regarding schemas"""
        interfaces.library.assert_schemas()


class Test_Agent(BaseTestCase):
    def test_agent_format(self):
        """Agents's payload are valid regarding schemas"""
        interfaces.agent.assert_schemas()
