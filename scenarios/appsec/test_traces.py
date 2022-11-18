# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import pytest

from tests.constants import PYTHON_RELEASE_GA_1_1
from utils import BaseTestCase, context, interfaces, released, rfc, scenario

if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2365948382/Sensitive+Data+Obfuscation")
@released(golang="1.38.0", dotnet="2.7.0", java="0.100.0", nodejs="2.6.0")
@released(php_appsec="0.3.0", python=PYTHON_RELEASE_GA_1_1, ruby="?")
@scenario("APPSEC_CUSTOM_RULES")
class Test_AppSecObfuscator(BaseTestCase):
    """AppSec obfuscates sensitive data."""

    def test_appsec_obfuscator_key(self):
        """General obfuscation test of several attacks on several rule addresses."""
        # Validate that the AppSec events do not contain the following secret value.
        # Note that this value must contain an attack pattern in order to be part of the security event data
        # that is expected to be obfuscated.
        SECRET = "this-is-a-very-secret-value-having-the-attack"

        def validate_appsec_span_tags(span, appsec_data):  # pylint: disable=unused-argument
            if SECRET in span["meta"]["_dd.appsec.json"]:
                raise Exception("The security events contain the secret value that should be obfuscated")
            return True

        r = self.weblog_get("/waf/", cookies={"Bearer": f"{SECRET}aaaa"}, params={"pwd": f'{SECRET} o:3:"d":3:{{}}'})
        interfaces.library.assert_waf_attack(r, address="server.request.cookies")
        interfaces.library.assert_waf_attack(r, address="server.request.query")
        interfaces.library.add_appsec_validation(r, validate_appsec_span_tags)

    def test_appsec_obfuscator_cookies(self):
        """
        Specific obfuscation test for the cookies which often contain sensitive data and are
        expected to be properly obfuscated on sensitive cookies only.
        """
        # Validate that the AppSec events do not contain the following secret value.
        # Note that this value must contain an attack pattern in order to be part of the security event data
        # that is expected to be obfuscated.
        SECRET_VALUE_WITH_SENSITIVE_KEY = "this-is-a-very-sensitive-cookie-value-having-the-aaaa-attack"
        SECRET_VALUE_WITH_NON_SENSITIVE_KEY = "not-a-sensitive-cookie-value-having-an-bbbb-attack"

        def validate_appsec_span_tags(span, appsec_data):  # pylint: disable=unused-argument
            if SECRET_VALUE_WITH_SENSITIVE_KEY in span["meta"]["_dd.appsec.json"]:
                raise Exception("The security events contain the secret value that should be obfuscated")
            if SECRET_VALUE_WITH_NON_SENSITIVE_KEY not in span["meta"]["_dd.appsec.json"]:
                raise Exception("Could not find the non-sensitive cookie data")
            return True

        r = self.weblog_get(
            "/waf/", cookies={"Bearer": SECRET_VALUE_WITH_SENSITIVE_KEY, "Good": SECRET_VALUE_WITH_NON_SENSITIVE_KEY}
        )
        interfaces.library.assert_waf_attack(r, address="server.request.cookies")
        interfaces.library.add_appsec_validation(r, validate_appsec_span_tags)
