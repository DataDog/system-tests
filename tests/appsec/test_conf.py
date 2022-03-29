# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, context, interfaces, released, missing_feature, irrelevant
import pytest


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
