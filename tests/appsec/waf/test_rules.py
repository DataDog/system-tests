# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Exhaustive tests on WAF default rule set"""

from utils import context, weblog, interfaces, bug, missing_feature, irrelevant, flaky, features, waf_rules


@features.waf_rules
class Test_Scanners:
    """Appsec WAF tests on scanners rules"""

    def setup_scanners(self):
        self.r_1 = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})
        self.r_2 = weblog.get("/waf/", headers={"random-key": "acunetix-user-agreement"})
        self.r_3 = weblog.get("/waf/", params={"key": "appscan_fingerprint"})

    def test_scanners(self):
        """AppSec catches attacks from scanners"""
        interfaces.library.assert_waf_attack(self.r_1, waf_rules.security_scanner.ua0_600_12x)
        interfaces.library.assert_waf_attack(self.r_2, waf_rules.security_scanner.crs_913_110)
        interfaces.library.assert_waf_attack(self.r_3, waf_rules.security_scanner.crs_913_120)


@features.waf_rules
class Test_HttpProtocol:
    """Appsec WAF tests on HTTP protocol rules"""

    def setup_http_protocol(self):
        self.r_1 = weblog.get("/waf/", params={"key": ".cookie;domain="})

    @bug(context.library < "dotnet@2.1.0", reason="APMRP-360")
    @bug(context.library < "java@0.98.1", reason="APMRP-360")
    def test_http_protocol(self):
        """AppSec catches attacks by violation of HTTP protocol in encoded cookie value"""
        interfaces.library.assert_waf_attack(self.r_1, waf_rules.http_protocol_violation.crs_943_100)

    def setup_http_protocol2(self):
        self.r_1 = weblog.get("/waf/", params={"key": "get e http/1"})
        self.r_2 = weblog.get("/waf/", params={"key": "\nset-cookie:"})

    def test_http_protocol2(self):
        """AppSec catches attacks by violation of HTTP protocol"""
        interfaces.library.assert_waf_attack(self.r_1, waf_rules.http_protocol_violation.crs_921_110)
        interfaces.library.assert_waf_attack(self.r_2, waf_rules.http_protocol_violation.crs_921_160)


@features.waf_rules
class Test_LFI:
    """Appsec WAF tests on LFI rules"""

    def setup_lfi(self):
        self.r_1 = weblog.get("/waf/", headers={"x-attack": "/../"})
        self.r_2 = weblog.get("/waf/0x5c0x2e0x2e0x2f")
        self.r_3 = weblog.get("/waf/", params={"attack": "/.htaccess"})

    def test_lfi(self):
        """AppSec catches LFI attacks"""
        interfaces.library.assert_waf_attack(self.r_1, waf_rules.lfi)
        interfaces.library.assert_waf_attack(self.r_2, waf_rules.lfi.crs_930_100)
        interfaces.library.assert_waf_attack(self.r_3, waf_rules.lfi.crs_930_120)

    def setup_lfi_percent_2f(self):
        self.r_4 = weblog.get("/waf/%2e%2e%2f")

    # AH00026: found %2f (encoded '/') in URI path (/waf/%2e%2e%2f), returning 404
    @irrelevant(library="php", weblog_variant="apache-mod-8.0")
    @irrelevant(library="python", weblog_variant="django-poc")
    def test_lfi_percent_2f(self):
        """Appsec catches encoded LFI attacks"""
        interfaces.library.assert_waf_attack(self.r_4, waf_rules.lfi)

    def setup_lfi_in_path(self):
        self.r_5 = weblog.get("/waf/..")

    @bug(context.library < "java@0.92.0", reason="APMRP-360")
    @flaky(context.library >= "java@1.42.1", reason="APPSEC-55828")
    @irrelevant(library="python", weblog_variant="django-poc")
    @irrelevant(library="dotnet", reason="lfi patterns are always filtered by the host web-server")
    @irrelevant(
        context.weblog_variant in ("akka-http", "play") and context.library == "java", reason="path is normalized to /"
    )
    def test_lfi_in_path(self):
        """AppSec catches LFI attacks in URL path like /.."""
        interfaces.library.assert_waf_attack(self.r_5, waf_rules.lfi.crs_930_110)


@features.waf_rules
class Test_RFI:
    """Appsec WAF tests on RFI rules"""

    def setup_rfi(self):
        self.r_1 = weblog.get("/waf/", params={"attack": "mosConfig_absolute_path=file://"})
        self.r_2 = weblog.get("/waf/", params={"attack": "file://rfi?"})

    def test_rfi(self):
        """Appsec WAF detects remote file injection attacks"""
        interfaces.library.assert_waf_attack(self.r_1, waf_rules.rfi.crs_931_110)
        interfaces.library.assert_waf_attack(self.r_2, waf_rules.rfi.crs_931_120)


