# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import pytest
from utils import BaseTestCase, context, coverage, interfaces, released, missing_feature, irrelevant, bug, rfc
from .waf.utils import rules


if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@coverage.not_testable
class Test_OneVariableInstallation:
    """Installation with 1 env variable"""


@released(dotnet="1.29.0", java="0.87.0", nodejs="2.0.0", php_appsec="0.1.0", python="?", ruby="?")
@coverage.basic
class Test_StaticRuleSet(BaseTestCase):
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
class Test_FleetManagement(BaseTestCase):
    """ApppSec supports Fleet management"""


@coverage.basic
class Test_RuleSet_1_2_4(BaseTestCase):
    """ AppSec uses rule set 1.2.4 or higher """

    def test_main(self):
        assert context.appsec_rules_version >= "1.2.4"


@coverage.basic
class Test_RuleSet_1_2_5(BaseTestCase):
    """ AppSec uses rule set 1.2.5 or higher """

    def test_main(self):
        assert context.appsec_rules_version >= "1.2.5"


@released(dotnet="2.7.0", golang="1.38.0", java="0.99.0", nodejs="2.5.0")
@released(php_appsec="0.3.0", python="?", ruby="1.0.0")
@coverage.good
class Test_RuleSet_1_3_1(BaseTestCase):
    """ AppSec uses rule set 1.3.1 or higher """

    def test_main(self):
        """ Test rule set version number"""
        interfaces.library.add_assertion(context.appsec_rules_version >= "1.3.1")

    def test_nosqli_keys(self):
        """Test a rule defined on this rules version: nosql on keys"""
        r = self.weblog_get("/waf/", params={"$nin": "value"})
        interfaces.library.assert_waf_attack(r, rules.nosql_injection.sqr_000_007)

    @irrelevant(library="php", reason="The PHP runtime interprets brackets as arrays, so this is considered malformed")
    @irrelevant(library="nodejs", reason="Node interprets brackets as arrays, so they're truncated")
    def test_nosqli_keys_with_brackets(self):
        """Test a rule defined on this rules version: nosql on keys with brackets"""
        r = self.weblog_get("/waf/", params={"[$ne]": "value"})
        interfaces.library.assert_waf_attack(r, rules.nosql_injection.crs_942_290)


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2355333252/Environment+Variables")
@coverage.basic
@released(java="0.100.0", nodejs="2.7.0", python="1.1.2")
class Test_ConfigurationVariables(BaseTestCase):
    """ Configuration environment variables """

    # some test are available in scenarios/

    def test_enabled(self):
        # test DD_APPSEC_ENABLED = true
        r = self.weblog_get("/waf/", headers={"User-Agent": "Arachni/v1"})
        interfaces.library.assert_waf_attack(r)
