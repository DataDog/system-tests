# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import weblog, interfaces, features, scenarios


HEADERS = {
    "Accept": "text/html",
    "Accept-Encoding": "br;q=1.0, gzip;q=0.8, *;q=0.1",
    "Accept-Language": "en-GB, *;q=0.5",
    "Content-Language": "en-GB",
    "Content-Type": "application/json; charset=utf-8",
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
LOGIN_SAFE = "login_safe"


def validate_tags_and_metadata(span, prefix, expected_tags, metadata):
    """Validate that expected tags are present in span metadata"""
    if metadata is not None:
        for key, value in metadata.items():
            expected_tags[prefix + "." + key] = value

    for tag, expected_value in expected_tags.items():
        assert tag in span["meta"], f"Can't find {tag} in span's meta"
        value = span["meta"][tag]
        if value != expected_value:
            raise Exception(f"{tag} value is '{value}', should be '{expected_value}'")

    return True


@features.event_tracking_sdk_v2
@scenarios.everything_disabled
class Test_UserLoginSuccessEventV2_AppsecDisabled:
    """Test that ATO SDK v2 login success events work correctly when DD_APPSEC_ENABLED=false.

    According to RFC-1017, when AppSec is disabled, the SDK must set the tags in the root span
    exactly as it would when AppSec is active, but calls to libddwaf and header collection
    must be prevented.
    """

    def get_user_login_success_tags_validator(self, login, user_id, metadata=None):
        def validate(span):
            expected_tags = {
                "appsec.events.users.login.success.usr.login": login,
                "appsec.events.users.login.success.usr.id": user_id,
                "usr.id": user_id,
                "appsec.events.users.login.success.track": "true",
                "_dd.appsec.events.users.login.success.sdk": "true",
                "_dd.appsec.user.collection_mode": "sdk",
            }

            return validate_tags_and_metadata(span, "appsec.events.users.login.success", expected_tags, metadata)

        return validate

    def setup_user_login_success_event_basic(self):
        """Test basic login success event when AppSec is disabled"""
        data = {"login": LOGIN_SAFE, "user_id": USER_ID_SAFE}
        self.r = weblog.post("/user_login_success_event_v2", json=data)

    def test_user_login_success_event_basic(self):
        """Verify that login success events still generate correct tags when AppSec is disabled"""
        assert self.r.status_code == 200

        interfaces.library.validate_spans(
            self.r, validator=self.get_user_login_success_tags_validator(LOGIN_SAFE, USER_ID_SAFE)
        )

    def setup_user_login_success_event_with_metadata(self):
        """Test login success event with metadata when AppSec is disabled"""
        metadata = {"custom_key": "custom_value", "session_id": "12345"}
        data = {"login": LOGIN_SAFE, "user_id": USER_ID_SAFE, "metadata": metadata}
        self.r = weblog.post("/user_login_success_event_v2", json=data)

    def test_user_login_success_event_with_metadata(self):
        """Verify that login success events with metadata work when AppSec is disabled"""
        assert self.r.status_code == 200

        metadata = {"custom_key": "custom_value", "session_id": "12345"}
        interfaces.library.validate_spans(
            self.r, validator=self.get_user_login_success_tags_validator(LOGIN_SAFE, USER_ID_SAFE, metadata)
        )

    def setup_user_login_success_no_appsec_events(self):
        """Test that no AppSec security events are generated when AppSec is disabled"""
        data = {"login": LOGIN_SAFE, "user_id": USER_ID_SAFE}
        self.r = weblog.post("/user_login_success_event_v2", json=data, headers=HEADERS)

    def test_user_login_success_no_appsec_events(self):
        """Verify that no AppSec security events are generated when AppSec is disabled"""
        assert self.r.status_code == 200

        # Verify that no AppSec events are generated
        interfaces.library.assert_no_appsec_event(self.r)

        # But SDK tags should still be present
        interfaces.library.validate_spans(
            self.r, validator=self.get_user_login_success_tags_validator(LOGIN_SAFE, USER_ID_SAFE)
        )


@features.event_tracking_sdk_v2
@scenarios.everything_disabled
class Test_UserLoginFailureEventV2_AppsecDisabled:
    """Test that ATO SDK v2 login failure events work correctly when DD_APPSEC_ENABLED=false.

    According to RFC-1017, when AppSec is disabled, the SDK must set the tags in the root span
    exactly as it would when AppSec is active, but calls to libddwaf and header collection
    must be prevented.
    """

    def get_user_login_failure_tags_validator(self, login, *, exists, metadata=None):
        def validate(span):
            expected_tags = {
                "appsec.events.users.login.failure.usr.login": login,
                "appsec.events.users.login.failure.usr.exists": str(exists).lower(),
                "appsec.events.users.login.failure.track": "true",
                "_dd.appsec.events.users.login.failure.sdk": "true",
            }

            return validate_tags_and_metadata(span, "appsec.events.users.login.failure", expected_tags, metadata)

        return validate

    def setup_user_login_failure_event_basic(self):
        """Test basic login failure event when AppSec is disabled"""
        data = {"login": LOGIN_SAFE, "exists": True}
        self.r = weblog.post("/user_login_failure_event_v2", json=data)

    def test_user_login_failure_event_basic(self):
        """Verify that login failure events still generate correct tags when AppSec is disabled"""
        assert self.r.status_code == 200

        interfaces.library.validate_spans(
            self.r, validator=self.get_user_login_failure_tags_validator(LOGIN_SAFE, exists=True)
        )

    def setup_user_login_failure_event_user_not_exists(self):
        """Test login failure event for non-existent user when AppSec is disabled"""
        data = {"login": LOGIN_SAFE, "exists": False}
        self.r = weblog.post("/user_login_failure_event_v2", json=data)

    def test_user_login_failure_event_user_not_exists(self):
        """Verify that login failure events work for non-existent users when AppSec is disabled"""
        assert self.r.status_code == 200

        interfaces.library.validate_spans(
            self.r, validator=self.get_user_login_failure_tags_validator(LOGIN_SAFE, exists=False)
        )

    def setup_user_login_failure_event_with_metadata(self):
        """Test login failure event with metadata when AppSec is disabled"""
        metadata = {"attempt_count": "3", "ip_address": "192.168.1.1"}
        data = {"login": LOGIN_SAFE, "exists": True, "metadata": metadata}
        self.r = weblog.post("/user_login_failure_event_v2", json=data)

    def test_user_login_failure_event_with_metadata(self):
        """Verify that login failure events with metadata work when AppSec is disabled"""
        assert self.r.status_code == 200

        metadata = {"attempt_count": "3", "ip_address": "192.168.1.1"}
        interfaces.library.validate_spans(
            self.r, validator=self.get_user_login_failure_tags_validator(LOGIN_SAFE, exists=True, metadata=metadata)
        )

    def setup_user_login_failure_no_appsec_events(self):
        """Test that no AppSec security events are generated when AppSec is disabled"""
        data = {"login": LOGIN_SAFE, "exists": False}
        self.r = weblog.post("/user_login_failure_event_v2", json=data, headers=HEADERS)

    def test_user_login_failure_no_appsec_events(self):
        """Verify that no AppSec security events are generated when AppSec is disabled"""
        assert self.r.status_code == 200

        # Verify that no AppSec events are generated
        interfaces.library.assert_no_appsec_event(self.r)

        # But SDK tags should still be present
        interfaces.library.validate_spans(
            self.r, validator=self.get_user_login_failure_tags_validator(LOGIN_SAFE, exists=False)
        )


@features.event_tracking_sdk_v2
@scenarios.everything_disabled
class Test_SDK_V2_Metrics_AppsecDisabled:
    """Test that ATO SDK v2 metrics are still generated when DD_APPSEC_ENABLED=false"""

    def validate_metric_type_and_version(self, event_type, version, metric):
        return (
            metric.get("type") == "count"
            and f"event_type:{event_type}" in metric.get("tags", ())
            and f"sdk_version:{version}" in metric.get("tags", ())
        )

    def setup_user_login_success_metrics(self):
        """Test that metrics are generated for login success events when AppSec is disabled"""
        data = {"login": LOGIN_SAFE, "user_id": USER_ID_SAFE}
        self.r = weblog.post("/user_login_success_event_v2", json=data)

    def test_user_login_success_metrics(self):
        """Verify that metrics are still generated for login success when AppSec is disabled"""
        assert self.r.status_code == 200

        # Check that SDK metrics are still generated
        success_metric_found = False
        for data, _trace, _span in interfaces.library.get_spans(request=self.r):
            for metric in data.get("request", {}).get("body", {}).get("series", []):
                if metric.get("metric") == "appsec.sdk.event" and self.validate_metric_type_and_version(
                    "login_success", "v2", metric
                ):
                    success_metric_found = True
                    break

        assert success_metric_found, "Expected login_success metric with v2 version not found"

    def setup_user_login_failure_metrics(self):
        """Test that metrics are generated for login failure events when AppSec is disabled"""
        data = {"login": LOGIN_SAFE, "exists": False}
        self.r = weblog.post("/user_login_failure_event_v2", json=data)

    def test_user_login_failure_metrics(self):
        """Verify that metrics are still generated for login failure when AppSec is disabled"""
        assert self.r.status_code == 200

        # Check that SDK metrics are still generated
        failure_metric_found = False
        for data, _trace, _span in interfaces.library.get_spans(request=self.r):
            for metric in data.get("request", {}).get("body", {}).get("series", []):
                if metric.get("metric") == "appsec.sdk.event" and self.validate_metric_type_and_version(
                    "login_failure", "v2", metric
                ):
                    failure_metric_found = True
                    break

        assert failure_metric_found, "Expected login_failure metric with v2 version not found"
