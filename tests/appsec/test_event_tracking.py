# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
from utils import weblog, interfaces, features, missing_feature, context, irrelevant
from tests.appsec.utils import find_series

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


def validate_metric_type_and_version(event_type, version, metric):
    return (
        metric.get("type") == "count"
        and f"event_type:{event_type}" in metric.get("tags", ())
        and f"sdk_version:{version}" in metric.get("tags", ())
    )


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

            for tag, expected_value in expected_tags.items():
                assert tag in span["meta"], f"Can't find {tag} in span's meta"
                value = span["meta"][tag]
                if value != expected_value:
                    raise Exception(f"{tag} value is '{value}', should be '{expected_value}'")

            return True

        interfaces.library.validate_spans(self.r, validator=validate_user_login_success_tags)

    def setup_user_login_success_header_collection(self):
        self.r = weblog.get("/user_login_success_event", headers=HEADERS)

    @missing_feature(library="dotnet")
    @missing_feature(context.library < "nodejs@5.18.0")
    @missing_feature(context.library < "ruby@2.13.0")
    def test_user_login_success_header_collection(self):
        # Validate that all relevant headers are included on user login success

        def validate_user_login_success_header_collection(span):
            if span.get("parent_id") not in (0, None):
                return None

            for header in HEADERS:
                assert f"http.request.headers.{header.lower()}" in span["meta"], f"Can't find {header} in span's meta"
            return True

        interfaces.library.validate_spans(self.r, validator=validate_user_login_success_header_collection)


@features.user_monitoring
class Test_UserLoginSuccessEvent_Metrics:
    """Success test for User Login Event SDK for AppSec"""

    def setup_user_login_success_event(self):
        self.r = weblog.get("/user_login_success_event")

    def test_user_login_success_event(self):
        # Call the user login success SDK and validate tags
        series = find_series("appsec", ["sdk.event"])

        assert series

        assert any(validate_metric_type_and_version("login_success", "v1", s) for s in series), [
            s.get("tags") for s in series
        ]


@features.user_monitoring
class Test_UserLoginFailureEvent:
    """Failure test for User Login Event SDK for AppSec"""

    def setup_user_login_failure_event(self):
        headers = {
            "X-Forwarded-For": "1.2.3.4",
        }

        self.r = weblog.get("/user_login_failure_event", headers=headers)

    @irrelevant(context.library >= "golang@2.0.0-rc.1", reason="implementation deprecated")
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

        interfaces.library.validate_spans(self.r, validator=validate_user_login_failure_tags)

    def setup_user_login_failure_header_collection(self):
        self.r = weblog.get("/user_login_failure_event", headers=HEADERS)

    @missing_feature(context.library < "dotnet@3.7.0")
    @missing_feature(context.library < "nodejs@5.18.0")
    @missing_feature(context.library < "ruby@2.13.0")
    def test_user_login_failure_header_collection(self):
        # Validate that all relevant headers are included on user login failure

        def validate_user_login_failure_header_collection(span):
            if span.get("parent_id") not in (0, None):
                return None

            for header in HEADERS:
                assert f"http.request.headers.{header.lower()}" in span["meta"], f"Can't find {header} in span's meta"
            return True

        interfaces.library.validate_spans(self.r, validator=validate_user_login_failure_header_collection)


@features.user_monitoring
class Test_UserLoginFailureEvent_Metrics:
    """Success test for User Login Event SDK for AppSec"""

    def setup_user_login_success_event(self):
        self.r = weblog.get("/user_login_failure_event")

    def test_user_login_success_event(self):
        # Call the user login success SDK and validate tags
        series = find_series("appsec", ["sdk.event"])

        assert series

        assert any(validate_metric_type_and_version("login_failure", "v1", s) for s in series), [
            s.get("tags") for s in series
        ]


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

            return True

        interfaces.library.validate_spans(self.r, validator=validate_custom_event_tags)


@features.user_monitoring
class Test_CustomEvent_Metrics:
    """Success test for User Login Event SDK for AppSec"""

    def setup_user_login_success_event(self):
        self.r = weblog.get("/custom_event")

    def test_user_login_success_event(self):
        # Call the user login success SDK and validate tags
        series = find_series("appsec", ["sdk.event"])

        assert series

        assert any(validate_metric_type_and_version("custom", "v1", s) for s in series), [s.get("tags") for s in series]
