from utils import scenarios, released, interfaces, weblog


@released(java="?", dotnet="2.29.0", golang="?", nodejs="?", php_appsec="?", python="?", ruby="?", cpp="?")
@scenarios.appsec_custom_rules
class Test_CustomRules:
    """Includes a version of the WAF supporting custom rules"""

    def setup_normal_custom_rule(self):
        self.cr1 = weblog.get("/waf/", params={"value1": "custom_rule1"})
        self.cr2 = weblog.get("/waf/", params={"value2": "custom_rule2"})

    def test_normal_custom_rule(self):
        interfaces.library.assert_waf_attack(self.cr1, pattern="custom_rule1", address="server.request.query")
        interfaces.library.assert_waf_attack(self.cr2, pattern="custom_rule2", address="server.request.query")
