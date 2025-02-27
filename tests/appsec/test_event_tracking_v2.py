# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import weblog, interfaces, features, scenarios
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

USER_ID_SAFE = "user_id_safe"
USER_ID_IN_RULE = "user_id_unsafe"
LOGIN_SAFE = "login_safe"
LOGIN_IN_RULE = "login_unsafe"


def validate_metric_type_and_version(event_type, version, metric):
    return (
        metric.get("type") == "count"
        and f"event_type:{event_type}" in metric.get("tags", ())
        and f"sdk_version:{version}" in metric.get("tags", ())
    )


@features.user_monitoring
@scenarios.appsec_ato_sdk
class Test_UserLoginSuccessEventV2_Tags:
    """Test tags created in AppSec User Login Success Event SDK v2"""

    def get_user_login_success_tags_validator(self, login, user_id):
        def validate(span):
            expected_tags = {
                "appsec.events.users.login.success.usr.login": login,
                "appsec.events.users.login.success.usr.id": user_id,
                "usr.id": user_id,
                "appsec.events.users.login.success.track": "true",
                "_dd.appsec.events.users.login.success.sdk": "true",
                "appsec.events.users.login.success.metadata0": "value0",
                "appsec.events.users.login.success.metadata1": "value1",
                "http.client_ip": "1.2.3.4",
            }

            for tag, expected_value in expected_tags.items():
                assert tag in span["meta"], f"Can't find {tag} in span's meta"
                value = span["meta"][tag]
                if value != expected_value:
                    raise Exception(f"{tag} value is '{value}', should be '{expected_value}'")

            return True

        return validate

    def setup_user_login_success_event(self):
        headers = {
            "X-Forwarded-For": "1.2.3.4",
        }

        params = {"login": LOGIN_SAFE, "user_id": USER_ID_SAFE}

        self.r = weblog.get("/user_login_success_event_v2", params=params, headers=headers)

    def test_user_login_success_event(self):
        # Call the user login success SDK and validate tags and metrics

        interfaces.library.validate_spans(self.r, self.get_user_login_success_tags_validator(LOGIN_SAFE, USER_ID_SAFE))


@features.user_monitoring
@scenarios.appsec_ato_sdk
class Test_UserLoginSuccessEventV2_HeaderCollection:
    """Test headers are collected in AppSec User Login Success Event SDK v2"""

    def setup_user_login_success_header_collection(self):
        params = {"login": LOGIN_SAFE, "userid": USER_ID_SAFE}

        self.r = weblog.get("/user_login_success_event_v2", params=params, headers=HEADERS)

    def test_user_login_success_header_collection(self):
        # Validate that all relevant headers are included on login success SDK

        def validate_user_login_success_header_collection(span):
            if span.get("parent_id") not in (0, None):
                return None

            for header in HEADERS:
                assert f"http.request.headers.{header.lower()}" in span["meta"], f"Can't find {header} in span's meta"

            return True

        interfaces.library.validate_spans(self.r, validate_user_login_success_header_collection)


@features.user_monitoring
@scenarios.appsec_ato_sdk
class Test_UserLoginSuccessEventV2_Metrics:
    """Test metrics in AppSec User Login Success Event SDK v2"""

    def setup_user_login_success_event(self):
        params = {"login": LOGIN_SAFE, "user_id": USER_ID_SAFE}

        self.r = weblog.get("/user_login_success_event_v2", params=params)

    def test_user_login_success_event(self):
        # Call the user login success SDK and validate tags and metrics

        series = find_series("appsec", metric="sdk.event", is_metrics=True)

        assert series
        assert any(validate_metric_type_and_version("login_success", "v2", s) for s in series), [
            s.get("tags") for s in series
        ]


@features.user_monitoring
@scenarios.appsec_ato_sdk
class Test_UserLoginSuccessEventV2_Libddwaf:
    """Test libddwaf calls in AppSec User Login Success Event SDK v2"""

    def setup_user_login_success_unsafe_login_success_event(self):
        params = {"login": LOGIN_SAFE, "user_id": USER_ID_SAFE}

        self.r = weblog.get("/user_login_success_event_v2", params=params)

    def test_user_login_success_unsafe_login_success_event(self):
        # Call the user login success SDK with unsafe login and validate tags, metrics and threat

        interfaces.library.assert_waf_attack(self.r, rule="003_trigger_on_login_success")

    def setup_user_login_success_unsafe_login_event(self):
        params = {"login": LOGIN_IN_RULE, "user_id": USER_ID_SAFE}

        self.r = weblog.get("/user_login_success_event_v2", params=params)

    def test_user_login_success_unsafe_login_event(self):
        # Call the user login success SDK with unsafe login and validate tags, metrics and threat

        interfaces.library.assert_waf_attack(self.r, rule="001_trigger_on_usr_login")
        interfaces.library.assert_waf_attack(self.r, rule="003_trigger_on_login_success")

    def setup_user_login_success_unsafe_user_id_event(self):
        params = {"login": LOGIN_SAFE, "user_id": USER_ID_IN_RULE}

        self.r = weblog.get("/user_login_success_event_v2", params=params)

    def test_user_login_success_unsafe_user_id_event(self):
        # Call the user login success SDK with unsafe user id and validate tags, metrics and threat
        interfaces.library.assert_waf_attack(self.r, rule="002_trigger_on_usr_id")
        interfaces.library.assert_waf_attack(self.r, rule="003_trigger_on_login_success")


