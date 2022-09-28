# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
import pytest
from tkinter import Misc

from tests.constants import PYTHON_RELEASE_GA_1_1
from utils import BaseTestCase, coverage, interfaces, released, rfc, missing_feature, context, irrelevant


if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2355333252/Environment+Variables")
@coverage.basic
@released(dotnet="2.8.0", golang="1.38.0", java="0.100.0", nodejs="2.7.0")
@released(php_appsec="0.3.2", python="1.1.2", ruby="1.0.0")
class Test_ConfigurationVariables(BaseTestCase):
    """ Configuration environment variables """

    # DD_APPSEC_TRACE_RATE_LIMIT is not tested here, there is a dedicated class on appsec/rate_limiter.py

    @irrelevant(library="ruby", weblog_variant="rack", reason="it's not possible to auto instrument with rack")
    @missing_feature(
        context.weblog_variant in ["sinatra14", "sinatra20", "sinatra21"],
        reason="Conf is done in weblog instead of library",
    )
    def test_disabled(self):
        """ test DD_APPSEC_ENABLED = false """
        r = self.weblog_get("/waf/", headers={"User-Agent": "Arachni/v1"})
        interfaces.library.assert_no_appsec_event(r)

    def test_appsec_rules(self):
        """ test DD_APPSEC_RULES = custom rules file """
        r = self.weblog_get("/waf", headers={"attack": "dedicated-value-for-testing-purpose"})
        interfaces.library.assert_waf_attack(r, pattern="dedicated-value-for-testing-purpose")

    @missing_feature(library="java", reason="request is reported")
    def test_waf_timeout(self):
        """ test DD_APPSEC_WAF_TIMEOUT = low value """
        long_payload = "?" + "&".join(f"{k}={v}" for k, v in ((f"key_{i}", f"value{i}") for i in range(100)))
        r = self.weblog_get(f"/waf/{long_payload}", headers={"User-Agent": "Arachni/v1"})
        interfaces.library.assert_no_appsec_event(r)

    @missing_feature(context.library <= "ruby@1.0.0")
    @missing_feature(context.library < f"python@{PYTHON_RELEASE_GA_1_1}")
    def test_obfuscation_parameter_key(self):
        """ test DD_APPSEC_OBFUSCATION_PARAMETER_KEY_REGEXP """

        SECRET = "This-value-is-secret"

        def validate_appsec_span_tags(span, appsec_data):
            if SECRET in span["meta"]["_dd.appsec.json"]:
                raise Exception("The security events contain the secret value that should be obfuscated")
            return True

        r = self.weblog_get("/waf", headers={"hide-key": f"acunetix-user-agreement {SECRET}"})
        interfaces.library.assert_waf_attack(r, pattern="<Redacted>")
        interfaces.library.add_appsec_validation(r, validate_appsec_span_tags)

    @missing_feature(context.library <= "ruby@1.0.0")
    @missing_feature(context.library < "python@{}".format(PYTHON_RELEASE_GA_1_1))
    def test_obfuscation_parameter_value(self):
        """ test DD_APPSEC_OBFUSCATION_PARAMETER_VALUE_REGEXP """

        SECRET = "hide_value"

        def validate_appsec_span_tags(span, appsec_data):
            if SECRET in span["meta"]["_dd.appsec.json"]:
                raise Exception("The security events contain the secret value that should be obfuscated")
            return True

        r = self.weblog_get("/waf", headers={"attack": f"acunetix-user-agreement {SECRET}"})
        interfaces.library.assert_waf_attack(r, pattern="<Redacted>")
        interfaces.library.add_appsec_validation(r, validate_appsec_span_tags)
