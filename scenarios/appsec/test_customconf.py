# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, context, interfaces, released, bug, missing_feature
import pytest


if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")

# get the default log output
stdout = interfaces.library_stdout if context.library != "dotnet" else interfaces.library_dotnet_managed


class _BaseNoAppSec(BaseTestCase):
    def test_no_attack_detected(self):
        """ Appsec does not catch any attack """
        r = self.weblog_get("/", headers={"User-Agent": "Arachni/v1"})
        interfaces.library.assert_no_appsec_event(r)

        r = self.weblog_get("/waf", params={"attack": "<script>"})
        interfaces.library.assert_no_appsec_event(r)


@released(java="0.93.0", php_appsec="0.3.0", ruby="?")
class Test_CorruptedRules(_BaseNoAppSec):
    """AppSec do not report anything if rule file is invalid"""

    @missing_feature(library="golang")
    @missing_feature(library="nodejs")
    @missing_feature(library="python")
    @missing_feature(library="php")
    @bug(library="dotnet", reason="ERROR io CRITICAL")
    def test_c05(self):
        """Log C5: Rules file is corrupted"""
        stdout.assert_presence(r"AppSec could not read the rule file .* as it was invalid: .*", level="CRITICAL")


@released(java="0.93.0", nodejs="?", php_appsec="0.3.0", ruby="?")
class Test_MissingRules(_BaseNoAppSec):
    """AppSec do not report anything if rule file is missing"""

    @missing_feature(library="golang")
    @missing_feature(library="nodejs")
    @missing_feature(library="python")
    @missing_feature(library="php")
    @bug(library="dotnet", reason="ERROR io CRITICAL")  # and the last sentence is missing
    def test_c04(self):
        """Log C4: Rules file is missing"""
        stdout.assert_presence(
            r'AppSec could not find the rules file in path "?/donotexists"?. '
            r"AppSec will not run any protections in this application. "
            r"No security activities will be collected.",
            level="CRITICAL",
        )


# Basically the same test as Test_MissingRules, and will be called by the same scenario (save CI time)
@released(java="0.93.0", nodejs="2.0.0", php_appsec="0.3.0", python="?", ruby="?")
class Test_ConfRuleSet(BaseTestCase):
    """AppSec support env var DD_APPSEC_RULES"""

    def test_requests(self):
        """ Appsec does not catch any attack """
        r = self.weblog_get("/waf", headers={"User-Agent": "Arachni/v1"})
        interfaces.library.assert_no_appsec_event(r)

        r = self.weblog_get("/waf", headers={"attack": "dedicated-value-for-testing-purpose"})
        interfaces.library.assert_waf_attack(r, pattern="dedicated-value-for-testing-purpose")

    def test_log(self):
        stdout.assert_absence("AppSec could not read the rule file")
        stdout.assert_absence("failed to parse rule")
        stdout.assert_absence("WAF initialization failed")
