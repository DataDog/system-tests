# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from tests.appsec.utils import find_series
from utils import weblog, context, interfaces, scenarios, features, bug


# get the default log output
stdout = interfaces.library_stdout if context.library != "dotnet" else interfaces.library_dotnet_managed


@scenarios.appsec_corrupted_rules
@features.threats_configuration
class Test_CorruptedRules:
    """AppSec do not report anything if rule file is invalid"""

    def setup_c05(self):
        self.r_1 = weblog.get("/", headers={"User-Agent": "Arachni/v1"})
        self.r_2 = weblog.get("/waf", params={"attack": "<script>"})

    def test_c05(self):
        for r in [self.r_1, self.r_2]:
            assert r.status_code == 200
            # Appsec does not catch any attack
            interfaces.library.assert_no_appsec_event(r)


@scenarios.appsec_corrupted_rules
@features.threats_configuration
class Test_CorruptedRules_Telemetry:
    """Report telemetry when rules file is corrupted"""

    def setup_waf_init_and_config_errors_tags(self):
        self.r_1 = weblog.get("/", headers={"User-Agent": "Arachni/v1"})
        self.r_2 = weblog.get("/waf", params={"attack": "<script>"})

    @bug(context.library < "nodejs@5.68.0", reason="APPSEC-59077")
    def test_waf_init_and_config_errors_tags(self):
        waf_init_series = find_series("appsec", ["waf.init"])
        waf_init_metric = [
            d for d in waf_init_series if "event_rules_version:unknown" in d["tags"] and "success:false" in d["tags"]
        ]
        assert waf_init_metric, "waf.init missing 'success:false' or 'event_rules_version:unknown' tag"

        waf_config_errors_series = find_series("appsec", ["waf.config_errors"])
        with_event_rules_version_tag = [
            d for d in waf_config_errors_series if "event_rules_version:unknown" in d["tags"]
        ]
        assert with_event_rules_version_tag, "waf.config_errors missing 'event_rules_version:unknown' tag"

        with_waf_version = [d for d in waf_config_errors_series if any(t.startswith("waf_version:") for t in d["tags"])]
        assert with_waf_version, "waf.config_errors missing 'waf_version:<version>' tag"

        with_action_tag = [d for d in waf_config_errors_series if "action:init" in d["tags"]]
        assert with_action_tag, "waf.config_errors missing 'action:init' tag"


@scenarios.appsec_missing_rules
@features.threats_configuration
class Test_MissingRules:
    """AppSec do not report anything if rule file is missing"""

    def setup_c04(self):
        self.r_1 = weblog.get("/", headers={"User-Agent": "Arachni/v1"})
        self.r_2 = weblog.get("/waf", params={"attack": "<script>"})

    def test_c04(self):
        for r in [self.r_1, self.r_2]:
            assert r.status_code == 200
            # Appsec does not catch any attack
            interfaces.library.assert_no_appsec_event(r)


# Basically the same test as Test_MissingRules, and will be called by the same scenario (save CI time)
@scenarios.appsec_custom_rules
@features.threats_configuration
class Test_ConfRuleSet:
    """AppSec support env var DD_APPSEC_RULES"""

    def setup_requests(self):
        self.r_1 = weblog.get("/waf", headers={"User-Agent": "Arachni/v1"})
        self.r_2 = weblog.get("/waf", headers={"attack": "dedicated-value-for-testing-purpose"})

    def test_requests(self):
        """Appsec does not catch any attack"""
        interfaces.library.assert_no_appsec_event(self.r_1)
        interfaces.library.assert_waf_attack(self.r_2, pattern="dedicated-value-for-testing-purpose")

    def test_log(self):
        # Check if it's implemented for the weblog variant
        if context.library == "java":
            stdout.assert_presence(r"AppSec is FULLY_ENABLED with (ddwaf|powerwaf)")
        # Check there is no error reported in logs
        stdout.assert_absence("AppSec could not read the rule file")
        stdout.assert_absence("failed to parse rule")
        stdout.assert_absence("WAF initialization failed")


@scenarios.appsec_custom_rules
@features.threats_configuration
@features.serialize_waf_rules_without_limiting_their_sizes
class Test_NoLimitOnWafRules:
    """Serialize WAF rules without limiting their sizes"""

    def setup_main(self):
        self.r_1 = weblog.get("/waf", headers={"attack": "first_pattern_of_a_very_long_list"})
        self.r_2 = weblog.get("/waf", headers={"attack": "last_pattern_of_a_very_long_list"})

    def test_main(self):
        interfaces.library.assert_waf_attack(self.r_1, pattern="first_pattern_of_a_very_long_list")
        interfaces.library.assert_waf_attack(self.r_2, pattern="last_pattern_of_a_very_long_list")