@features.waf_rules
class Test_CommandInjection:
    """Appsec WAF tests on Command injection rules"""

    def setup_command_injection(self):
        self.r_1 = weblog.get("/waf/", params={"x-attack": "$pwd"})
        self.r_2 = weblog.get("/waf/", headers={"x-attack": "() {"})
        self.r_3 = weblog.get("/waf/", headers={"x-file-name": "routing.yml"})
        self.r_4 = weblog.get("/waf/", headers={"x-attack": "|type %d%\\d.ini|"})
        self.r_5 = weblog.get("/waf/", headers={"x-attack": "|cat /etc/passwd|"})
        self.r_6 = weblog.get("/waf/", headers={"x-attack": "|timeout /t 1|"})

    def test_command_injection(self):
        """Appsec WAF detects command injection attacks"""
        interfaces.library.assert_waf_attack(self.r_1, waf_rules.command_injection.crs_932_160)
        interfaces.library.assert_waf_attack(self.r_2, waf_rules.command_injection.crs_932_171)
        interfaces.library.assert_waf_attack(self.r_3, waf_rules.command_injection.crs_932_180)
        interfaces.library.assert_waf_attack(self.r_4, waf_rules.command_injection.sqr_000_008)
        interfaces.library.assert_waf_attack(self.r_5, waf_rules.command_injection.sqr_000_009)
        interfaces.library.assert_waf_attack(self.r_6, waf_rules.command_injection.sqr_000_010)


@features.waf_rules
class Test_PhpCodeInjection:
    """Appsec WAF tests on PHP injection rules"""

    def setup_php_code_injection(self):
        self.r_1 = weblog.get("/waf/", headers={"x-file-name": ".php."})
        self.r_2 = weblog.get("/waf/", params={"x-attack": "$globals"})
        self.r_3 = weblog.get("/waf/", params={"x-attack": "AUTH_TYPE"})
        self.r_4 = weblog.get("/waf/", params={"x-attack": "php://fd"})
        self.r_5 = weblog.get("/waf/", params={"x-attack": "bzdecompress"})
        self.r_6 = weblog.get("/waf/", params={"x-attack": "rar://"})

    def test_php_code_injection(self):
        """Appsec WAF detects unrestricted file upload attacks"""
        interfaces.library.assert_waf_attack(self.r_1, waf_rules.unrestricted_file_upload.crs_933_111)
        interfaces.library.assert_waf_attack(self.r_2, waf_rules.php_code_injection.crs_933_130)
        interfaces.library.assert_waf_attack(self.r_3, waf_rules.php_code_injection.crs_933_131)
        interfaces.library.assert_waf_attack(self.r_4, waf_rules.php_code_injection.crs_933_140)
        interfaces.library.assert_waf_attack(self.r_5, waf_rules.php_code_injection.crs_933_150)
        interfaces.library.assert_waf_attack(self.r_6, waf_rules.php_code_injection.crs_933_200)

    def setup_php_code_injection_bug(self):
        self.r_7 = weblog.get("/waf/", params={"x-attack": " var_dump ()"})
        self.r_8 = weblog.get("/waf/", params={"x-attack": 'o:4:"x":5:{d}'})

    @missing_feature(context.library < "golang@1.36.0" and context.weblog_variant == "echo")
    def test_php_code_injection_bug(self):
        """Appsec WAF detects other php injection rules"""
        interfaces.library.assert_waf_attack(self.r_7, waf_rules.php_code_injection.crs_933_160)
        interfaces.library.assert_waf_attack(self.r_8, waf_rules.php_code_injection.crs_933_170)


@features.waf_rules
class Test_JsInjection:
    """Appsec WAF tests on Js Injection rules"""

    def setup_js_injection(self):
        self.r_1 = weblog.get("/waf/", params={"key": "this.constructor"})
        self.r_2 = weblog.get("/waf/", params={"key": "require('.')"})

    def test_js_injection(self):
        """AppSec catches JS code injection"""
        interfaces.library.assert_waf_attack(self.r_1, waf_rules.js_code_injection.crs_934_100)
        interfaces.library.assert_waf_attack(self.r_2, waf_rules.js_code_injection.sqr_000_002)


@features.waf_rules
class Test_XSS:
    """Appsec WAF tests on XSS rules"""

    def setup_xss(self):
        self.requests = [
            weblog.get("/waf/", params={"key": "<script>"}),
            weblog.get("/waf/", params={"key": "javascript:x"}),
            weblog.get("/waf/", params={"key": "vbscript:x"}),
            weblog.get("/waf/", params={"key": "<EMBED+src="}),
            weblog.get("/waf/", params={"key": "<importimplementation="}),
            weblog.get("/waf/", params={"key": "<LINK+href="}),
            weblog.get("/waf/", params={"key": "<BASE+href="}),
            weblog.get("/waf/", params={"key": "<APPLET+"}),
            weblog.get("/waf/", params={"key": "<OBJECT+type="}),
            weblog.get("/waf/", params={"key": "!![]"}),
            weblog.get("/waf/", params={"key": "+ADw->|<+AD$-"}),
        ]

    def test_xss(self):
        """AppSec catches XSS attacks"""
        for r in self.requests:
            interfaces.library.assert_waf_attack(r, waf_rules.xss)


