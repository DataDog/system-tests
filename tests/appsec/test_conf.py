# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import pytest
from utils import BaseTestCase, context, coverage, interfaces, released, missing_feature, irrelevant, bug
from .waf.utils import rules


if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@released(dotnet="1.29.0", java="0.87.0", nodejs="2.0.0", php_appsec="0.1.0", python="?", ruby="?")
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
class Test_FleetManagement(BaseTestCase):
    """ApppSec supports Fleet management"""

    def test_basic(self):
        interfaces.library.append_not_implemented_validation()


class Test_RuleSet_1_2_4(BaseTestCase):
    """ AppSec uses rule set 1.2.4 or higher """

    def test_main(self):
        assert context.appsec_rules_version >= "1.2.4"


class Test_RuleSet_1_2_5(BaseTestCase):
    """ AppSec uses rule set 1.2.5 or higher """

    def test_main(self):
        assert context.appsec_rules_version >= "1.2.5"


@released(dotnet="2.7.0", golang="1.38.0", java="0.99.0", nodejs="?")
@released(php_appsec="0.3.0", python="1.1.0rc2.dev", ruby="?")
@coverage.good
class Test_RuleSet_1_3_1(BaseTestCase):
    """ AppSec uses rule set 1.3.1 or higher """

    def test_main(self):
        """ Test rule set version number"""
        interfaces.library.add_assertion(context.appsec_rules_version >= "1.3.1")

    @bug(library="python@1.1.0", reason="a PR was not included in the release")
    def test_nosqli_keys(self):
        """Test a rule defined on this rules version: nosql on keys"""
        r = self.weblog_get("/waf/", params={"$nin": "value"})
        interfaces.library.assert_waf_attack(r, rules.nosql_injection.sqr_000_007)

    @bug(library="python@1.1.0", reason="a PR was not included in the release")
    @irrelevant(library="php", reason="The PHP runtime interprets brackets as arrays, so this is considered malformed")
    def test_nosqli_keys_with_brackets(self):
        """Test a rule defined on this rules version: nosql on keys with brackets"""
        r = self.weblog_get("/waf/", params={"[$ne]": "value"})
        interfaces.library.assert_waf_attack(r, rules.nosql_injection.crs_942_290)
