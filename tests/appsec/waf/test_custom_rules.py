from utils import interfaces, weblog, features
from utils._context._scenarios.dynamic import dynamic_scenario


@features.waf_features
@dynamic_scenario(mandatory={"DD_APPSEC_RULES": "/appsec_custom_rules.json"})
class Test_CustomRules:
    """Includes a version of the WAF supporting custom rules"""

    def setup_normal_custom_rule(self):
        self.cr1 = weblog.get("/waf/", params={"value1": "custom_rule1"})
        self.cr2 = weblog.get("/waf/", params={"value2": "custom_rule2"})

    def test_normal_custom_rule(self):
        interfaces.library.assert_waf_attack(self.cr1, pattern="custom_rule1", address="server.request.query")
        interfaces.library.assert_waf_attack(self.cr2, pattern="custom_rule2", address="server.request.query")