@features.user_monitoring
@scenarios.appsec_ato_sdk
class Test_UserLoginFailureEventV2_Tags:
    """Test created tags in AppSec User Login Failure Event SDK v2"""

    def get_user_login_failure_tags_validator(self, login, exists):
        def validate(span):
            expected_tags = {
                "appsec.events.users.login.failure.usr.login": login,
                "appsec.events.users.login.failure.usr.exists": "true" if exists else "false",
                "appsec.events.users.login.failure.track": "true",
                "_dd.appsec.events.users.login.failure.sdk": "true",
                "appsec.events.users.login.failure.metadata0": "value0",
                "appsec.events.users.login.failure.metadata1": "value1",
                "http.client_ip": "1.2.3.4",
            }

            for tag, expected_value in expected_tags.items():
                assert tag in span["meta"], f"Can't find {tag} in span's meta"
                value = span["meta"][tag]
                if value != expected_value:
                    raise Exception(f"{tag} value is '{value}', should be '{expected_value}'")

            return True

        return validate

    def setup_user_login_failure_event_exists(self):
        headers = {
            "X-Forwarded-For": "1.2.3.4",
        }

        params = {"login": LOGIN_SAFE, "exists": "true"}

        self.r = weblog.get("/user_login_failure_event_v2", params=params, headers=headers)

    def test_user_login_failure_event_exists(self):
        # Call the user login failure SDK with existing account and validate tags and metrics

        interfaces.library.validate_spans(self.r, self.get_user_login_failure_tags_validator(LOGIN_SAFE, exists=True))

    def setup_user_login_failure_event_does_not_exist(self):
        headers = {
            "X-Forwarded-For": "1.2.3.4",
        }

        params = {"login": LOGIN_SAFE, "exists": "false"}

        self.r = weblog.get("/user_login_failure_event_v2", params=params, headers=headers)

    def test_user_login_failure_event_does_not_exist(self):
        # Call the user login failure SDK with account that does not exist and validate tags and metrics

        interfaces.library.validate_spans(self.r, self.get_user_login_failure_tags_validator(LOGIN_SAFE, exists=False))


@features.user_monitoring
@scenarios.appsec_ato_sdk
class Test_UserLogiFailureEventV2_HeaderCollection:
    """Test collected headers in AppSec User Login Failure Event SDK v2"""

    def setup_user_login_failure_header_collection(self):
        params = {"login": LOGIN_SAFE, "exists": "true"}

        self.r = weblog.get("/user_login_failure_event_v2", params=params, headers=HEADERS)

    def test_user_login_failure_header_collection(self):
        # Validate that all relevant headers are included on user login failure

        def validate_user_login_failure_header_collection(span):
            if span.get("parent_id") not in (0, None):
                return None

            for header in HEADERS:
                assert f"http.request.headers.{header.lower()}" in span["meta"], f"Can't find {header} in span's meta"

            return True

        interfaces.library.validate_spans(self.r, validate_user_login_failure_header_collection)


@features.user_monitoring
@scenarios.appsec_ato_sdk
class Test_UserLoginFailureEventV2_Metrics:
    """Test metrics in AppSec User Login Failure Event SDK v2"""

    def setup_user_login_failure_event(self):
        params = {"login": LOGIN_SAFE, "exists": "true"}

        self.r = weblog.get("/user_login_failure_event_v2", params=params)

    def test_user_login_failure_event(self):
        # Call the user login success SDK and validate tags and metrics

        series = find_series("appsec", metric="sdk.event", is_metrics=True)

        assert series
        assert any(validate_metric_type_and_version("login_failure", "v2", s) for s in series), [
            s.get("tags") for s in series
        ]


@features.user_monitoring
@scenarios.appsec_ato_sdk
class Test_UserLoginFailureEventV2_Libddwaf:
    """Test libddwaf calls in AppSec User Login Failure Event SDK v2"""

    def setup_user_login_failure_safe_login_event(self):
        params = {"login": LOGIN_SAFE, "exists": "true"}

        self.r = weblog.get("/user_login_failure_event_v2", params=params)

    def test_user_login_failure_safe_login_event(self):
        # Call the user login failure SDK with unsafe login and validate tags, metrics and threat
        interfaces.library.assert_waf_attack(self.r, rule="004_trigger_on_login_failure")

    def setup_user_login_failure_unsafe_login_event(self):
        params = {"login": LOGIN_IN_RULE, "exists": "true"}

        self.r = weblog.get("/user_login_failure_event_v2", params=params)

    def test_user_login_failure_unsafe_login_event(self):
        # Call the user login failure SDK with unsafe login and validate tags, metrics and threat

        interfaces.library.assert_waf_attack(self.r, rule="001_trigger_on_usr_login")
        interfaces.library.assert_waf_attack(self.r, rule="004_trigger_on_login_failure")
