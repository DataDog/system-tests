# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, BaseTestCase, interfaces, released, bug, irrelevant, missing_feature
from .utils import rules
import pytest


if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@released(golang="1.36.0" if context.weblog_variant in ["echo", "chi"] else "1.34.0")
@released(dotnet="1.28.6", java="0.87.0", nodejs="2.0.0", php_appsec="0.1.0", python="?")
@missing_feature(context.library <= "golang@1.36.2" and context.weblog_variant == "gin")
class Test_404(BaseTestCase):
    """ Appsec WAF misc tests """

    def test_404(self):
        """ AppSec WAF catches attacks, even on 404"""

        r = self.weblog_get("/path_that_doesn't_exists/", headers={"User-Agent": "Arachni/v1"})
        assert r.status_code == 404
        interfaces.library.assert_waf_attack(
            r,
            rule=rules.security_scanner.ua0_600_12x,
            pattern="Arachni/v",
            address="server.request.headers.no_cookies",
            key_path=["user-agent"],
        )


# Not yet specified
@released(golang="1.36.0", dotnet="2.3.0", java="0.95.0", nodejs="2.0.0", php_appsec="0.2.0", python="?", ruby="?")
@missing_feature(context.library <= "golang@1.36.2" and context.weblog_variant == "gin")
class Test_MultipleHighlight(BaseTestCase):
    """ Appsec reports multiple attacks on same request """

    def test_multiple_hightlight(self):
        """Rule with multiple condition are reported on all conditions"""
        r = self.weblog_get("/waf", params={"value": "processbuilder unmarshaller"})
        interfaces.library.assert_waf_attack(
            r, rules.java_code_injection.crs_944_110, patterns=["processbuilder", "unmarshaller"]
        )


@released(golang="1.35.0")
@released(dotnet="2.1.0", java="0.92.0", nodejs="2.0.0", php_appsec="0.1.0", python="?", ruby="0.54.2")
@missing_feature(context.library <= "golang@1.36.2" and context.weblog_variant == "gin")
class Test_MultipleAttacks(BaseTestCase):
    """If several attacks are sent threw one requests, all of them are reported"""

    def test_basic(self):
        """Basic test with more than one attack"""
        r = self.weblog_get("/waf/", headers={"User-Agent": "/../"}, params={"key": "appscan_fingerprint"})
        interfaces.library.assert_waf_attack(r, rules.lfi.crs_930_100, pattern="/../")
        interfaces.library.assert_waf_attack(r, rules.security_scanner.crs_913_120, pattern="appscan_fingerprint")

    def test_same_source(self):
        """Test with more than one attack in headers"""
        r = self.weblog_get("/waf/", headers={"User-Agent": "/../", "random-key": "acunetix-user-agreement"})
        interfaces.library.assert_waf_attack(r, rules.security_scanner.crs_913_110, pattern="acunetix-user-agreement")
        interfaces.library.assert_waf_attack(r, rules.lfi.crs_930_100, pattern="/../")

    def test_same_location(self):
        """Test with more than one attack in a unique property"""
        r = self.weblog_get("/waf/", headers={"User-Agent": "Arachni/v1 and /../"})
        interfaces.library.assert_waf_attack(r, rules.lfi.crs_930_100, pattern="/../")
        interfaces.library.assert_waf_attack(r, rules.security_scanner.ua0_600_12x, pattern="Arachni/v")


@bug(library="php")
class Test_NoWafTimeout(BaseTestCase):
    """ With an high value of DD_APPSEC_WAF_TIMEOUT, there is no WAF timeout"""

    def test_main(self):
        interfaces.library_stdout.assert_absence("Ran out of time while running flow")  # PHP version


# TODO :
# * /waf?arg=value&arg=attack
# * /waf?arg=attack&arg=value
# * some on POST url encoded
