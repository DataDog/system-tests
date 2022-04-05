# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import pytest

from utils import BaseTestCase, context, interfaces, released, bug, missing_feature, irrelevant, rfc


if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2365948382/Sensitive+Data+Obfuscation")
@missing_feature(reason="Not started yet in any lib")
class Test_AppSecObfuscator(BaseTestCase):
    """AppSec obfuscates sensitive data."""

    def test_appsec_obfuscator(self):
        """General obfuscation test of several attacks on several rule addresses."""
        # Validate that the AppSec events do not contain the following secret value.
        # Note that this value must contain an attack pattern in order to be part of the security event data
        # that is expected to be obfuscated.
        SECRET = "this is a very secret value having the appscan_fingerprint attack"

        def validate_appsec_span_tags(payload, chunk, span, appsec_data):
            if SECRET in span["meta"]["_dd.appsec.json"]:
                raise Exception("The security events contain the secret value that should be obfuscated")
            return True

        r = self.weblog_get(
            "/waf/",
            headers={"User-Agent": f"Arachni/v1", "DD_API_TOKEN": SECRET},
            cookies={"Bearer": SECRET},
            params={"pwd": SECRET},
        )
        interfaces.library.assert_waf_attack(r)
        interfaces.library.add_appsec_validation(r, validate_appsec_span_tags)

    def test_appsec_obfuscator_cookies(self):
        """
        Specific obfuscation test for the cookies which often contain sensitive data and are
        expected to be properly obfuscated on sensitive cookies only.
        """
        # Validate that the AppSec events do not contain the following secret value.
        # Note that this value must contain an attack pattern in order to be part of the security event data
        # that is expected to be obfuscated.
        SECRET_VALUE_WITH_SENSITIVE_KEY = "this is a very sensitive cookie value having the appscan_fingerprint attack"
        SECRET_VALUE_WITH_NON_SENSITIVE_KEY = "not a sensitive cookie value having an appscan_fingerprint attack"

        def validate_appsec_span_tags(payload, chunk, span, appsec_data):
            if SECRET_VALUE_WITH_SENSITIVE_KEY in span["meta"]["_dd.appsec.json"]:
                raise Exception("The security events contain the secret value that should be obfuscated")
            if SECRET_VALUE_WITH_NON_SENSITIVE_KEY not in span["meta"]["_dd.appsec.json"]:
                raise Exception("Could not find the non-sensitive cookie data")
            return True

        r = self.weblog_get(
            "/waf/",
            cookies={"Bearer": SECRET_VALUE_WITH_SENSITIVE_KEY, "Good": SECRET_VALUE_WITH_NON_SENSITIVE_KEY},
        )
        interfaces.library.assert_waf_attack(r)
        interfaces.library.add_appsec_validation(r, validate_appsec_span_tags)
