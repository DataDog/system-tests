# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import weblog, interfaces, context, bug, missing_feature, coverage, released
from .._test_iast_fixtures import SinkFixture, get_iast_event, assert_iast_vulnerability


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
@released(java="0.108.0", php_appsec="?", python="1.6.0", ruby="?")
@missing_feature(weblog_variant="spring-boot-3-native", reason="GraalVM. Tracing support only")
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

    @missing_feature(weblog_variant="spring-boot-openliberty")
    @missing_feature(library="python", reason="Need to be implement duplicates vulnerability hashes")
    def test_insecure_hash_remove_duplicates(self):
        """If one line is vulnerable and it is executed multiple times (for instance in a loop) in a request,
        we will report only one vulnerability"""
        assert_iast_vulnerability(
            request=self.r_insecure_hash_remove_duplicates,
            vulnerability_count=1,
            vulnerability_type="WEAK_HASH",
            expected_location=self.sink_fixture.expected_location,
            expected_evidence=self.sink_fixture.expected_evidence,
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
            expected_location=self.sink_fixture.expected_location,
        )

    def setup_telemetry_metric_instrumented_sink(self):
        self.sink_fixture.setup_telemetry_metric_instrumented_sink()

    @missing_feature(context.library < "java@1.13.0", reason="Not implemented yet")
    @missing_feature(library="nodejs", reason="Not implemented yet")
    @missing_feature(library="python", reason="Not implemented yet")
    def test_telemetry_metric_instrumented_sink(self):
        self.sink_fixture.test_telemetry_metric_instrumented_sink()

    def setup_telemetry_metric_executed_sink(self):
        self.sink_fixture.setup_telemetry_metric_executed_sink()

    @missing_feature(context.library < "java@1.13.0", reason="Not implemented yet")
    @missing_feature(library="nodejs", reason="Not implemented yet")
    @missing_feature(library="python", reason="Not implemented yet")
    def test_telemetry_metric_executed_sink(self):
        self.sink_fixture.test_telemetry_metric_executed_sink()
