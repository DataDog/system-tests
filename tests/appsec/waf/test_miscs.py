# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, BaseTestCase, interfaces, skipif
from .utils import rules


@skipif(not context.appsec_is_released, reason=context.appsec_not_released_reason)
class Test_404(BaseTestCase):
    """ Appsec WAF misc tests """

    def test_404(self):
        """ AppSec WAF catches attacks, even on 404"""

        r = self.weblog_get("/path_that_doesn't_exists/", headers={"User-Agent": "Arachni/v1"})
        assert r.status_code == 404
        interfaces.library.assert_waf_attack(
            r,
            rule_id=rules.security_scanner.ua0_600_12x,
            pattern="Arachni/v",
            address="server.request.headers.no_cookies",
        )


@skipif(not context.appsec_is_released, reason=context.appsec_not_released_reason)
class Test_MultipleHighlight(BaseTestCase):
    """ Appsec WAF misc tests """

    @skipif(context.library == "dotnet", reason="known bug?")
    @skipif(context.library == "java", reason="known bug: under Valentin's investigations")
    def test_multiple_hightlight(self):
        """Rule with multiple condition are reported on all conditions"""
        r = self.weblog_get("/waf", params={"value": "processbuilder unmarshaller"})
        interfaces.library.assert_waf_attack(
            r, rule_id=rules.java_code_injection.crs_944_110, pattern=["processbuilder", "unmarshaller"]
        )


@skipif(not context.appsec_is_released, reason=context.appsec_not_released_reason)
@skipif(context.library == "dotnet", reason="missing feature: behavior not yet specified")
@skipif(context.library == "java", reason="missing feature: behavior not yet specified")
class Test_MultipleAttacks(BaseTestCase):
    """If several attacks are sent threw one requests, all of them are reported"""

    def test_basic(self):
        """Basic test with more than one attack"""
        r = self.weblog_get("/waf/", headers={"User-Agent": "Arachni/v1"}, params={"key": "appscan_fingerprint"})
        interfaces.library.assert_waf_attack(r, rules.security_scanner.ua0_600_12x, pattern="Arachni/v")
        interfaces.library.assert_waf_attack(r, rules.security_scanner.crs_913_120, pattern="appscan_fingerprint")

    def test_same_source(self):
        """Test with more than one attack in headers"""
        r = self.weblog_get("/waf/", headers={"User-Agent": "Arachni/v1", "random-key": "acunetix-user-agreement"})
        interfaces.library.assert_waf_attack(r, rules.security_scanner.crs_913_110, pattern="acunetix-user-agreement")
        interfaces.library.assert_waf_attack(r, rules.security_scanner.ua0_600_12x, pattern="Arachni/v")

    def test_same_location(self):
        """Test with more than one attack in a unique property"""
        r = self.weblog_get("/waf/", headers={"User-Agent": "Arachni/v1 and /../"})
        interfaces.library.assert_waf_attack(r, rules.lfi.crs_930_100, pattern="/../")
        interfaces.library.assert_waf_attack(r, rules.security_scanner.ua0_600_12x, pattern="Arachni/v")


# TODO :
# * /waf?arg=value&arg=attack
# * /waf?arg=attack&arg=value
# * some on POST url encoded
