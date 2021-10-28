# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Exhaustive tests on WAF default rule set"""

from utils import context, BaseTestCase, interfaces, released, bug, missing_feature
from .utils import rules
import pytest


if context.weblog_variant == "echo-poc":
    pytestmark = pytest.mark.skip("not relevant: echo is not instrumented")
elif context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@released(golang="1.33.1", dotnet="1.28.6", java="0.87.0", php="?", python="?", ruby="0.51.0")
@missing_feature(library="nodejs", reason="query string not yet supported")
class Test_Scanners(BaseTestCase):
    """ Appsec WAF tests on scanners rules """

    def test_scanners(self):
        """ AppSec catches attacks from scanners"""
        r = self.weblog_get("/waf/", headers={"User-Agent": "Arachni/v1"})
        interfaces.library.assert_waf_attack(r, rules.security_scanner.ua0_600_12x)

        r = self.weblog_get("/waf", headers={"random-key": "acunetix-user-agreement"})
        interfaces.library.assert_waf_attack(r, rules.security_scanner.crs_913_110)

        r = self.weblog_get("/waf", params={"key": "appscan_fingerprint"})
        interfaces.library.assert_waf_attack(r, rules.security_scanner.crs_913_120)


@released(golang="?", php="?", python="?", ruby="0.51.0")
@missing_feature(library="nodejs", reason="query string not yet supported")
class Test_HttpProtocol(BaseTestCase):
    """ Appsec WAF tests on HTTP protocol rules """

    @bug(library="dotnet", reason="APPSEC-1407")
    @bug(library="java", reason="under Valentin's investigations")
    @bug(library="ruby", reason="? need to be investiged")
    def test_http_protocol(self):
        """ AppSec catches attacks by violation of HTTP protocol"""
        r = self.weblog_get("/waf", cookies={"key": ".cookie-;domain="})
        interfaces.library.assert_waf_attack(r, rules.http_protocol_violation.crs_943_100)

    @missing_feature(library="ruby", reason="query string is not sent as decoded map")
    def test_http_protocol2(self):
        """ AppSec catches attacks by violation of HTTP protocol"""
        r = self.weblog_get("/waf", params={"key": "get e http/1"})
        interfaces.library.assert_waf_attack(r, rules.http_protocol_violation.crs_921_110)

        r = self.weblog_get("/waf", params={"key": "\n :"})
        interfaces.library.assert_waf_attack(r, rules.http_protocol_violation.crs_921_160)


@released(golang="?", php="?", python="?", ruby="0.51.0")
@missing_feature(library="nodejs", reason="query string not yet supported")
class Test_LFI(BaseTestCase):
    """ Appsec WAF tests on LFI rules """

    def test_lfi(self):
        """ AppSec catches LFI attacks"""
        r = self.weblog_get("/waf", headers={"x-attack": "/../"})
        interfaces.library.assert_waf_attack(r, rule_id=rules.lfi.crs_930_100)

        r = self.weblog_get("/waf/0x5c0x2e0x2e0x2f")
        interfaces.library.assert_waf_attack(r, rule_id=rules.lfi.crs_930_100)

        r = self.weblog_get("/waf/%2e%2e%2f")
        interfaces.library.assert_waf_attack(r, rule_id=rules.lfi.crs_930_100)

        r = self.weblog_get("/waf/", params={"attack": ".htaccess"})
        interfaces.library.assert_waf_attack(r, rule_id=rules.lfi.crs_930_120)

    @bug(library="dotnet", reason="APPSEC-1405")
    @bug(library="java", reason="under Valentin's investigations")
    @bug(library="golang", reason="? may be not supported by framework")
    @bug(library="ruby", reason="? may be not supported by framework")
    def test_lfi_in_path(self):
        """ AppSec catches LFI attacks in URL path like /.."""
        r = self.weblog_get("/waf/..")
        interfaces.library.assert_waf_attack(r, rule_id=rules.lfi.crs_930_110)


