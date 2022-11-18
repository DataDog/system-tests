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
    python="1.6.0",
    ruby="?",
    cpp="?",
)
class TestIastWeakHash(BaseTestCase):
    """Verify IAST WEAK HASH detection feature"""

    EXPECTATIONS = {
        "python": {"LOCATION": "/iast.py" if context.weblog_variant != "uwsgi-poc" else "/./iast.py"},
        "nodejs": {"LOCATION": "/usr/app/iast.js"},
        "java": {"LOCATION": "com.datadoghq.system_tests.springboot.iast.utils.CryptoExamples"},
    }

    def __expected_location(self):
        expected = self.EXPECTATIONS.get(context.library.library)
        return expected.get("LOCATION") if expected else None

    def __expected_weak_cipher_algorithm(self):
        expected = self.EXPECTATIONS.get(context.library.library)
        return expected.get("WEAK_CIPHER_ALGORITHM") if expected else None

    @missing_feature(library="python", reason="Need to be implement duplicates vulnerability hashes")
    @missing_feature(context.weblog_variant == "spring-boot-openliberty")
    def test_insecure_hash_remove_duplicates(self):
        """If one line is vulnerable and it is executed multiple times (for instance in a loop) in a request,
        we will report only one vulnerability"""
        r = self.weblog_get("/iast/insecure_hashing/deduplicate")

        interfaces.library.expect_iast_vulnerabilities(
            r, vulnerability_count=1, vulnerability_type="WEAK_HASH", location_path=self.__expected_location(),
        )

    @missing_feature(context.weblog_variant == "spring-boot-openliberty")
    def test_insecure_hash_multiple(self):
        """If a endpoint has multiple vulnerabilities (in diferent lines) we will report all of them"""
        r = self.weblog_get("/iast/insecure_hashing/multiple_hash")

        interfaces.library.expect_iast_vulnerabilities(
            r, vulnerability_count=2, vulnerability_type="WEAK_HASH", location_path=self.__expected_location(),
        )

    @missing_feature(context.library < "nodejs@3.3.1", reason="Need to be implement global vulnerability deduplication")
    def test_secure_hash(self):
        """Strong hash algorithm is not reported as insecure"""
        r = self.weblog_get("/iast/insecure_hashing/test_secure_algorithm")
        interfaces.library.expect_no_vulnerabilities(r)

    @bug(context.weblog_variant == "spring-boot-openliberty")
    def test_insecure_md5_hash(self):
        """Test md5 weak hash algorithm reported as insecure"""
        r = self.weblog_get("/iast/insecure_hashing/test_md5_algorithm")

        interfaces.library.expect_iast_vulnerabilities(r, vulnerability_type="WEAK_HASH", evidence="md5")
