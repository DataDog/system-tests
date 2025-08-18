# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import weblog, context, missing_feature, features, rfc, scenarios
from utils._context._scenarios.dynamic import dynamic_scenario
from tests.appsec.iast.utils import (
    BaseSinkTest,
    assert_iast_vulnerability,
    validate_extended_location_data,
    validate_stack_traces,
)


def _expected_location() -> str | None:
    if context.library.name == "java":
        return "com.datadoghq.system_tests.iast.utils.CryptoExamples"

    if context.library.name == "nodejs":
        if context.weblog_variant in ("express4", "express5", "fastify"):
            return "iast/index.js"
        if context.weblog_variant == "express4-typescript":
            return "iast.ts"

    if context.library.name == "python":
        if context.library.version >= "1.12.0":
            return "iast.py"
        # old value: absolute path
        elif context.weblog_variant == "uwsgi-poc":
            return "/app/./iast.py"
        else:
            return "/app/iast.py"
    return None


def _expected_evidence() -> str:
    if context.library.name == "dotnet":
        return "MD5"
    else:
        return "md5"


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

    @missing_feature(context.library < "java@1.9.0", reason="Metrics not implemented")
    @missing_feature(library="dotnet", reason="Not implemented yet")
    def test_telemetry_metric_instrumented_sink(self):
        super().test_telemetry_metric_instrumented_sink()

    @missing_feature(context.library < "java@1.11.0", reason="Metrics not implemented")
    @missing_feature(context.library < "dotnet@2.38.0", reason="Not implemented yet")
    def test_telemetry_metric_executed_sink(self):
        super().test_telemetry_metric_executed_sink()


@rfc(
    "https://docs.google.com/document/d/1ga7yCKq2htgcwgQsInYZKktV0hNlv4drY9XzSxT-o5U/edit?tab=t.0#heading=h.d0f5wzmlfhat"
)
@features.iast_stack_trace
class TestWeakHash_StackTrace:
    """Validate stack trace generation"""

    def setup_stack_trace(self):
        self.r = weblog.get("/iast/insecure_hashing/test_md5_algorithm")

    def test_stack_trace(self):
        validate_stack_traces(self.r)


@dynamic_scenario(mandatory={"DD_IAST_ENABLED": "true", "DD_IAST_DEDUPLICATION_ENABLED": "true", "DD_IAST_REQUEST_SAMPLING": "100", "DD_IAST_VULNERABILITIES_PER_REQUEST": "10", "DD_IAST_MAX_CONTEXT_OPERATIONS": "10"})
@features.weak_hash_vulnerability_detection
class TestDeduplication:
    """Verify vulnerability deduplication."""

    location_map = _expected_location()
    evidence_map = _expected_evidence()

    def setup_insecure_hash_remove_duplicates(self):
        self.r_insecure_hash_remove_duplicates = weblog.get("/iast/insecure_hashing/deduplicate")

    def test_insecure_hash_remove_duplicates(self):
        """If one line is vulnerable and it is executed multiple times (for instance in a loop) in a request,
        we will report only one vulnerability
        """
        assert_iast_vulnerability(
            request=self.r_insecure_hash_remove_duplicates,
            vulnerability_count=1,
            vulnerability_type="WEAK_HASH",
            expected_location=_expected_location(),
            expected_evidence=_expected_evidence(),
        )

    def setup_insecure_hash_multiple(self):
        self.r_insecure_hash_multiple = weblog.get("/iast/insecure_hashing/multiple_hash")

    def test_insecure_hash_multiple(self):
        """If a endpoint has multiple vulnerabilities (in diferent lines) we will report all of them"""
        assert_iast_vulnerability(
            request=self.r_insecure_hash_multiple,
            vulnerability_count=2,
            vulnerability_type="WEAK_HASH",
            expected_location=_expected_location(),
        )


@rfc("https://docs.google.com/document/d/1R8AIuQ9_rMHBPdChCb5jRwPrg1WvIz96c_WQ3y8DWk4")
@features.iast_extended_location
class TestWeakHash_ExtendedLocation:
    """Test extended location data"""

    vulnerability_type = "WEAK_HASH"

    def setup_extended_location_data(self):
        self.r = weblog.get("/iast/insecure_hashing/test_md5_algorithm")

    def test_extended_location_data(self):
        validate_extended_location_data(self.r, self.vulnerability_type)
