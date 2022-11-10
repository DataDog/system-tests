# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, interfaces, context, missing_feature, coverage, released

# Weblog are ok for nodejs/express4 and java/spring-boot
@coverage.basic
@released(
    dotnet="?",
    golang="?",
    java={"spring-boot": "0.108.0", "spring-boot-jetty": "0.108.0", "spring-boot-openliberty": "0.108.0", "*": "?"},
    nodejs={"express4": "3.6.0", "*": "?"},
    php_appsec="?",
    python="1.6.0rc1.dev",
    ruby="?",
    cpp="?",
)
class Test_Iast(BaseTestCase):
    """Verify IAST features"""

    EXPECTATIONS = {
        "python": {"LOCATION": {"WEAK_HASH": "/iast.py"}, "WEAK_CIPHER_ALGORITHM": "????"},
        "nodejs": {"LOCATION": {"WEAK_HASH": "/usr/app/app.js"}, "WEAK_CIPHER_ALGORITHM": "des-ede-cbc"},
        "java": {
            "LOCATION": {
                "WEAK_HASH": "com.datadoghq.system_tests.springboot.iast.utils.CryptoExamples",
                "SQL_INJECTION": "com.datadoghq.system_tests.springboot.iast.utils.SqlExamples",
            },
            "WEAK_CIPHER_ALGORITHM": "Blowfish",
        },
    }

    def __expected_location(self, vulnerability):
        expected = self.EXPECTATIONS.get(context.library.library)
        location = expected.get("LOCATION") if expected else None
        return location.get(vulnerability) if location else None

    def __expected_weak_cipher_algorithm(self):
        expected = self.EXPECTATIONS.get(context.library.library)
        return expected.get("WEAK_CIPHER_ALGORITHM") if expected else None

    @missing_feature(library="python", reason="Need to be implement deduplicate vulnerability hashes")
    def test_insecure_hash_remove_duplicates(self):
        """If one line is vulnerable and it is executed multiple times (for instance in a loop) in a request,
        we will report only one vulnerability"""
        r = self.weblog_get("/iast/insecure_hashing/deduplicate")

        interfaces.library.expect_iast_vulnerabilities(
            r,
            vulnerability_count=1,
            vulnerability_type="WEAK_HASH",
            location_path=self.__expected_location("WEAK_HASH"),
        )

    def test_insecure_hash_multiple(self):
        """If a endpoint has multiple vulnerabilities (in diferent lines) we will report all of them"""
        r = self.weblog_get("/iast/insecure_hashing/multiple_hash")

        interfaces.library.expect_iast_vulnerabilities(
            r,
            vulnerability_count=2,
            vulnerability_type="WEAK_HASH",
            location_path=self.__expected_location("WEAK_HASH"),
        )

    @missing_feature(context.library < "nodejs@3.3.1", reason="Need to be implement global vulnerability deduplication")
    def test_secure_hash(self):
        """Strong hash algorithm is not reported as insecure"""
        r = self.weblog_get("/iast/insecure_hashing/test_secure_algorithm")
        interfaces.library.expect_no_vulnerabilities(r)

    def test_insecure_md5_hash(self):
        """Test md5 weak hash algorithm reported as insecure"""
        r = self.weblog_get("/iast/insecure_hashing/test_md5_algorithm")

        interfaces.library.expect_iast_vulnerabilities(r, vulnerability_type="WEAK_HASH", evidence="md5")

    @missing_feature(library="python", reason="Need to be implement endpoint")
    def test_insecure_cipher(self):
        """Test weak cipher algorithm is reported as insecure"""
        r = self.weblog_get("/iast/insecure_cipher/test_insecure_algorithm")

        interfaces.library.expect_iast_vulnerabilities(
            r, vulnerability_type="WEAK_CIPHER", evidence=self.__expected_weak_cipher_algorithm(),
        )

    @missing_feature(library="python", reason="Need to be implement endpoint")
    def test_secure_cipher(self):
        """Test strong cipher algorithm is not reported as insecure"""
        r = self.weblog_get("/iast/insecure_cipher/test_secure_algorithm")

        interfaces.library.expect_no_vulnerabilities(r)

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
            r,
            vulnerability_count=1,
            vulnerability_type="SQL_INJECTION",
            location_path=self.__expected_location("SQL_INJECTION"),
        )
