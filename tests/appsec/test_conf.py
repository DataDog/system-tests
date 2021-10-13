# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, context, skipif, interfaces


@skipif(not context.appsec_is_released, reason=context.appsec_not_released_reason)
class Test_StaticRuleSet(BaseTestCase):
    """Test different way to configure AppSec"""

    @skipif(context.library == "dotnet", reason="Missing feature: can't be tested has thers is no log")
    def test_basic_hardcoded_ruleset(self):
        """ Library has loaded a hardcoded AppSec ruleset"""
        stdout = interfaces.library_stdout if context.library != "dotnet" else interfaces.library_dotnet_managed
        stdout.assert_presence(r"AppSec loaded \d+ rules from file <.*>$", level="INFO")


@skipif(not context.appsec_is_released, reason=context.appsec_not_released_reason)
@skipif(context.library == "dotnet", reason="Missing feature")
@skipif(context.library == "golang", reason="missing feature")
@skipif(context.library == "java", reason="Missing feature")
class Test_FleetManagement(BaseTestCase):
    def test_basic(self):
        raise NotImplementedError
