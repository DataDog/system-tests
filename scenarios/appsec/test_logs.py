# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, context, skipif, interfaces, released, bug
import pytest


if context.weblog_variant == "echo-poc":
    pytestmark = pytest.mark.skip("not relevant: echo is not instrumented")
elif context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")

# get the default log outpu
stdout = interfaces.library_stdout if context.library != "dotnet" else interfaces.library_dotnet_managed


@released(golang="?", nodejs="?", php="?", python="?", ruby="?")
class Test_Standardization(BaseTestCase):
    """AppSec errors logs should be standardized"""

    @bug(library="dotnet", reason="ERROR io CRITICAL")  # and the last sentence is missing
    @bug(library="java", reason="ERROR io CRITICAL")
    def test_c04(self):
        """Log C4: Rules file is missing"""
        stdout.assert_presence(
            r'AppSec could not find the rules file in path "?/donotexists"?. '
            r"AppSec will not run any protections in this application. "
            r"No security activities will be collected.",
            level="CRITICAL",
        )

    @bug(library="dotnet", reason="ERROR io CRITICAL")
    @skipif(context.library == "java", reason="missing feature: Partial, Cannot be fully implemented")
    def test_c05(self):
        """Log C5: Rules file is corrupted"""
        stdout.assert_presence(r"AppSec could not read the rule file .* as it was invalid: .*", level="CRITICAL")
