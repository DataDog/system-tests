# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import pytest
from utils import weblog, context, coverage, interfaces, released, missing_feature, irrelevant, rfc, scenario
from tests.constants import PYTHON_RELEASE_GA_1_1
from .waf.utils import rules


if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@coverage.not_testable
class Test_OneVariableInstallation:
    """Installation with 1 env variable"""


@released(dotnet="1.29.0", java="0.87.0", nodejs="2.0.0", php_appsec="0.1.0", python="?", ruby="?")
@coverage.basic
class Test_StaticRuleSet:
    """Appsec loads rules from a static rules file"""

    @missing_feature(library="golang", reason="standard logs not implemented")
    @missing_feature(library="dotnet", reason="Rules file is not parsed")
    @missing_feature(library="php", reason="Rules file is not parsed")
    @missing_feature(library="nodejs", reason="Rules file is not parsed")
    def test_basic_hardcoded_ruleset(self):
        """ Library has loaded a hardcoded AppSec ruleset"""
        stdout = interfaces.library_stdout if context.library != "dotnet" else interfaces.library_dotnet_managed
        stdout.assert_presence(r"AppSec loaded \d+ rules from file <?.*>?$", level="INFO")


@released(golang="?", dotnet="?", java="?", nodejs="?", php="?", python="?", ruby="?")
@coverage.not_implemented
class Test_FleetManagement:
    """ApppSec supports Fleet management"""


@coverage.basic
class Test_RuleSet_1_2_4:
    """ AppSec uses rule set 1.2.4 or higher """

    def test_main(self):
        assert context.appsec_rules_version >= "1.2.4"


@coverage.basic
class Test_RuleSet_1_2_5:
    """ AppSec uses rule set 1.2.5 or higher """

    def test_main(self):
        assert context.appsec_rules_version >= "1.2.5"


@released(dotnet="2.7.0", golang="1.38.0", java="0.99.0", nodejs="2.5.0")
@released(php_appsec="0.3.0", python="1.2.1", ruby="1.0.0")
@coverage.good
class Test_RuleSet_1_3_1:
    """ AppSec uses rule set 1.3.1 or higher """

    def test_main(self):
        """ Test rule set version number"""
        assert context.appsec_rules_version >= "1.3.1"

    def setup_nosqli_keys(self):
        self.r_keys = weblog.get("/waf/", params={"$nin": "value"})

    def test_nosqli_keys(self):
        """Test a rule defined on this rules version: nosql on keys"""
        interfaces.library.assert_waf_attack(self.r_keys, rules.nosql_injection)

    def setup_nosqli_keys_with_brackets(self):
        self.r_keys2 = weblog.get("/waf/", params={"[$ne]": "value"})

    @irrelevant(library="php", reason="The PHP runtime interprets brackets as arrays, so this is considered malformed")
    @irrelevant(library="nodejs", reason="Node interprets brackets as arrays, so they're truncated")
    def test_nosqli_keys_with_brackets(self):
        """Test a rule defined on this rules version: nosql on keys with brackets"""
        interfaces.library.assert_waf_attack(self.r_keys2, rules.nosql_injection.crs_942_290)


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2355333252/Environment+Variables")
@coverage.basic
@released(java="0.100.0", nodejs="2.7.0", python="1.1.2")
class Test_ConfigurationVariables:
    """ Configuration environment variables """

    SECRET = "This-value-is-secret"

    # this value is defined in DD_APPSEC_OBFUSCATION_PARAMETER_VALUE_REGEXP
    SECRET_WITH_HIDDEN_VALUE = "hide_value"

    def setup_enabled(self):
        self.r_enabled = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    def test_enabled(self):
        """ test DD_APPSEC_ENABLED = true """
        interfaces.library.assert_waf_attack(self.r_enabled)

    def setup_disabled(self):
        self.r_disabled = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    @irrelevant(library="ruby", weblog_variant="rack", reason="it's not possible to auto instrument with rack")
    @missing_feature(
        context.weblog_variant in ["sinatra14", "sinatra20", "sinatra21"],
        reason="Conf is done in weblog instead of library",
    )
    @scenario("APPSEC_DISABLED")
    def test_disabled(self):
        """ test DD_APPSEC_ENABLED = false """
        interfaces.library.assert_no_appsec_event(self.r_disabled)

    def setup_appsec_rules(self):
        self.r_appsec_rules = weblog.get("/waf", headers={"attack": "dedicated-value-for-testing-purpose"})

    @scenario("APPSEC_CUSTOM_RULES")
    def test_appsec_rules(self):
        """ test DD_APPSEC_RULES = custom rules file """
        interfaces.library.assert_waf_attack(self.r_appsec_rules, pattern="dedicated-value-for-testing-purpose")

    def setup_waf_timeout(self):
        long_payload = "?" + "&".join(f"{k}={v}" for k, v in ((f"key_{i}", f"value{i}") for i in range(1000)))
        self.r_waf_timeout = weblog.get(f"/waf/{long_payload}", headers={"User-Agent": "Arachni/v1"})

    @missing_feature(context.library < "java@0.113.0")
    @missing_feature(context.library == "java" and context.weblog_variant == "spring-boot-openliberty")
    @scenario("APPSEC_LOW_WAF_TIMEOUT")
    def test_waf_timeout(self):
        """ test DD_APPSEC_WAF_TIMEOUT = low value """
        interfaces.library.assert_no_appsec_event(self.r_waf_timeout)

    def setup_obfuscation_parameter_key(self):
        self.r_op_key = weblog.get("/waf", headers={"hide-key": f"acunetix-user-agreement {self.SECRET}"})

    @missing_feature(context.library <= "ruby@1.0.0")
    @missing_feature(context.library < f"python@{PYTHON_RELEASE_GA_1_1}")
    @scenario("APPSEC_CUSTOM_OBFUSCATION")
    def test_obfuscation_parameter_key(self):
        """ test DD_APPSEC_OBFUSCATION_PARAMETER_KEY_REGEXP """

        def validate_appsec_span_tags(span, appsec_data):  # pylint: disable=unused-argument
            if self.SECRET in span["meta"]["_dd.appsec.json"]:
                raise Exception("The security events contain the secret value that should be obfuscated")
            return True

        interfaces.library.assert_waf_attack(self.r_op_key, pattern="<Redacted>")
        interfaces.library.validate_appsec(self.r_op_key, validate_appsec_span_tags)

    def setup_obfuscation_parameter_value(self):
        headers = {"attack": f"acunetix-user-agreement {self.SECRET_WITH_HIDDEN_VALUE}"}
        self.r_op_value = weblog.get("/waf", headers=headers)

    @missing_feature(context.library <= "ruby@1.0.0")
    @missing_feature(context.library < f"python@{PYTHON_RELEASE_GA_1_1}")
    @scenario("APPSEC_CUSTOM_OBFUSCATION")
    def test_obfuscation_parameter_value(self):
        """ test DD_APPSEC_OBFUSCATION_PARAMETER_VALUE_REGEXP """

        def validate_appsec_span_tags(span, appsec_data):  # pylint: disable=unused-argument
            if self.SECRET_WITH_HIDDEN_VALUE in span["meta"]["_dd.appsec.json"]:
                raise Exception("The security events contain the secret value that should be obfuscated")
            return True

        interfaces.library.assert_waf_attack(self.r_op_value, pattern="<Redacted>")
        interfaces.library.validate_appsec(self.r_op_value, validate_appsec_span_tags)
