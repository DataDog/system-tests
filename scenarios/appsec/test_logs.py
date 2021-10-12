# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, context, skipif, interfaces

# get the default log outpu
stdout = interfaces.library_stdout if context.library != "dotnet" else interfaces.library_dotnet_managed


@skipif(context.library == "cpp", reason="not relevant: No C++ appsec planned")
@skipif(not context.appsec_is_released, reason=context.appsec_not_released_reason)
class Test_Standardization(BaseTestCase):
    """AppSec errors logs should be standardized"""

    @skipif(context.library == "dotnet", reason="known bug: ERROR io CRITICAL")  # and the last sentence is missing
    @skipif(context.library == "java", reason="known bug: ERROR io CRITICAL")
    def test_c04(self):
        """Log C4: Rules file is missing"""
        stdout.assert_presence(
            r'AppSec could not find the rules file in path "?/donotexists"?. '
            r"AppSec will not run any protections in this application. "
            r"No security activities will be collected.",
            level="CRITICAL",
        )

    @skipif(context.library == "dotnet", reason="known bug: ERROR io CRITICAL")
    @skipif(context.library == "java", reason="missing feature: Partial, Cannot be fully implemented")
    def test_c05(self):
        """Log C5: Rules file is corrupted"""
        stdout.assert_presence(r"AppSec could not read the rule file .* as it was invalid: .*", level="CRITICAL")