@features.waf_rules
class Test_SQLI:
    """Appsec WAF tests on SQLI rules"""

    def setup_sqli(self):
        self.r_1 = weblog.get("/waf/", params={"value": "sleep()"})

    def test_sqli(self):
        interfaces.library.assert_waf_attack(self.r_1, waf_rules.sql_injection.crs_942_160)

    def setup_sqli2(self):
        self.r_3 = weblog.get("/waf/", params={"value": "alter d char set f"})
        self.r_4 = weblog.get("/waf/", params={"value": "merge using("})

    @flaky(context.library <= "php@0.68.2", reason="APMRP-360")
    def test_sqli2(self):
        """Other SQLI patterns"""
        interfaces.library.assert_waf_attack(self.r_3, waf_rules.sql_injection.crs_942_240)
        interfaces.library.assert_waf_attack(self.r_4, waf_rules.sql_injection.crs_942_250)


@features.waf_rules
class Test_NoSqli:
    """Appsec WAF tests on NoSQLi rules"""

    def setup_nosqli_keys(self):
        self.r_3 = weblog.get("/waf/", params={"[$ne]": "value"})
        self.r_4 = weblog.get("/waf/", params={"$nin": "value"})

    @missing_feature(context.library in ["php"], reason="Need to use last WAF version")
    @missing_feature(context.library < "java@0.96.0", reason="Was using a too old WAF version")
    @irrelevant(library="nodejs", reason="brackets are interpreted as arrays and thus truncated")
    def test_nosqli_keys(self):
        """AppSec catches NoSQLI attacks in keys"""
        interfaces.library.assert_waf_attack(self.r_3, waf_rules.nosql_injection)
        interfaces.library.assert_waf_attack(self.r_4, waf_rules.nosql_injection)


@features.waf_rules
class Test_JavaCodeInjection:
    """Appsec WAF tests on Java code injection rules"""

    def setup_java_code_injection(self):
        self.r_1 = weblog.get("/waf/", params={"value": "java.lang.runtime"})
        self.r_2 = weblog.get("/waf/", params={"value": "unmarshaller processbuilder"})
        self.r_3 = weblog.get("/waf/", params={"value": "java.beans.xmldecode"})

    def test_java_code_injection(self):
        """AppSec catches java code injections"""
        interfaces.library.assert_waf_attack(self.r_1, waf_rules.java_code_injection)
        interfaces.library.assert_waf_attack(self.r_2, waf_rules.java_code_injection.crs_944_110)
        interfaces.library.assert_waf_attack(self.r_3, waf_rules.java_code_injection.crs_944_130)


@features.waf_rules
class Test_SSRF:
    """Appsec WAF tests on SSRF rules"""

    def setup_ssrf(self):
        self.r = weblog.get("/waf/", params={"value": "metadata.goog/"})

    def test_ssrf(self):
        """AppSec catches SSRF attacks"""
        interfaces.library.assert_waf_attack(self.r, waf_rules.ssrf.sqr_000_001)


@features.waf_rules
class Test_DiscoveryScan:
    """AppSec WAF Tests on Discovery Scan rules"""

    def setup_security_scan(self):
        self.r1 = weblog.get("/etc/something")
        self.r2 = weblog.get("/mysql")
        self.r3 = weblog.get("/myadmin")
        self.r4 = weblog.get("/readme.md")
        self.r5 = weblog.get("/web-inf/web.xml")
        self.r6 = weblog.get("/src/main.rb")
        self.r7 = weblog.get("/access.log")
        self.r8 = weblog.get("/mykey.pem")
        self.r9 = weblog.get("/logs.tar")
        self.r10 = weblog.get("/administrator/components/component.php")
        self.r11 = weblog.get("/login.pwd")

    @bug(context.library < "java@0.98.0" and context.weblog_variant == "spring-boot-undertow", reason="APMRP-360")
    @bug(library="java", weblog_variant="spring-boot-openliberty", reason="APPSEC-6583")
    def test_security_scan(self):
        """AppSec WAF catches Discovery scan"""

        interfaces.library.assert_waf_attack(self.r1, waf_rules.security_scanner.nfd_000_001)
        interfaces.library.assert_waf_attack(self.r2, waf_rules.security_scanner.nfd_000_001)
        interfaces.library.assert_waf_attack(self.r3, waf_rules.security_scanner.nfd_000_001)
        interfaces.library.assert_waf_attack(self.r4, waf_rules.security_scanner.nfd_000_002)
        interfaces.library.assert_waf_attack(self.r5, waf_rules.security_scanner.nfd_000_003)
        interfaces.library.assert_waf_attack(self.r6, waf_rules.security_scanner.nfd_000_004)
        interfaces.library.assert_waf_attack(self.r7, waf_rules.security_scanner.nfd_000_005)
        interfaces.library.assert_waf_attack(self.r8, waf_rules.security_scanner.nfd_000_006)

        # need some match for those two rules
        # interfaces.library.assert_waf_attack(self.r9, rules.security_scanner.nfd_000_007)
        # interfaces.library.assert_waf_attack(self.r10, rules.security_scanner.nfd_000_008)

        interfaces.library.assert_waf_attack(self.r11, waf_rules.security_scanner.nfd_000_009)
