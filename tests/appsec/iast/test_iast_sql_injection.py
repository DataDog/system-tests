# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, interfaces, context, missing_feature, coverage, released, bug

# Weblog are ok for nodejs/express4 and java/spring-boot
@coverage.basic
@released(
    dotnet="?",
    golang="?",
    java={"spring-boot": "0.108.0", "spring-boot-jetty": "0.108.0", "spring-boot-openliberty": "0.108.0", "*": "?"},
    nodejs={"express4": "3.6.0", "*": "?"},
    php_appsec="?",
    python="?",
    ruby="?",
    cpp="?",
)
class TestIastSqlInjection(BaseTestCase):
    """Verify IAST SQL INJECTION feature"""

    EXPECTATIONS = {"java": {"LOCATION": "com.datadoghq.system_tests.springboot.iast.utils.CmdExamples"}}

    def __expected_location(self):
        expected = self.EXPECTATIONS.get(context.library.library)
        return expected.get("LOCATION") if expected else None

    @missing_feature(reason="Need to implement SQL injection detection")
    def test_secure_sql(self):
        """Secure SQL queries are not reported as insecure"""
        r = self.weblog_post("/iast/sqli/test_secure", data={"username": "shaquille_oatmeal", "password": "123456"})
        interfaces.library.expect_no_vulnerabilities(r)

    @missing_feature(reason="Need to implement SQL injection detection")
    def test_insecure_sql(self):
        """Insecure SQL queries are reported as insecure"""
        r = self.weblog_post("/iast/sqli/test_insecure", data={"username": "shaquille_oatmeal", "password": "123456"})
        interfaces.library.expect_iast_vulnerabilities(
            r, vulnerability_count=1, vulnerability_type="SQL_INJECTION", location_path=self.__expected_location(),
        )
