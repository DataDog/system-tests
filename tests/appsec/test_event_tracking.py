# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
import re

import pytest

from utils import weblog, context, coverage, interfaces, released, irrelevant

if context.weblog_variant == "spring-boot-payara":
    pytestmark = pytest.mark.skip("missing feature: No AppSec support")


_is_spring_native_weblog = re.fullmatch(r"spring-.+native", context.weblog_variant) is not None


@released(java="1.8.0", php_appsec="0.6.0", python="1.9.0", ruby="1.9.0")
@irrelevant(_is_spring_native_weblog, reason="GraalVM. Tracing support only")
@coverage.basic
class Test_UserLoginSuccessEvent:
    """Success test for User Login Event SDK for AppSec"""

    def setup_user_login_success_event(self):
        headers = {
            "X-Forwarded-For": "1.2.3.4",
        }

        self.r = weblog.get("/user_login_success_event", headers=headers)

    def test_user_login_success_event(self):
        # Call the user login success SDK and validate tags

        def validate_user_login_success_tags(span):
            expected_tags = {
                "http.client_ip": "1.2.3.4",
                "usr.id": "system_tests_user",
                "appsec.events.users.login.success.track": "true",
                "appsec.events.users.login.success.metadata0": "value0",
                "appsec.events.users.login.success.metadata1": "value1",
            }

            for tag, expected_value in expected_tags.items():
                assert tag in span["meta"], f"Can't find {tag} in span's meta"
                value = span["meta"][tag]
                if value != expected_value:
                    raise Exception(f"{tag} value is '{value}', should be '{expected_value}'")

            return True

        interfaces.library.validate_spans(self.r, validate_user_login_success_tags)


@released(java="1.8.0", php_appsec="0.6.0", python="1.9.0", ruby="1.9.0")
@irrelevant(_is_spring_native_weblog, reason="GraalVM. Tracing support only")
@coverage.basic
class Test_UserLoginFailureEvent:
    """Failure test for User Login Event SDK for AppSec"""

    def setup_user_login_failure_event(self):
        headers = {
            "X-Forwarded-For": "1.2.3.4",
        }

        self.r = weblog.get("/user_login_failure_event", headers=headers)

    def test_user_login_failure_event(self):
        # Call the user login failure SDK and validate tags

        def validate_user_login_failure_tags(span):
            expected_tags = {
                "http.client_ip": "1.2.3.4",
                "appsec.events.users.login.failure.usr.id": "system_tests_user",
                "appsec.events.users.login.failure.track": "true",
                "appsec.events.users.login.failure.usr.exists": "true",
                "appsec.events.users.login.failure.metadata0": "value0",
                "appsec.events.users.login.failure.metadata1": "value1",
            }

            for tag, expected_value in expected_tags.items():
                assert tag in span["meta"], f"Can't find {tag} in span's meta"
                value = span["meta"][tag]
                if value != expected_value:
                    raise Exception(f"{tag} value is '{value}', should be '{expected_value}'")

            return True

        interfaces.library.validate_spans(self.r, validate_user_login_failure_tags)


@released(java="1.8.0", php_appsec="0.6.0", python="1.10.0", ruby="1.9.0")
@irrelevant(_is_spring_native_weblog, reason="GraalVM. Tracing support only")
@coverage.basic
class Test_CustomEvent:
    """Test for Custom Event SDK for AppSec"""

    def setup_custom_event_event(self):
        headers = {
            "X-Forwarded-For": "1.2.3.4",
        }

        self.r = weblog.get("/custom_event", headers=headers)

    def test_custom_event_event(self):
        # Call the user login failure SDK and validate tags

        def validate_custom_event_tags(span):
            expected_tags = {
                "http.client_ip": "1.2.3.4",
                "appsec.events.system_tests_event.track": "true",
                "appsec.events.system_tests_event.metadata0": "value0",
                "appsec.events.system_tests_event.metadata1": "value1",
            }

            for tag, expected_value in expected_tags.items():
                assert tag in span["meta"], f"Can't find {tag} in span's meta"
                value = span["meta"][tag]
                if value != expected_value:
                    raise Exception(f"{tag} value is '{value}', should be '{expected_value}'")

            return True

        interfaces.library.validate_spans(self.r, validate_custom_event_tags)
