# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
from utils import weblog, interfaces, features, missing_feature, context

HEADERS = {
    "Accept": "text/html",
    "Accept-Encoding": "br;q=1.0, gzip;q=0.8, *;q=0.1",
    "Accept-Language": "en-GB, *;q=0.5",
    "Content-Language": "en-GB",
    "Content-Length": "0",
    "Content-Type": "text/html; charset=utf-8",
    "Content-Encoding": "deflate, gzip",
    "Host": "127.0.0.1:1234",
    "User-Agent": "Benign User Agent 1.0",
    "X-Forwarded-For": "42.42.42.42, 43.43.43.43",
    "X-Client-IP": "42.42.42.42, 43.43.43.43",
    "X-Real-IP": "42.42.42.42, 43.43.43.43",
    "X-Forwarded": "42.42.42.42, 43.43.43.43",
    "X-Cluster-Client-IP": "42.42.42.42, 43.43.43.43",
    "Forwarded-For": "42.42.42.42, 43.43.43.43",
    "Forwarded": "42.42.42.42, 43.43.43.43",
    "Via": "42.42.42.42, 43.43.43.43",
    "True-Client-IP": "42.42.42.42, 43.43.43.43",
}


@features.user_monitoring
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
            # Older Golang releases did not set the tag at all.
            if context.library != "golang" or context.library >= "golang@1.73.0-dev":
                expected_tags["_dd.appsec.events.users.login.failure.sdk"] = "true"

            for tag, expected_value in expected_tags.items():
                assert tag in span["meta"], f"Can't find {tag} in span's meta"
                value = span["meta"][tag]
                if value != expected_value:
                    raise Exception(f"{tag} value is '{value}', should be '{expected_value}'")

            return True

        interfaces.library.validate_spans(self.r, validate_user_login_success_tags)

    def setup_user_login_success_header_collection(self):
        self.r = weblog.get("/user_login_success_event", headers=HEADERS)

    @missing_feature(library="dotnet")
    @missing_feature(context.library < "nodejs@5.18.0")
    @missing_feature(library="ruby")
    def test_user_login_success_header_collection(self):
        # Validate that all relevant headers are included on user login success

        def validate_user_login_success_header_collection(span):
            if span.get("parent_id") not in (0, None):
                return None

            for header in HEADERS:
                assert f"http.request.headers.{header.lower()}" in span["meta"], f"Can't find {header} in span's meta"
            return True

        interfaces.library.validate_spans(self.r, validate_user_login_success_header_collection)


@features.user_monitoring
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
            # Older Golang releases did not set the tag at all.
            if context.library != "golang" or context.library >= "golang@1.73.0-dev":
                expected_tags["_dd.appsec.events.users.login.failure.sdk"] = "true"

            for tag, expected_value in expected_tags.items():
                assert tag in span["meta"], f"Can't find {tag} in span's meta"
                value = span["meta"][tag]
                if value != expected_value:
                    raise Exception(f"{tag} value is '{value}', should be '{expected_value}'")

            return True

        interfaces.library.validate_spans(self.r, validate_user_login_failure_tags)

    def setup_user_login_failure_header_collection(self):
        self.r = weblog.get("/user_login_failure_event", headers=HEADERS)

    @missing_feature(context.library < "dotnet@3.7.0")
    @missing_feature(context.library < "nodejs@5.18.0")
    @missing_feature(library="ruby")
    def test_user_login_failure_header_collection(self):
        # Validate that all relevant headers are included on user login failure

        def validate_user_login_failure_header_collection(span):
            if span.get("parent_id") not in (0, None):
                return None

            for header in HEADERS:
                assert f"http.request.headers.{header.lower()}" in span["meta"], f"Can't find {header} in span's meta"
            return True

        interfaces.library.validate_spans(self.r, validate_user_login_failure_header_collection)


@features.custom_business_logic_events
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

            # For <custom> events, the _dd.appsec.events.<custom>.sdk tag is not required, but if
            # present, must be set to "true" (these events always come from the SDK, so there is no
            # ambiguity to resolve with automatically generated ones).
            assert span["meta"].get("_dd.appsec.events.system_tests_event.sdk", "true") == "true"

            return True

        interfaces.library.validate_spans(self.r, validate_custom_event_tags)
