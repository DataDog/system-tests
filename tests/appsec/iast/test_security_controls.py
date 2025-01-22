# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, features, rfc, weblog, interfaces, irrelevant
from tests.appsec.iast.utils import BaseSinkTest, assert_iast_vulnerability, assert_metric


@features.iast_security_controls
@rfc("https://docs.google.com/document/d/1j1hp87-2wJnXUGADZxzLnvKJmaF_Gd6ZR1hPS3LVguQ/edit?pli=1&tab=t.0")
class TestSecurityControls:
    @staticmethod
    def assert_iast_is_enabled(request):
        product_enabled = False
        for _, _, span in interfaces.library.get_spans(request=request):
            # Check if the product is enabled in meta
            meta = span["meta"]
            if "_dd.iast.json" in meta:
                product_enabled = True
                break
            # Check if the product is enabled in meta_struct
            if "meta_struct" in span:
                meta_struct = span["meta_struct"]
                if meta_struct and meta_struct.get("vulnerability"):
                    product_enabled = True
                    break
            metrics = span["metrics"]
            if "_dd.iast.enabled" in metrics and metrics["_dd.iast.enabled"] == 1:
                product_enabled = True
                break

        assert product_enabled, "IAST is not available"

    def setup_iast_is_enabled(self):
        self.check_r = weblog.post("/iast/sc/iv/not-configured", data={"param": "param"})

    def setup_vulnerability_suppression_with_an_input_validator_configured_for_a_specific_vulnerability(self):
        self.setup_iast_is_enabled()
        self.r = weblog.post("/iast/sc/iv/configured", data={"param": "param"})

    def test_vulnerability_suppression_with_an_input_validator_configured_for_a_specific_vulnerability(self):
        self.assert_iast_is_enabled(self.check_r)
        BaseSinkTest.assert_no_iast_event(self.r, "COMMAND_INJECTION")
        assert_metric(self.r, "_dd.iast.telemetry.suppressed.vulnerabilities.command_injection", True)

    def setup_no_vulnerability_suppression_with_an_input_validator_configured_for_a_different_vulnerability(self):
        self.setup_iast_is_enabled()
        self.r = weblog.post("/iast/sc/iv/not-configured", data={"param": "param"})

    def test_no_vulnerability_suppression_with_an_input_validator_configured_for_a_different_vulnerability(self):
        self.assert_iast_is_enabled(self.check_r)
        assert_iast_vulnerability(
            request=self.r,
            vulnerability_count=1,
            vulnerability_type="SQL_INJECTION",
        )
        assert_metric(self.r, "_dd.iast.telemetry.suppressed.vulnerabilities.sql_injection", False)

    def setup_vulnerability_suppression_with_an_input_validator_configured_for_all_vulnerabilities(self):
        self.setup_iast_is_enabled()
        self.r = weblog.post("/iast/sc/iv/all", data={"param": "param"})

    def test_vulnerability_suppression_with_an_input_validator_configured_for_all_vulnerabilities(self):
        self.assert_iast_is_enabled(self.check_r)
        BaseSinkTest.assert_no_iast_event(self.r, "SQL_INJECTION")
        assert_metric(self.r, "_dd.iast.telemetry.suppressed.vulnerabilities.sql_injection", True)

    def setup_vulnerability_suppression_with_an_input_validator_configured_for_an_overloaded_method_with_specific_signature(
        self,
    ):
        self.setup_iast_is_enabled()
        self.r = weblog.post("iast/sc/iv/overloaded/secure", data={"user": "usr1", "password": "pass"})

    def test_vulnerability_suppression_with_an_input_validator_configured_for_an_overloaded_method_with_specific_signature(
        self,
    ):
        self.assert_iast_is_enabled(self.check_r)
        BaseSinkTest.assert_no_iast_event(self.r, "SQL_INJECTION")
        assert_metric(self.r, "_dd.iast.telemetry.suppressed.vulnerabilities.sql_injection", True)

    def setup_no_vulnerability_suppression_with_an_input_validator_configured_for_an_overloaded_method_with_specific_signature(
        self,
    ):
        self.setup_iast_is_enabled()
        self.r = weblog.post("iast/sc/iv/overloaded/insecure", data={"user": "usr1", "password": "pass"})

    def test_no_vulnerability_suppression_with_an_input_validator_configured_for_an_overloaded_method_with_specific_signature(
        self,
    ):
        self.assert_iast_is_enabled(self.check_r)
        assert_iast_vulnerability(
            request=self.r,
            vulnerability_count=1,
            vulnerability_type="SQL_INJECTION",
        )
        assert_metric(self.r, "_dd.iast.telemetry.suppressed.vulnerabilities.sql_injection", False)

    def setup_vulnerability_suppression_with_a_sanitizer_configured_for_a_specific_vulnerability(self):
        self.setup_iast_is_enabled()
        self.r = weblog.post("/iast/sc/s/configured", data={"param": "param"})

    def test_vulnerability_suppression_with_a_sanitizer_configured_for_a_specific_vulnerability(self):
        self.assert_iast_is_enabled(self.check_r)
        BaseSinkTest.assert_no_iast_event(self.r, "COMMAND_INJECTION")
        assert_metric(self.r, "_dd.iast.telemetry.suppressed.vulnerabilities.command_injection", True)

    def setup_no_vulnerability_suppression_with_a_sanitizer_configured_for_a_different_vulnerability(self):
        self.setup_iast_is_enabled()
        self.r = weblog.post("/iast/sc/s/not-configured", data={"param": "param"})

    def test_no_vulnerability_suppression_with_a_sanitizer_configured_for_a_different_vulnerability(self):
        self.assert_iast_is_enabled(self.check_r)
        assert_iast_vulnerability(
            request=self.r,
            vulnerability_count=1,
            vulnerability_type="SQL_INJECTION",
        )
        assert_metric(self.r, "_dd.iast.telemetry.suppressed.vulnerabilities.sql_injection", False)

    def setup_vulnerability_suppression_with_a_sanitizer_configured_for_all_vulnerabilities(self):
        self.setup_iast_is_enabled()
        self.r = weblog.post("/iast/sc/s/all", data={"param": "param"})

    def test_vulnerability_suppression_with_a_sanitizer_configured_for_all_vulnerabilities(self):
        self.assert_iast_is_enabled(self.check_r)
        BaseSinkTest.assert_no_iast_event(self.r, "SQL_INJECTION")
        assert_metric(self.r, "_dd.iast.telemetry.suppressed.vulnerabilities.sql_injection", True)

    def setup_vulnerability_suppression_with_a_sanitizer_configured_for_an_overloaded_method_with_specific_signature(
        self,
    ):
        self.setup_iast_is_enabled()
        self.r = weblog.post("iast/sc/s/overloaded/secure", data={"param": "param"})

    def test_vulnerability_suppression_with_a_sanitizer_configured_for_an_overloaded_method_with_specific_signature(
        self,
    ):
        self.assert_iast_is_enabled(self.check_r)
        BaseSinkTest.assert_no_iast_event(self.r, "COMMAND_INJECTION")
        assert_metric(self.r, "_dd.iast.telemetry.suppressed.vulnerabilities.command_injection", True)

    def setup_no_vulnerability_suppression_with_a_sanitizer_configured_for_an_overloaded_method_with_specific_signature(
        self,
    ):
        self.setup_iast_is_enabled()
        self.r = weblog.post("iast/sc/s/overloaded/insecure", data={"param": "param"})

    @irrelevant(context.library == "nodejs")
    def test_no_vulnerability_suppression_with_a_sanitizer_configured_for_an_overloaded_method_with_specific_signature(
        self,
    ):
        self.assert_iast_is_enabled(self.check_r)
        assert_iast_vulnerability(
            request=self.r,
            vulnerability_count=1,
            vulnerability_type="COMMAND_INJECTION",
        )
        assert_metric(self.r, "_dd.iast.telemetry.suppressed.vulnerabilities.sql_injection", False)
