# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import weblog, context, bug, missing_feature, coverage, features
from .._test_iast_fixtures import BaseSinkTest, assert_iast_vulnerability


def _expected_location():
    if context.library.library == "java":
        return "com.datadoghq.system_tests.iast.utils.CryptoExamples"

    if context.library.library == "nodejs":
        if context.weblog_variant == "express4":
            return "iast/index.js"
        if context.weblog_variant == "express4-typescript":
            return "iast.ts"

    if context.library.library == "python":
        if context.library.version >= "1.12.0":
            return "iast.py"
        else:
            # old value: absolute path
            if context.weblog_variant == "uwsgi-poc":
                return "/app/./iast.py"
            else:
                return "/app/iast.py"


def _expected_evidence():
    if context.library.library == "dotnet":
        return "MD5"
    else:
        return "md5"


@coverage.basic
@features.weak_hash_vulnerability_detection
class TestWeakHash(BaseSinkTest):
    """Verify weak hash detection."""

    vulnerability_type = "WEAK_HASH"
    http_method = "GET"
    insecure_endpoint = "/iast/insecure_hashing/test_md5_algorithm"
    secure_endpoint = "/iast/insecure_hashing/test_secure_algorithm"
    data = None
    location_map = _expected_location()
    evidence_map = _expected_evidence()

    def setup_insecure_hash_remove_duplicates(self):
        self.r_insecure_hash_remove_duplicates = weblog.get("/iast/insecure_hashing/deduplicate")

    @missing_feature(weblog_variant="spring-boot-openliberty")
    def test_insecure_hash_remove_duplicates(self):
        """If one line is vulnerable and it is executed multiple times (for instance in a loop) in a request,
        we will report only one vulnerability"""
        assert_iast_vulnerability(
            request=self.r_insecure_hash_remove_duplicates,
            vulnerability_count=1,
            vulnerability_type="WEAK_HASH",
            expected_location=self.expected_location,
            expected_evidence=self.expected_evidence,
        )

    def setup_insecure_hash_multiple(self):
        self.r_insecure_hash_multiple = weblog.get("/iast/insecure_hashing/multiple_hash")

    @bug(weblog_variant="spring-boot-openliberty")
    def test_insecure_hash_multiple(self):
        """If a endpoint has multiple vulnerabilities (in diferent lines) we will report all of them"""
        assert_iast_vulnerability(
            request=self.r_insecure_hash_multiple,
            vulnerability_count=2,
            vulnerability_type="WEAK_HASH",
            expected_location=self.expected_location,
        )

    @missing_feature(context.library < "java@1.9.0", reason="Metrics not implemented")
    @missing_feature(library="dotnet", reason="Not implemented yet")
    def test_telemetry_metric_instrumented_sink(self):
        super().test_telemetry_metric_instrumented_sink()

    @missing_feature(context.library < "java@1.11.0", reason="Metrics not implemented")
    @missing_feature(context.library < "dotnet@2.38.0", reason="Not implemented yet")
    def test_telemetry_metric_executed_sink(self):
        super().test_telemetry_metric_executed_sink()
