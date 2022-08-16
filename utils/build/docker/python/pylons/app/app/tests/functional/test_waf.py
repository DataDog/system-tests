from app.tests import *


class TestWafController(TestController):
    def test_index(self):
        response = self.app.get(url(controller="waf", action="index"))
        # Test response...
