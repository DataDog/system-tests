from utils import interfaces, released, scenarios, weblog


@released(
    java="?", php_appsec="0.8.1", python={"django-poc": "1.12", "flask-poc": "1.12", "*": "1.16.1"}, ruby="1.12.0",
)
@scenarios.appsec_custom_rules
class Test_CustomRules:
    """Includes a version of the WAF supporting custom rules"""

    def setup_normal_custom_rule(self):
        self.cr1 = weblog.get("/waf/", params={"value1": "custom_rule1"})
        self.cr2 = weblog.get("/waf/", params={"value2": "custom_rule2"})

    def test_normal_custom_rule(self):
        interfaces.library.assert_waf_attack(self.cr1, pattern="custom_rule1", address="server.request.query")
        interfaces.library.assert_waf_attack(self.cr2, pattern="custom_rule2", address="server.request.query")
