# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, weblog, interfaces, bug, scenarios, features, waf_rules, missing_feature
from utils._context._scenarios.dynamic import dynamic_scenario



@bug(context.library == "python@1.1.0", reason="APMRP-360")
@features.appsec_response_blocking
class Test_404:
    """Appsec WAF misc tests"""

    def setup_404(self):
        self.r = weblog.get("/path_that_doesn't_exists/", headers={"User-Agent": "Arachni/v1"})

    @bug(library="java", weblog_variant="spring-boot-openliberty", reason="APPSEC-6583")
    def test_404(self):
        """AppSec WAF catches attacks, even on 404"""

        assert self.r.status_code == 404
        interfaces.library.assert_waf_attack(
            self.r,
            rule=waf_rules.security_scanner.ua0_600_12x,
            pattern="Arachni/v",
            address="server.request.headers.no_cookies",
            key_path=["user-agent"],
        )


@dynamic_scenario(mandatory={"DD_APPSEC_RULES": "/appsec_custom_rules.json"})
@features.appsec_blocking_action
class Test_MultipleHighlight:
    """Appsec reports multiple attacks on same request"""

    def setup_multiple_hightlight(self):
        self.r = weblog.get("/waf", params={"value": "highlight1 highlight2"})

    def test_multiple_hightlight(self):
        """Rule with multiple condition are reported on all conditions"""
        interfaces.library.assert_waf_attack(self.r, "multiple_highlight_rule", patterns=["highlight1", "highlight2"])


@features.appsec_blocking_action
class Test_MultipleAttacks:
    """If several attacks are sent threw one requests, all of them are reported"""

    def setup_basic(self):
        self.r_basic = weblog.get("/waf/", headers={"User-Agent": "/../"}, params={"key": "appscan_fingerprint"})

    @missing_feature(
        context.library < "nodejs@5.57.0" and context.weblog_variant == "fastify",
        reason="Query string not supported yet",
    )
    def test_basic(self):
        """Basic test with more than one attack"""
        interfaces.library.assert_waf_attack(self.r_basic, pattern="/../")
        interfaces.library.assert_waf_attack(self.r_basic, pattern="appscan_fingerprint")

    def setup_same_source(self):
        self.r_same_source = weblog.get(
            "/waf/", headers={"User-Agent": "/../", "random-key": "acunetix-user-agreement"}
        )

    def test_same_source(self):
        """Test with more than one attack in headers"""
        interfaces.library.assert_waf_attack(self.r_same_source, pattern="acunetix-user-agreement")
        interfaces.library.assert_waf_attack(self.r_same_source, pattern="/../")

    def setup_same_location(self):
        self.r_same_location = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1 and /../"})

    def test_same_location(self):
        """Test with more than one attack in a unique property"""
        interfaces.library.assert_waf_attack(self.r_same_location, pattern="/../")
        interfaces.library.assert_waf_attack(self.r_same_location, pattern="Arachni/v")


@features.waf_features
class Test_CorrectOptionProcessing:
    """Check that the case sensitive option is properly processed"""

    def setup_main(self):
        self.r_match = weblog.get("/waf/", params={"x-attack": "QUERY_STRING"})
        self.r_no_match = weblog.get("/waf/", params={"x-attack": "query_string"})

    def test_main(self):
        interfaces.library.assert_waf_attack(self.r_match)
        interfaces.library.assert_no_appsec_event(self.r_no_match)
