# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import pytest

from utils import context, weblog, interfaces, released, bug, coverage, missing_feature
from .utils import rules


if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@released(golang={"gin": "1.37.0", "echo": "1.36.0", "chi": "1.36.0", "*": "1.34.0"})
@released(dotnet="1.28.6", java="0.87.0", nodejs="2.0.0", php_appsec="0.1.0", python="1.1.0rc2.dev")
@bug(library="python@1.1.0", reason="a PR was not included in the release")
@missing_feature(context.weblog_variant == "spring-boot-native", reason="GraalVM. Tracing support only")
@missing_feature(context.weblog_variant == "spring-boot-3-native", reason="GraalVM. Tracing support only")
@coverage.basic
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
            rule=rules.security_scanner.ua0_600_12x,
            pattern="Arachni/v",
            address="server.request.headers.no_cookies",
            key_path=["user-agent"],
        )


@released(golang="1.37.0" if context.weblog_variant == "gin" else "1.36.0")
@released(dotnet="2.3.0", java="0.95.0", nodejs="2.0.0")
@released(php_appsec="0.2.0", python="1.2.1", ruby="1.0.0.beta1")
@missing_feature(context.weblog_variant == "spring-boot-native", reason="GraalVM. Tracing support only")
@missing_feature(context.weblog_variant == "spring-boot-3-native", reason="GraalVM. Tracing support only")
@coverage.basic
class Test_MultipleHighlight:
    """Appsec reports multiple attacks on same request"""

    def setup_multiple_hightlight(self):
        self.r = weblog.get("/waf", params={"value": "processbuilder unmarshaller"})

    def test_multiple_hightlight(self):
        """Rule with multiple condition are reported on all conditions"""
        interfaces.library.assert_waf_attack(
            self.r, rules.java_code_injection.crs_944_110, patterns=["processbuilder", "unmarshaller"]
        )


@released(golang="1.37.0" if context.weblog_variant == "gin" else "1.35.0")
@released(dotnet="2.1.0", java="0.92.0", nodejs="2.0.0", php_appsec="0.1.0", python="1.2.1", ruby="0.54.2")
@missing_feature(context.weblog_variant == "spring-boot-native", reason="GraalVM. Tracing support only")
@missing_feature(context.weblog_variant == "spring-boot-3-native", reason="GraalVM. Tracing support only")
@coverage.good
class Test_MultipleAttacks:
    """If several attacks are sent threw one requests, all of them are reported"""

    def setup_basic(self):
        self.r_basic = weblog.get("/waf/", headers={"User-Agent": "/../"}, params={"key": "appscan_fingerprint"})

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


@missing_feature(library="php")
@coverage.basic
class Test_NoWafTimeout:
    """With an high value of DD_APPSEC_WAF_TIMEOUT, there is no WAF timeout"""

    @missing_feature(context.weblog_variant == "spring-boot-native", reason="GraalVM. Tracing support only")
    @missing_feature(context.weblog_variant == "spring-boot-3-native", reason="GraalVM. Tracing support only")
    def test_main(self):
        interfaces.library_stdout.assert_absence("Ran out of time while running flow")