@released(golang="1.33.1", dotnet="1.28.6", java="0.87.0", php="?", python="?", ruby="0.51.0")
@missing_feature(library="nodejs", reason="query string not yet supported")
class Test_RFI(BaseTestCase):
    """ Appsec WAF tests on RFI rules """

    @missing_feature(library="ruby", reason="query string is not sent as decoded map")
    def test_rfi(self):
        """ Appsec WAF detects remote file injection attacks """
        r = self.weblog_get("/waf/", params={"attack": "mosConfig_absolute_path=file://"})
        interfaces.library.assert_waf_attack(r, rules.rfi.crs_931_110)

        r = self.weblog_get("/waf/", params={"attack": "file?"})
        interfaces.library.assert_waf_attack(r, rules.rfi.crs_931_120)


@released(golang="1.33.1", dotnet="1.28.6", java="0.87.0", php="?", python="?", ruby="0.51.0")
@missing_feature(library="nodejs", reason="query string not yet supported")
class Test_CommandInjection(BaseTestCase):
    """ Appsec WAF tests on Command injection rules """

    def test_command_injection(self):
        """ Appsec WAF detects command injection attacks """
        r = self.weblog_get("/waf/", cookies={"x-attack": "$pwd"})
        interfaces.library.assert_waf_attack(r, rule_id=rules.command_injection.crs_932_160)

        r = self.weblog_get("/waf/", headers={"x-attack": "() {"})
        interfaces.library.assert_waf_attack(r, rule_id=rules.command_injection.crs_932_171)

        r = self.weblog_get("/waf/", headers={"x-file-name": "routing.yml"})
        interfaces.library.assert_waf_attack(r, rule_id=rules.command_injection.crs_932_180)

        r = self.weblog_get("/waf/", headers={"x-attack": "|type %d%\\d.ini|"})
        interfaces.library.assert_waf_attack(r, rule_id=rules.command_injection.sqr_000_008)

        r = self.weblog_get("/waf/", headers={"x-attack": "|cat /etc/passwd|"})
        interfaces.library.assert_waf_attack(r, rule_id=rules.command_injection.sqr_000_009)

        r = self.weblog_get("/waf/", headers={"x-attack": "|timeout /t 1|"})
        interfaces.library.assert_waf_attack(r, rule_id=rules.command_injection.sqr_000_010)


@released(golang="1.33.1", java="0.87.0", php="?", python="?", ruby="0.51.0")
@missing_feature(library="nodejs", reason="query string not yet supported")
class Test_PhpCodeInjection(BaseTestCase):
    """ Appsec WAF tests on PHP injection rules """

    def test_php_code_injection(self):
        """ Appsec WAF detects unrestricted file upload attacks """
        r = self.weblog_get("/waf/", headers={"x-file-name": ".php."})
        interfaces.library.assert_waf_attack(r, rule_id=rules.unrestricted_file_upload.crs_933_111)

        r = self.weblog_get("/waf/", cookies={"x-attack": "$globals"})
        interfaces.library.assert_waf_attack(r, rule_id=rules.php_code_injection.crs_933_130)

        r = self.weblog_get("/waf/", cookies={"x-attack": "AUTH_TYPE"})
        interfaces.library.assert_waf_attack(r, rule_id=rules.php_code_injection.crs_933_131)

        r = self.weblog_get("/waf/", cookies={"x-attack": "php://fd"})
        interfaces.library.assert_waf_attack(r, rule_id=rules.php_code_injection.crs_933_140)

        r = self.weblog_get("/waf/", params={"x-attack": "bzdecompress"})
        interfaces.library.assert_waf_attack(r, rule_id=rules.php_code_injection.crs_933_150)

        r = self.weblog_get("/waf/", cookies={"x-attack": "rar://"})
        interfaces.library.assert_waf_attack(r, rule_id=rules.php_code_injection.crs_933_200)

    @bug(library="dotnet", reason="APPSEC-1407 and APPSEC-1408")
    @bug(library="golang")
    def test_php_code_injection_bug(self):
        """ Appsec WAF detects other php injection rules """
        r = self.weblog_get("/waf/", cookies={"x-attack": " var_dump ()"})
        interfaces.library.assert_waf_attack(r, rule_id=rules.php_code_injection.crs_933_160)

        r = self.weblog_get("/waf/", cookies={"x-attack": 'o:4:"x":5:{d}'})
        interfaces.library.assert_waf_attack(r, rule_id=rules.php_code_injection.crs_933_170)


