# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
import pytest
from utils import weblog, interfaces, context, bug, missing_feature, coverage, released
from ..iast_fixtures import SinkFixture

if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


def _expected_location():
    if context.library.library == "java":
        return "com.datadoghq.system_tests.iast.utils.CryptoExamples"

    if context.library.library == "nodejs":
        return "iast/index.js"

    if context.library.library == "python":
        if context.library.version >= "1.12.0":
            return "iast.py"
        else:
            # old value: absolute path
            if context.weblog_variant == "uwsgi-poc":
                return "/app/./iast.py"
            else:
                return "/app/iast.py"


@coverage.basic
@released(dotnet="?", golang="?", php_appsec="?", python="1.6.0", ruby="?")
@released(nodejs={"express4": "3.11.0", "*": "?"})
@released(
    java={
        "spring-boot": "0.108.0",
        "spring-boot-jetty": "0.108.0",
        "spring-boot-openliberty": "0.108.0",
        "spring-boot-wildfly": "0.108.0",
        "spring-boot-undertow": "0.108.0",
        "resteasy-netty3": "1.11.0",
        "jersey-grizzly2": "1.11.0",
        "vertx3": "1.12.0",
        "*": "?",
    }
)
@missing_feature(context.weblog_variant == "spring-boot-native", reason="GraalVM. Tracing support only")
@missing_feature(context.weblog_variant == "spring-boot-3-native", reason="GraalVM. Tracing support only")
class TestWeakHash:
    """Verify weak hash detection."""

    sink_fixture = SinkFixture(
        vulnerability_type="WEAK_HASH",
        http_method="GET",
        insecure_endpoint="/iast/insecure_hashing/test_md5_algorithm",
        secure_endpoint="/iast/insecure_hashing/test_secure_algorithm",
        data=None,
        location_map=_expected_location,
        evidence_map="md5",
    )

    def setup_insecure(self):
        self.sink_fixture.setup_insecure()

    def test_insecure(self):
        self.sink_fixture.test_insecure()

    def setup_secure(self):
        self.sink_fixture.setup_secure()

    def test_secure(self):
        self.sink_fixture.test_secure()

    def setup_insecure_hash_remove_duplicates(self):
        self.r_insecure_hash_remove_duplicates = weblog.get("/iast/insecure_hashing/deduplicate")

    @missing_feature(context.weblog_variant == "spring-boot-openliberty")
    @missing_feature(library="python", reason="Need to be implement duplicates vulnerability hashes")
    def test_insecure_hash_remove_duplicates(self):
        """If one line is vulnerable and it is executed multiple times (for instance in a loop) in a request,
        we will report only one vulnerability"""

        interfaces.library.expect_iast_vulnerabilities(
            self.r_insecure_hash_remove_duplicates,
            vulnerability_count=1,
            vulnerability_type="WEAK_HASH",
            location_path=self.sink_fixture.expected_location,
            evidence=self.sink_fixture.expected_evidence,
        )

    def setup_insecure_hash_multiple(self):
        self.r_insecure_hash_multiple = weblog.get("/iast/insecure_hashing/multiple_hash")

    @bug(context.weblog_variant == "spring-boot-openliberty")
    def test_insecure_hash_multiple(self):
        """If a endpoint has multiple vulnerabilities (in diferent lines) we will report all of them"""

        interfaces.library.expect_iast_vulnerabilities(
            self.r_insecure_hash_multiple,
            vulnerability_count=2,
            vulnerability_type="WEAK_HASH",
            location_path=self.sink_fixture.expected_location,
        )
