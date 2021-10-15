# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, context, skipif, interfaces, released


@released(cpp="not relevant")
@released(golang="?" if context.weblog_variant != "echo-poc" else "not relevant: echo is not instrumented")
@released(dotnet="1.29.0", java="0.87.0", nodejs="?", php="?", python="?", ruby="?")
class Test_StaticRuleSet(BaseTestCase):
    """Test different way to configure AppSec"""

    def test_basic_hardcoded_ruleset(self):
        """ Library has loaded a hardcoded AppSec ruleset"""
        stdout = interfaces.library_stdout if context.library != "dotnet" else interfaces.library_dotnet_managed
        stdout.assert_presence(r"AppSec loaded \d+ rules from file <.*>$", level="INFO")


@released(cpp="not relevant")
@released(golang="?" if context.weblog_variant != "echo-poc" else "not relevant: echo is not instrumented")
@released(dotnet="?", java="?", nodejs="?", php="?", python="?", ruby="?")
class Test_FleetManagement(BaseTestCase):
    def test_basic(self):
        raise NotImplementedError