@released(golang="1.33.1", dotnet="1.28.6", java="0.87.0", php="?", python="?", ruby="0.51.0")
@missing_feature(library="nodejs", reason="query string not yet supported")
class Test_JsInjection(BaseTestCase):
    """ Appsec WAF tests on Js Injection rules """

    def test_js_injection(self):
        """AppSec catches JS code injection"""
        r = self.weblog_get("/waf/", params={"key": "this.constructor"})
        interfaces.library.assert_waf_attack(r, rules.js_code_injection.crs_934_100)

    @missing_feature(library="ruby", reason="query string is not sent as decoded map")
    def test_js_injection1(self):
        """AppSec catches JS code injection"""
        r = self.weblog_get("/waf/", params={"key": "require('.')"})
        interfaces.library.assert_waf_attack(r, rules.js_code_injection.sqr_000_002)


@released(golang="?", java="0.87.0", php="?", python="?", ruby="0.51.0")
@missing_feature(library="nodejs", reason="query string not yet supported")
class Test_XSS(BaseTestCase):
    """ Appsec WAF tests on XSS rules """

    def test_xss(self):
        """AppSec catches XSS attacks"""
        r = self.weblog_get("/waf/", cookies={"key": "<script>"})
        interfaces.library.assert_waf_attack(r, rules.xss.crs_941_110)

        r = self.weblog_get("/waf/", cookies={"key": "javascript:x"})
        interfaces.library.assert_waf_attack(r, rules.xss.crs_941_210)

        r = self.weblog_get("/waf/", cookies={"key": "vbscript:x"})
        interfaces.library.assert_waf_attack(r, rules.xss.crs_941_220)

        r = self.weblog_get("/waf/", cookies={"key": "<EMBED+src="})
        interfaces.library.assert_waf_attack(r, rules.xss.crs_941_230)

        r = self.weblog_get("/waf/", cookies={"key": "<importimplementation="})
        interfaces.library.assert_waf_attack(r, rules.xss.crs_941_240)

        r = self.weblog_get("/waf/", cookies={"key": "<LINK+href="})
        interfaces.library.assert_waf_attack(r, rules.xss.crs_941_270)

        r = self.weblog_get("/waf/", cookies={"key": "<BASE+href="})
        interfaces.library.assert_waf_attack(r, rules.xss.crs_941_280)

        r = self.weblog_get("/waf/", cookies={"key": "<APPLET+"})
        interfaces.library.assert_waf_attack(r, rules.xss.crs_941_290)

        r = self.weblog_get("/waf/", cookies={"key": "<OBJECT+type="})
        interfaces.library.assert_waf_attack(r, rules.xss.crs_941_300)

        r = self.weblog_get("/waf/", cookies={"key": "!![]"})
        interfaces.library.assert_waf_attack(r, rules.xss.crs_941_360)

    @bug(library="ruby", reason="need to be investiged")
    def test_xss1(self):
        """AppSec catches XSS attacks"""
        r = self.weblog_get("/waf/", cookies={"key": "+ADw->|<+AD$-"})
        interfaces.library.assert_waf_attack(r, rules.xss.crs_941_350)

    @bug(library="dotnet", reason="APPSEC-1407 and APPSEC-1408")
    def test_xss2(self):
        """Other XSS patterns, to be merged once issue are corrected"""
        r = self.weblog_get("/waf", cookies={"value": '<vmlframe src="xss">'})
        interfaces.library.assert_waf_attack(r, rules.xss.crs_941_200)


