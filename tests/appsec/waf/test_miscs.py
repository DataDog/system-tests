# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import (
    context,
    weblog,
    interfaces,
    bug,
    coverage,
    missing_feature,
    scenarios,
    features,
)
from .utils import rules


@bug(context.library == "python@1.1.0", reason="a PR was not included in the release")
@coverage.basic
@features.appsec_response_blocking
class Test_404:
    """Appsec WAF misc tests"""

    def setup_404(self):
        self.r = weblog.get(
            "/path_that_doesn't_exists/", headers={"User-Agent": "Arachni/v1"}
        )

    @bug(library="java", weblog_variant="spring-boot-openliberty", reason="APPSEC-6583")
    def test_404(self):
        """AppSec WAF catches attacks, even on 404"""

        assert self.r.status_code == 404
        interfaces.library.assert_waf_attack(
            self.r,
            rule=rules.security_scanner.ua0_600_12x,
            pattern="Arachni/v",
            address="server.request.headers.no_cookies",
            key_path=["user-agent"],
        )


@scenarios.appsec_custom_rules
@coverage.basic
@features.appsec_blocking_action
class Test_MultipleHighlight:
    """Appsec reports multiple attacks on same request"""

    def setup_multiple_hightlight(self):
        self.r = weblog.get("/waf", params={"value": "highlight1 highlight2"})

    def test_multiple_hightlight(self):
        """Rule with multiple condition are reported on all conditions"""
        interfaces.library.assert_waf_attack(
            self.r, "multiple_highlight_rule", patterns=["highlight1", "highlight2"]
        )


@coverage.good
@features.appsec_blocking_action
class Test_MultipleAttacks:
    """If several attacks are sent threw one requests, all of them are reported"""

    def setup_basic(self):
        self.r_basic = weblog.get(
            "/waf/",
            headers={"User-Agent": "/../"},
            params={"key": "appscan_fingerprint"},
        )

    def test_basic(self):
        """Basic test with more than one attack"""
        interfaces.library.assert_waf_attack(self.r_basic, pattern="/../")
        interfaces.library.assert_waf_attack(
            self.r_basic, pattern="appscan_fingerprint"
        )

    def setup_same_source(self):
        self.r_same_source = weblog.get(
            "/waf/",
            headers={"User-Agent": "/../", "random-key": "acunetix-user-agreement"},
        )

    def test_same_source(self):
        """Test with more than one attack in headers"""
        interfaces.library.assert_waf_attack(
            self.r_same_source, pattern="acunetix-user-agreement"
        )
        interfaces.library.assert_waf_attack(self.r_same_source, pattern="/../")

    def setup_same_location(self):
        self.r_same_location = weblog.get(
            "/waf/", headers={"User-Agent": "Arachni/v1 and /../"}
        )

    def test_same_location(self):
        """Test with more than one attack in a unique property"""
        interfaces.library.assert_waf_attack(self.r_same_location, pattern="/../")
        interfaces.library.assert_waf_attack(self.r_same_location, pattern="Arachni/v")


@coverage.good
@features.waf_features
class Test_CorrectOptionProcessing:
    """Check that the case sensitive option is properly processed"""

    def setup_main(self):
        self.r_match = weblog.get("/waf/", params={"x-attack": "QUERY_STRING"})
        self.r_no_match = weblog.get("/waf/", params={"x-attack": "query_string"})

    def test_main(self):
        interfaces.library.assert_waf_attack(self.r_match)
        interfaces.library.assert_no_appsec_event(self.r_no_match)


@coverage.basic
@features.threats_configuration
class Test_NoWafTimeout:
    """With an high value of DD_APPSEC_WAF_TIMEOUT, there is no WAF timeout"""

    @missing_feature(
        weblog_variant="spring-boot-3-native", reason="GraalVM. Tracing support only"
    )
    def test_main(self):
        interfaces.library_stdout.assert_absence("Ran out of time while running flow")
