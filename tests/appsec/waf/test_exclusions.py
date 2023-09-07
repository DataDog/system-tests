import pytest
from utils import context, interfaces, missing_feature, released, scenarios, weblog, bug

if context.weblog_variant == "akka-http":
    pytestmark = pytest.mark.skip("missing feature: No AppSec support")


@released(
    java="1.6.0", php_appsec="0.7.0", python={"django-poc": "1.12", "flask-poc": "1.12", "*": "1.16.1"}, ruby="1.11.0",
)
@missing_feature(context.weblog_variant == "spring-boot-3-native", reason="GraalVM. Tracing support only")
@scenarios.appsec_custom_rules
class Test_Exclusions:
    """Includes a version of the WAF supporting rule exclusion"""

    def setup_input_exclusion_negative_test(self):
        self.r_iexnt1 = weblog.get("/waf/", params={"excluded_key": "true"})
        self.r_iexnt2 = weblog.get("/waf/", params={"excluded_key": "true", "activate_exclusion": "false"})

    @bug(context.library <= "ruby@1.12.1")
    def test_input_exclusion_negative_test(self):
        interfaces.library.assert_waf_attack(self.r_iexnt1, pattern="true", address="server.request.query")
        interfaces.library.assert_waf_attack(self.r_iexnt2, pattern="true", address="server.request.query")

    def setup_input_exclusion_positive_test(self):
        self.r_iexpt = weblog.get("/waf/", params={"excluded_key": "true", "activate_exclusion": "true"})

    def test_input_exclusion_positive_test(self):
        interfaces.library.assert_no_appsec_event(self.r_iexpt)

    def setup_rule_exclusion_negative_test(self):
        self.r_rent1 = weblog.get("/waf/", params={"foo": "bbbb"})
        self.r_rent2 = weblog.get("/waf/", params={"foo": "bbbb", "activate_exclusion": "false"})

    def test_rule_exclusion_negative_test(self):
        interfaces.library.assert_waf_attack(self.r_rent1, pattern="bbbb", address="server.request.query")
        interfaces.library.assert_waf_attack(self.r_rent2, pattern="bbbb", address="server.request.query")

    def setup_rule_exclusion_positive_test(self):
        self.r_rept = weblog.get("/waf/", params={"foo": "bbbb", "activate_exclusion": "true"})

    @bug(context.library <= "ruby@1.12.1")
    def test_rule_exclusion_positive_test(self):
        interfaces.library.assert_no_appsec_event(self.r_rept)
