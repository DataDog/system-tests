# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, context, interfaces, released, missing_feature
import pytest


if context.weblog_variant == "echo-poc":
    pytestmark = pytest.mark.skip("not relevant: echo is not instrumented")
elif context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@released(golang="?", dotnet="1.29.0", java="0.87.0", nodejs="?", php="?", python="?", ruby="?")
class Test_StaticRuleSet(BaseTestCase):
    """Appsec loads rules from a static rules file"""

    @missing_feature(library="dotnet", reason="can't know the number of rules")
    def test_basic_hardcoded_ruleset(self):
        """ Library has loaded a hardcoded AppSec ruleset"""
        stdout = interfaces.library_stdout if context.library != "dotnet" else interfaces.library_dotnet_managed
        stdout.assert_presence(r"AppSec loaded \d+ rules from file <.*>$", level="INFO")


@released(golang="?", dotnet="?", java="?", nodejs="?", php="?", python="?", ruby="?")
class Test_FleetManagement(BaseTestCase):
    """ApppSec supports Fleet management"""

    def test_basic(self):
        raise NotImplementedError