@released(golang="?", php="?", python="?", ruby="0.51.0")
@missing_feature(library="nodejs", reason="query string not yet supported")
class Test_SQLI(BaseTestCase):
    """ Appsec WAF tests on SQLI rules """

    def test_sqli(self):
        """AppSec catches SQLI attacks"""
        r = self.weblog_get("/waf", cookies={"value": "db_name("})
        interfaces.library.assert_waf_attack(r, rules.sqli.crs_942_140)

        r = self.weblog_get("/waf", cookies={"value": "sleep()"})
        interfaces.library.assert_waf_attack(r, rules.sqli.crs_942_160)

        r = self.weblog_get("/waf", cookies={"value": "/*!*/"})
        interfaces.library.assert_waf_attack(r, rules.sqli.crs_942_500)

    @missing_feature(library="ruby", reason="query string is not sent as decoded map")
    def test_sqli1(self):
        """AppSec catches SQLI attacks"""
        r = self.weblog_get("/waf", params={"value": "0000012345"})
        interfaces.library.assert_waf_attack(r, rules.sqli.crs_942_220)

    @bug(library="dotnet", reason="APPSEC-1407 and APPSEC-1408")
    def test_sqli2(self):
        """Other SQLI patterns, to be merged once issue are corrected"""
        r = self.weblog_get("/waf", cookies={"value": "alter d char set f"})
        interfaces.library.assert_waf_attack(r, rules.sqli.crs_942_240)

        r = self.weblog_get("/waf", cookies={"value": "merge using("})
        interfaces.library.assert_waf_attack(r, rules.sqli.crs_942_250)

        r = self.weblog_get("/waf", cookies={"value": "union select from"})
        interfaces.library.assert_waf_attack(r, rules.sqli.crs_942_270)

    @bug(library="dotnet", reason="APPSEC-1407 and APPSEC-1408")
    @bug(library="java", reason="under Valentin's investigations")
    @bug(library="ruby", reason="need to be investiged")
    def test_sqli3(self):
        """Other SQLI patterns, to be merged once issue are corrected"""
        r = self.weblog_get("/waf", cookies={"value": ";shutdown--"})
        interfaces.library.assert_waf_attack(r, rules.sqli.crs_942_280)


@released(golang="1.33.1", dotnet="1.28.6", java="0.87.0", php="?", python="?", ruby="0.51.0")
@missing_feature(library="nodejs", reason="query string not yet supported")
class Test_NoSqli(BaseTestCase):
    """ Appsec WAF tests on NoSQLi rules """

    def test_nosqli(self):
        """AppSec catches NoSQLI attacks"""
        r = self.weblog_get("/waf", cookies={"value": "[$ne]"})
        interfaces.library.assert_waf_attack(r, rules.nosqli.crs_942_290)

        r = self.weblog_get("/waf", headers={"x-attack": "$nin"})
        interfaces.library.assert_waf_attack(r, rules.nosqli.sqr_000_007)


@released(golang="1.33.1", dotnet="1.28.6", java="0.87.0", php="?", python="?", ruby="0.51.0")
@missing_feature(library="nodejs", reason="query string not yet supported")
class Test_JavaCodeInjection(BaseTestCase):
    """ Appsec WAF tests on Java code injection rules """

    def test_java_code_injection(self):
        """AppSec catches java code injections"""
        r = self.weblog_get("/waf", params={"value": "java.lang.runtime"})
        interfaces.library.assert_waf_attack(r, rules.java_code_injection.crs_944_100)

        r = self.weblog_get("/waf", params={"value": "processbuilder unmarshaller"})
        interfaces.library.assert_waf_attack(r, rules.java_code_injection.crs_944_110)

        r = self.weblog_get("/waf", params={"value": "java.beans.xmldecode"})
        interfaces.library.assert_waf_attack(r, rules.java_code_injection.crs_944_130)


@released(golang="1.33.1", dotnet="1.28.6", java="0.87.0", php="?", python="?", ruby="0.51.0")
@missing_feature(library="nodejs", reason="query string not yet supported")
class Test_SSRF(BaseTestCase):
    """ Appsec WAF tests on SSRF rules """

    @missing_feature(library="ruby", reason="query string is not sent as decoded map")
    def test_ssrf(self):
        """AppSec catches SSRF attacks"""
        r = self.weblog_get("/waf", params={"value": "metadata.goog/"})
        interfaces.library.assert_waf_attack(r, rules.ssrf.sqr_000_001)
