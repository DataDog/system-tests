# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import weblog, interfaces, features, scenarios, irrelevant
from tests.appsec.utils import find_series
from abc import ABC, abstractmethod

IP_HEADERS = {
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

HEADERS = {
    "Accept": "text/html",
    "Accept-Encoding": "br;q=1.0, gzip;q=0.8, *;q=0.1",
    "Accept-Language": "en-GB, *;q=0.5",
    "Content-Language": "en-GB",
    "Content-Type": "application/json; charset=utf-8",
    "Host": "127.0.0.1:1234",
    "User-Agent": "Benign User Agent 1.0",
    **IP_HEADERS,
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


def validate_tags_and_metadata(span, prefix, expected_tags, metadata, unexpected_metadata):
    if metadata is not None:
        for key, value in metadata.items():
            expected_tags[prefix + "." + key] = value

    for tag, expected_value in expected_tags.items():
        assert tag in span["meta"], f"Can't find {tag} in span's meta"
        value = span["meta"][tag]
        if value != expected_value:
            raise Exception(f"{tag} value is '{value}', should be '{expected_value}'")

    if unexpected_metadata is not None:
        for key in unexpected_metadata:
            tag = prefix + "." + key
            assert tag not in span["meta"], f"Tag {tag} found in span's meta"

    return True


class BaseUserLoginSuccessEventV2Tags:
    """Test tags created in User Login Success Event SDK v2"""

    def get_user_login_success_tags_validator(self, login, user_id, metadata=None, unexpected_metadata=None):
        def validate(span):
            expected_tags = {
                "appsec.events.users.login.success.usr.login": login,
                "appsec.events.users.login.success.usr.id": user_id,
                "usr.id": user_id,
                "appsec.events.users.login.success.track": "true",
                "_dd.appsec.events.users.login.success.sdk": "true",
                "_dd.appsec.user.collection_mode": "sdk",
            }

            return validate_tags_and_metadata(
                span, "appsec.events.users.login.success", expected_tags, metadata, unexpected_metadata
            )

        return validate

    def setup_user_login_success_event_strings_metadata(self):
        headers = {
            "X-Forwarded-For": "1.2.3.4",
        }

        metadata = {"metadata0": "value0", "metadata1": "value1"}

        data = {"login": LOGIN_SAFE, "user_id": USER_ID_SAFE, "metadata": metadata}

        self.r = weblog.post("/user_login_success_event_v2", json=data, headers=headers)

    def test_user_login_success_event_strings_metadata(self):
        # Call the user login success SDK and validate tags

        assert self.r.status_code == 200

        metadata = {"metadata0": "value0", "metadata1": "value1"}

        interfaces.library.validate_spans(
            self.r, validator=self.get_user_login_success_tags_validator(LOGIN_SAFE, USER_ID_SAFE, metadata=metadata)
        )

    def setup_user_login_success_event_multi_type_metadata(self):
        headers = {
            "X-Forwarded-For": "1.2.3.4",
        }

        metadata = {"metadata0": "value0", "metadata_number": 123, "metadata_boolean": True}

        data = {"login": LOGIN_SAFE, "user_id": USER_ID_SAFE, "metadata": metadata}

        self.r = weblog.post("/user_login_success_event_v2", json=data, headers=headers)

    @irrelevant(library="golang", reason="dd-trace-go only accepts string metadata values")
    @irrelevant(library="java", reason="dd-trace-java only accepts string metadata values")
    @irrelevant(library="php", reason="dd-trace-php only accepts string metadata values")
    def test_user_login_success_event_multi_type_metadata(self):
        # Call the user login success SDK and validate tags

        assert self.r.status_code == 200

        metadata = {"metadata0": "value0", "metadata_number": "123", "metadata_boolean": "true"}

        interfaces.library.validate_spans(
            self.r, validator=self.get_user_login_success_tags_validator(LOGIN_SAFE, USER_ID_SAFE, metadata=metadata)
        )

    def setup_user_login_success_event_no_metadata(self):
        headers = {
            "X-Forwarded-For": "1.2.3.4",
        }

        data = {"login": LOGIN_SAFE, "user_id": USER_ID_SAFE}

        self.r = weblog.post("/user_login_success_event_v2", json=data, headers=headers)

    def test_user_login_success_event_no_metadata(self):
        # Call the user login success SDK with no metadata and validate tags

        assert self.r.status_code == 200

        interfaces.library.validate_spans(
            self.r, validator=self.get_user_login_success_tags_validator(LOGIN_SAFE, USER_ID_SAFE)
        )

    @irrelevant(library="java", reason="dd-trace-java only accepts string metadata values")
    def setup_user_login_success_event_deep_metadata(self):
        headers = {
            "X-Forwarded-For": "1.2.3.4",
        }

        metadata = {
            "prop1": {"prop2": {"prop3": {"prop4": {"data1": "metavalue1", "prop5": {"prop6": "ignored value"}}}}},
            "arr": [{"key": "metavalue2"}, "metavalue3"],
        }

        data = {"login": LOGIN_SAFE, "user_id": USER_ID_SAFE, "metadata": metadata}

        self.r = weblog.post("/user_login_success_event_v2", json=data, headers=headers)

    @irrelevant(library="golang", reason="dd-trace-go only accepts string metadata values")
    @irrelevant(library="java", reason="dd-trace-java only accepts string metadata values")
    @irrelevant(library="dotnet", reason="dd-trace-dotnet only accepts string metadata values")
    @irrelevant(library="php", reason="dd-trace-php only accepts string metadata values")
    def test_user_login_success_event_deep_metadata(self):
        # Call the user login success SDK with deep metadata and validate tags

        assert self.r.status_code == 200

        metadata = {"prop1.prop2.prop3.prop4.data1": "metavalue1", "arr.0.key": "metavalue2", "arr.1": "metavalue3"}

        unexpected_metadata = ["prop1.prop2.prop3.prop4.prop5.prop6"]

        interfaces.library.validate_spans(
            self.r,
            validator=self.get_user_login_success_tags_validator(
                LOGIN_SAFE, USER_ID_SAFE, metadata, unexpected_metadata
            ),
        )


@features.event_tracking_sdk_v2
@scenarios.appsec_ato_sdk
class Test_UserLoginSuccessEventV2_Tags_AppsecEnabled(BaseUserLoginSuccessEventV2Tags):
    """Test tags created in AppSec User Login Success Event SDK v2 when appsec is enabled"""


@features.event_tracking_sdk_v2
@scenarios.everything_disabled
class Test_UserLoginSuccessEventV2_Tags_AppsecDisabled(BaseUserLoginSuccessEventV2Tags):
    """Test tags created in AppSec User Login Success Event SDK v2 when appsec is disabled"""


class BaseUserLoginSuccessEventV2HeaderCollection(ABC):
    """Test headers are collected in AppSec User Login Success Event SDK v2"""

    def setup_user_login_success_header_collection(self):
        data = {"login": LOGIN_SAFE, "user_id": USER_ID_SAFE}

        self.r = weblog.post("/user_login_success_event_v2", json=data, headers=HEADERS)

    @abstractmethod
    def test_user_login_success_header_collection(self):
        raise AssertionError("Not implemented")


@features.event_tracking_sdk_v2
@scenarios.appsec_ato_sdk
class Test_UserLoginSuccessEventV2_HeaderCollection_AppsecEnabled(BaseUserLoginSuccessEventV2HeaderCollection):
    """Test headers are collected in AppSec User Login Success Event SDK v2 when appsec is enabled"""

    def test_user_login_success_header_collection(self):
        # Validate that all relevant headers are included on login success SDK

        assert self.r.status_code == 200

        def validate_user_login_success_header_collection(span):
            if span.get("parent_id") not in (0, None):
                return None

            for header in HEADERS:
                assert f"http.request.headers.{header.lower()}" in span["meta"], f"Can't find {header} in span's meta"

            return True

        interfaces.library.validate_spans(self.r, validator=validate_user_login_success_header_collection)


@features.event_tracking_sdk_v2
@scenarios.everything_disabled
class Test_UserLoginSuccessEventV2_HeaderCollection_AppsecDisabled(BaseUserLoginSuccessEventV2HeaderCollection):
    """Test headers are not collected in User Login Success Event SDK v2 when appsec is disabled"""

    def test_user_login_success_header_collection(self):
        assert self.r.status_code == 200

        def validate_user_login_success_header_collection(span):
            if span.get("parent_id") not in (0, None):
                return None

            for header in IP_HEADERS:
                assert (
                    f"http.request.headers.{header.lower()}" not in span["meta"]
                ), f"Header {header} is found in span's meta. It should not be collected when appsec is disabled."

            return True

        interfaces.library.validate_spans(self.r, validator=validate_user_login_success_header_collection)


class BaseUserLoginSuccessEventV2Metrics:
    """Test metrics in AppSec User Login Success Event SDK v2"""

    def setup_user_login_success_event(self):
        data = {"login": LOGIN_SAFE, "user_id": USER_ID_SAFE}

        self.r = weblog.post("/user_login_success_event_v2", json=data)

    def test_user_login_success_event(self):
        # Call the user login success SDK and validate metrics

        assert self.r.status_code == 200

        series = find_series("appsec", ["sdk.event"])

        assert series
        assert any(validate_metric_type_and_version("login_success", "v2", s) for s in series), [
            s.get("tags") for s in series
        ]


@features.event_tracking_sdk_v2
@scenarios.appsec_ato_sdk
class Test_UserLoginSuccessEventV2_Metrics_AppsecEnabled(BaseUserLoginSuccessEventV2Metrics):
    """Test metrics in AppSec User Login Success Event SDK v2 when appsec is enabled"""


@features.event_tracking_sdk_v2
@scenarios.everything_disabled
class Test_UserLoginSuccessEventV2_Metrics_AppsecDisabled(BaseUserLoginSuccessEventV2Metrics):
    """Test metrics in AppSec User Login Success Event SDK v2 when appsec is disabled"""


@features.event_tracking_sdk_v2
@scenarios.appsec_ato_sdk
class Test_UserLoginSuccessEventV2_Libddwaf:
    """Test libddwaf calls in AppSec User Login Success Event SDK v2"""

    def setup_user_login_success_unsafe_login_success_event(self):
        data = {"login": LOGIN_SAFE, "user_id": USER_ID_SAFE}

        self.r = weblog.post("/user_login_success_event_v2", json=data)

    def test_user_login_success_unsafe_login_success_event(self):
        # Call the user login success SDK with unsafe login and validate threat

        assert self.r.status_code == 200

        interfaces.library.assert_waf_attack(self.r, rule="003_trigger_on_login_success")

    def setup_user_login_success_unsafe_login_event(self):
        data = {"login": LOGIN_IN_RULE, "user_id": USER_ID_SAFE}

        self.r = weblog.post("/user_login_success_event_v2", json=data)

    def test_user_login_success_unsafe_login_event(self):
        # Call the user login success SDK with unsafe login and validate threat

        assert self.r.status_code == 200

        interfaces.library.assert_waf_attack(self.r, rule="001_trigger_on_usr_login")
        interfaces.library.assert_waf_attack(self.r, rule="003_trigger_on_login_success")

    def setup_user_login_success_unsafe_user_id_event(self):
        data = {"login": LOGIN_SAFE, "user_id": USER_ID_IN_RULE}

        self.r = weblog.post("/user_login_success_event_v2", json=data)

    def test_user_login_success_unsafe_user_id_event(self):
        # Call the user login success SDK with unsafe user id and validate threat

        assert self.r.status_code == 200

        interfaces.library.assert_waf_attack(self.r, rule="002_trigger_on_usr_id")
        interfaces.library.assert_waf_attack(self.r, rule="003_trigger_on_login_success")


class BaseUserLoginFailureEventV2Tags:
    """Test created tags in AppSec User Login Failure Event SDK v2"""

    def get_user_login_failure_tags_validator(self, login, exists, metadata=None, unexpected_metadata=None):
        def validate(span):
            expected_tags = {
                "appsec.events.users.login.failure.usr.login": login,
                "appsec.events.users.login.failure.usr.exists": "true" if exists else "false",
                "appsec.events.users.login.failure.track": "true",
                "_dd.appsec.events.users.login.failure.sdk": "true",
            }

            return validate_tags_and_metadata(
                span, "appsec.events.users.login.failure", expected_tags, metadata, unexpected_metadata
            )

        return validate

    def setup_user_login_failure_event_exists(self):
        headers = {
            "X-Forwarded-For": "1.2.3.4",
        }

        metadata = {"metadata0": "value0", "metadata1": "value1"}

        data = {"login": LOGIN_SAFE, "exists": "true", "metadata": metadata}

        self.r = weblog.post("/user_login_failure_event_v2", json=data, headers=headers)

    def test_user_login_failure_event_exists(self):
        # Call the user login failure SDK with existing account and validate tags

        assert self.r.status_code == 200

        metadata = {"metadata0": "value0", "metadata1": "value1"}

        interfaces.library.validate_spans(
            self.r, validator=self.get_user_login_failure_tags_validator(LOGIN_SAFE, exists=True, metadata=metadata)
        )

    def setup_user_login_failure_event_does_not_exist(self):
        headers = {
            "X-Forwarded-For": "1.2.3.4",
        }

        metadata = {"metadata0": "value0", "metadata1": "value1"}

        data = {"login": LOGIN_SAFE, "exists": "false", "metadata": metadata}

        self.r = weblog.post("/user_login_failure_event_v2", json=data, headers=headers)

    def test_user_login_failure_event_does_not_exist(self):
        # Call the user login failure SDK with account that does not exist and validate tags

        assert self.r.status_code == 200

        metadata = {"metadata0": "value0", "metadata1": "value1"}

        interfaces.library.validate_spans(
            self.r, validator=self.get_user_login_failure_tags_validator(LOGIN_SAFE, exists=False, metadata=metadata)
        )

    def setup_user_login_failure_event_no_metadata(self):
        headers = {
            "X-Forwarded-For": "1.2.3.4",
        }

        data = {"login": LOGIN_SAFE, "exists": "false"}

        self.r = weblog.post("/user_login_failure_event_v2", json=data, headers=headers)

    def test_user_login_failure_event_no_metadata(self):
        # Call the user login failure SDK with no metadata and validate tags

        assert self.r.status_code == 200

        interfaces.library.validate_spans(
            self.r, validator=self.get_user_login_failure_tags_validator(LOGIN_SAFE, exists=False)
        )

    def setup_user_login_failure_event_deep_metadata(self):
        headers = {
            "X-Forwarded-For": "1.2.3.4",
        }

        metadata = {
            "prop1": {"prop2": {"prop3": {"prop4": {"data1": "metavalue1", "prop5": {"prop6": "ignored value"}}}}},
            "arr": [{"key": "metavalue2"}, "metavalue3"],
        }

        data = {"login": LOGIN_SAFE, "exists": "false", "metadata": metadata}

        self.r = weblog.post("/user_login_failure_event_v2", json=data, headers=headers)

    @irrelevant(library="golang", reason="dd-trace-go only accepts string metadata values")
    @irrelevant(library="java", reason="dd-trace-java only accepts string metadata values")
    @irrelevant(library="dotnet", reason="dd-trace-dotnet only accepts string metadata values")
    @irrelevant(library="php", reason="dd-trace-php only accepts string metadata values")
    def test_user_login_failure_event_deep_metadata(self):
        # Call the user login failure SDK with deep metadata and validate tags

        assert self.r.status_code == 200

        metadata = {"prop1.prop2.prop3.prop4.data1": "metavalue1", "arr.0.key": "metavalue2", "arr.1": "metavalue3"}

        unexpected_metadata = ["prop1.prop2.prop3.prop4.prop5.prop6"]

        interfaces.library.validate_spans(
            self.r,
            validator=self.get_user_login_failure_tags_validator(
                LOGIN_SAFE, exists=False, metadata=metadata, unexpected_metadata=unexpected_metadata
            ),
        )


@features.event_tracking_sdk_v2
@scenarios.appsec_ato_sdk
class Test_UserLoginFailureEventV2_Tags_AppsecEnabled(BaseUserLoginFailureEventV2Tags):
    """Test tags created in AppSec User Login Failure Event SDK v2 when appsec is enabled"""


@features.event_tracking_sdk_v2
@scenarios.everything_disabled
class Test_UserLoginFailureEventV2_Tags_AppsecDisabled(BaseUserLoginFailureEventV2Tags):
    """Test tags created in AppSec User Login Failure Event SDK v2 when appsec is disabled"""


class BaseUserLoginFailureEventV2HeaderCollection(ABC):
    """Test collected headers in AppSec User Login Failure Event SDK v2"""

    def setup_user_login_failure_header_collection(self):
        data = {"login": LOGIN_SAFE, "exists": "false"}

        self.r = weblog.post("/user_login_failure_event_v2", json=data, headers=HEADERS)

    @abstractmethod
    def test_user_login_failure_header_collection(self):
        raise AssertionError("Not implemented")


@features.event_tracking_sdk_v2
@scenarios.appsec_ato_sdk
class Test_UserLoginFailureEventV2_HeaderCollection_AppsecEnabled(BaseUserLoginFailureEventV2HeaderCollection):
    """Test headers are collected in AppSec User Login Failure Event SDK v2 when appsec is enabled"""

    def test_user_login_failure_header_collection(self):
        assert self.r.status_code == 200

        def validate_user_login_failure_header_collection(span):
            if span.get("parent_id") not in (0, None):
                return None

            for header in HEADERS:
                assert f"http.request.headers.{header.lower()}" in span["meta"], f"Can't find {header} in span's meta"

            return True

        interfaces.library.validate_spans(self.r, validator=validate_user_login_failure_header_collection)


@features.event_tracking_sdk_v2
@scenarios.everything_disabled
class Test_UserLoginFailureEventV2_HeaderCollection_AppsecDisabled(BaseUserLoginFailureEventV2HeaderCollection):
    """Test headers are not collected in User Login Failure Event SDK v2 when AppSec is disabled"""

    def test_user_login_failure_header_collection(self):
        assert self.r.status_code == 200

        def validate_user_login_failure_header_collection(span):
            if span.get("parent_id") not in (0, None):
                return None

            for header in IP_HEADERS:
                assert (
                    f"http.request.headers.{header.lower()}" not in span["meta"]
                ), f"Header {header} is found in span's meta. It should not be collected when appsec is disabled."

            return True

        interfaces.library.validate_spans(self.r, validator=validate_user_login_failure_header_collection)


class BaseUserLoginFailureEventV2Metrics:
    """Test metrics in AppSec User Login Failure Event SDK v2"""

    def setup_user_login_failure_event(self):
        data = {"login": LOGIN_SAFE, "exists": "true"}

        self.r = weblog.post("/user_login_failure_event_v2", json=data)

    def test_user_login_failure_event(self):
        # Call the user login success SDK and validate metrics

        assert self.r.status_code == 200

        series = find_series("appsec", ["sdk.event"])

        assert series
        assert any(validate_metric_type_and_version("login_failure", "v2", s) for s in series), [
            s.get("tags") for s in series
        ]


@features.event_tracking_sdk_v2
@scenarios.appsec_ato_sdk
class Test_UserLoginFailureEventV2_Metrics_AppsecEnabled(BaseUserLoginFailureEventV2Metrics):
    """Test metrics in AppSec User Login Failure Event SDK v2 when AppSec is enabled"""


@features.event_tracking_sdk_v2
@scenarios.everything_disabled
class Test_UserLoginFailureEventV2_Metrics_AppsecDisabled(BaseUserLoginFailureEventV2Metrics):
    """Test metrics in AppSec User Login Failure Event SDK v2 when AppSec is disabled"""


@features.event_tracking_sdk_v2
@scenarios.appsec_ato_sdk
class Test_UserLoginFailureEventV2_Libddwaf:
    """Test libddwaf calls in AppSec User Login Failure Event SDK v2"""

    def setup_user_login_failure_safe_login_event(self):
        data = {"login": LOGIN_SAFE, "exists": "true"}

        self.r = weblog.post("/user_login_failure_event_v2", json=data)

    def test_user_login_failure_safe_login_event(self):
        # Call the user login failure SDK with unsafe login and validate threat

        assert self.r.status_code == 200

        interfaces.library.assert_waf_attack(self.r, rule="004_trigger_on_login_failure")

    def setup_user_login_failure_unsafe_login_event(self):
        data = {"login": LOGIN_IN_RULE, "exists": "true"}

        self.r = weblog.post("/user_login_failure_event_v2", json=data)

    def test_user_login_failure_unsafe_login_event(self):
        # Call the user login failure SDK with unsafe login and validate threat

        assert self.r.status_code == 200

        interfaces.library.assert_waf_attack(self.r, rule="001_trigger_on_usr_login")
        interfaces.library.assert_waf_attack(self.r, rule="004_trigger_on_login_failure")
