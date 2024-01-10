# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import (
    weblog,
    context,
    coverage,
    interfaces,
    bug,
    missing_feature,
    scenarios,
    features,
)


# get the default log output
stdout = (
    interfaces.library_stdout
    if context.library != "dotnet"
    else interfaces.library_dotnet_managed
)


@coverage.basic
@scenarios.appsec_corrupted_rules
@features.threats_configuration
class Test_CorruptedRules:
    """AppSec do not report anything if rule file is invalid"""

    @missing_feature(library="golang")
    @missing_feature(library="nodejs")
    @missing_feature(library="python")
    @missing_feature(library="php")
    @missing_feature(library="ruby", reason="standard logs not implemented")
    @bug(library="dotnet", reason="ERROR io CRITICAL")
    def test_c05(self):
        """Log C5: Rules file is corrupted"""
        stdout.assert_presence(
            r"AppSec could not read the rule file .* as it was invalid: .*",
            level="CRITICAL",
        )

    def setup_no_attack_detected(self):
        self.r_1 = weblog.get("/", headers={"User-Agent": "Arachni/v1"})
        self.r_2 = weblog.get("/waf", params={"attack": "<script>"})

    def test_no_attack_detected(self):
        """ Appsec does not catch any attack """
        interfaces.library.assert_no_appsec_event(self.r_1)
        interfaces.library.assert_no_appsec_event(self.r_2)


@coverage.basic
@scenarios.appsec_missing_rules
@features.threats_configuration
class Test_MissingRules:
    """AppSec do not report anything if rule file is missing"""

    @missing_feature(library="golang")
    @missing_feature(library="nodejs")
    @missing_feature(library="python")
    @missing_feature(library="php")
    @missing_feature(library="ruby", reason="standard logs not implemented")
    @bug(
        library="dotnet", reason="ERROR io CRITICAL"
    )  # and the last sentence is missing
    def test_c04(self):
        """Log C4: Rules file is missing"""
        stdout.assert_presence(
            r'AppSec could not find the rules file in path "?/donotexists"?. '
            r"AppSec will not run any protections in this application. "
            r"No security activities will be collected.",
            level="CRITICAL",
        )

    def setup_no_attack_detected(self):
        self.r_1 = weblog.get("/", headers={"User-Agent": "Arachni/v1"})
        self.r_2 = weblog.get("/waf", params={"attack": "<script>"})

    def test_no_attack_detected(self):
        """ Appsec does not catch any attack """
        interfaces.library.assert_no_appsec_event(self.r_1)
        interfaces.library.assert_no_appsec_event(self.r_2)


# Basically the same test as Test_MissingRules, and will be called by the same scenario (save CI time)
@coverage.good
@scenarios.appsec_custom_rules
@features.threats_configuration
class Test_ConfRuleSet:
    """AppSec support env var DD_APPSEC_RULES"""

    def setup_requests(self):
        self.r_1 = weblog.get("/waf", headers={"User-Agent": "Arachni/v1"})
        self.r_2 = weblog.get(
            "/waf", headers={"attack": "dedicated-value-for-testing-purpose"}
        )

    def test_requests(self):
        """ Appsec does not catch any attack """
        interfaces.library.assert_no_appsec_event(self.r_1)
        interfaces.library.assert_waf_attack(
            self.r_2, pattern="dedicated-value-for-testing-purpose"
        )

    def test_log(self):
        """ Check there is no error reported in logs """
        stdout.assert_absence("AppSec could not read the rule file")
        stdout.assert_absence("failed to parse rule")
        stdout.assert_absence("WAF initialization failed")


@coverage.basic
@scenarios.appsec_custom_rules
@features.threats_configuration
@features.serialize_waf_rules_without_limiting_their_sizes
class Test_NoLimitOnWafRules:
    """ Serialize WAF rules without limiting their sizes """

    def setup_main(self):
        self.r_1 = weblog.get(
            "/waf", headers={"attack": "first_pattern_of_a_very_long_list"}
        )
        self.r_2 = weblog.get(
            "/waf", headers={"attack": "last_pattern_of_a_very_long_list"}
        )

    def test_main(self):
        interfaces.library.assert_waf_attack(
            self.r_1, pattern="first_pattern_of_a_very_long_list"
        )
        interfaces.library.assert_waf_attack(
            self.r_2, pattern="last_pattern_of_a_very_long_list"
        )
