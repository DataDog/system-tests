# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import pytest
from utils import weblog, interfaces, context, coverage, released


if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


# Weblog are ok for nodejs/express4 and java/spring-boot
@coverage.basic
@released(dotnet="?", golang="?", nodejs="?", php_appsec="?", python="?", ruby="?")
@released(java={"spring-boot": "1.1.0", "spring-boot-jetty": "1.1.0", "spring-boot-openliberty": "1.1.0", "*": "?"})
class TestIastSqlInjection:
    """Verify IAST SQL INJECTION feature"""

    EXPECTATIONS = {
        "java": {"LOCATION": "com.datadoghq.system_tests.springboot.iast.utils.SqlExamples"},
        "nodejs": {"LOCATION": "/usr/app/iast.js"},
    }

    def __expected_location(self):
        expected = self.EXPECTATIONS.get(context.library.library)
        return expected.get("LOCATION") if expected else None

    def setup_secure_sql(self):
        self.r_secure_sql = weblog.post(
            "/iast/sqli/test_secure", data={"username": "shaquille_oatmeal", "password": "123456"}
        )

    def test_secure_sql(self):
        """Secure SQL queries are not reported as insecure"""
        interfaces.library.expect_no_vulnerabilities(self.r_secure_sql)

    def setup_insecure_sql(self):
        self.r_insecure_sql = weblog.post(
            "/iast/sqli/test_insecure", data={"username": "shaquille_oatmeal", "password": "123456"}
        )

    def test_insecure_sql(self):
        """Insecure SQL queries are reported as insecure"""
        interfaces.library.expect_iast_vulnerabilities(
            self.r_insecure_sql,
            vulnerability_count=1,
            vulnerability_type="SQL_INJECTION",
            location_path=self.__expected_location(),
        )
