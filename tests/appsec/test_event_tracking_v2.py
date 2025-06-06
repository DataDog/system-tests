# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import weblog, interfaces, features, scenarios, irrelevant
from tests.appsec.utils import find_series

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


@features.event_tracking_sdk_v2
@scenarios.appsec_ato_sdk
class Test_UserLoginSuccessEventV2_Tags:
    """Test tags created in AppSec User Login Success Event SDK v2"""

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
class Test_UserLoginSuccessEventV2_HeaderCollection:
    """Test headers are collected in AppSec User Login Success Event SDK v2"""

    def setup_user_login_success_header_collection(self):
        data = {"login": LOGIN_SAFE, "user_id": USER_ID_SAFE}

        self.r = weblog.post("/user_login_success_event_v2", json=data, headers=HEADERS)

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
@scenarios.appsec_ato_sdk
class Test_UserLoginSuccessEventV2_Metrics:
    """Test metrics in AppSec User Login Success Event SDK v2"""

    def setup_user_login_success_event(self):
        data = {"login": LOGIN_SAFE, "user_id": USER_ID_SAFE}

        self.r = weblog.post("/user_login_success_event_v2", json=data)

    def test_user_login_success_event(self):
        # Call the user login success SDK and validate metrics

        assert self.r.status_code == 200

        series = find_series("generate-metrics", "appsec", ["sdk.event"])

        assert series
        assert any(validate_metric_type_and_version("login_success", "v2", s) for s in series), [
            s.get("tags") for s in series
        ]


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


@features.event_tracking_sdk_v2
@scenarios.appsec_ato_sdk
class Test_UserLoginFailureEventV2_Tags:
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
class Test_UserLoginFailureEventV2_HeaderCollection:
    """Test collected headers in AppSec User Login Failure Event SDK v2"""

    def setup_user_login_failure_header_collection(self):
        data = {"login": LOGIN_SAFE, "exists": "false"}

        self.r = weblog.post("/user_login_failure_event_v2", json=data, headers=HEADERS)

    def test_user_login_failure_header_collection(self):
        # Validate that all relevant headers are included on user login failure

        assert self.r.status_code == 200

        def validate_user_login_failure_header_collection(span):
            if span.get("parent_id") not in (0, None):
                return None

            for header in HEADERS:
                assert f"http.request.headers.{header.lower()}" in span["meta"], f"Can't find {header} in span's meta"

            return True

        interfaces.library.validate_spans(self.r, validator=validate_user_login_failure_header_collection)


@features.event_tracking_sdk_v2
@scenarios.appsec_ato_sdk
class Test_UserLoginFailureEventV2_Metrics:
    """Test metrics in AppSec User Login Failure Event SDK v2"""

    def setup_user_login_failure_event(self):
        data = {"login": LOGIN_SAFE, "exists": "true"}

        self.r = weblog.post("/user_login_failure_event_v2", json=data)

    def test_user_login_failure_event(self):
        # Call the user login success SDK and validate metrics

        assert self.r.status_code == 200

        series = find_series("generate-metrics", "appsec", ["sdk.event"])

        assert series
        assert any(validate_metric_type_and_version("login_failure", "v2", s) for s in series), [
            s.get("tags") for s in series
        ]


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


@features.event_tracking_sdk_v2
@scenarios.ato_sdk
class Test_UserLoginSuccessEventV2_Tags_AppsecDisabled:
    """Test tags created in AppSec User Login Success Event SDK v2 when AppSec is disabled"""

    def get_user_login_success_tags_validator_appsec_disabled(
        self, login, user_id, metadata=None, unexpected_metadata=None
    ):
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

    def setup_user_login_success_event_strings_metadata_appsec_disabled(self):
        headers = {
            "X-Forwarded-For": "1.2.3.4",
        }

        metadata = {"metadata0": "value0", "metadata1": "value1"}

        data = {"login": LOGIN_SAFE, "user_id": USER_ID_SAFE, "metadata": metadata}

        self.r = weblog.post("/user_login_success_event_v2", json=data, headers=headers)

    def test_user_login_success_event_strings_metadata_appsec_disabled(self):
        # Call the user login success SDK with AppSec disabled and validate tags

        assert self.r.status_code == 200

        metadata = {"metadata0": "value0", "metadata1": "value1"}

        interfaces.library.validate_spans(
            self.r,
            validator=self.get_user_login_success_tags_validator_appsec_disabled(
                LOGIN_SAFE, USER_ID_SAFE, metadata=metadata
            ),
        )

    def setup_user_login_success_event_no_metadata_appsec_disabled(self):
        headers = {
            "X-Forwarded-For": "1.2.3.4",
        }

        data = {"login": LOGIN_SAFE, "user_id": USER_ID_SAFE}

        self.r = weblog.post("/user_login_success_event_v2", json=data, headers=headers)

    def test_user_login_success_event_no_metadata_appsec_disabled(self):
        # Call the user login success SDK with no metadata when AppSec is disabled and validate tags

        assert self.r.status_code == 200

        interfaces.library.validate_spans(
            self.r, validator=self.get_user_login_success_tags_validator_appsec_disabled(LOGIN_SAFE, USER_ID_SAFE)
        )


@features.event_tracking_sdk_v2
@scenarios.ato_sdk
class Test_UserLoginSuccessEventV2_HeaderCollection_AppsecDisabled:
    """Test that headers are NOT collected in AppSec User Login Success Event SDK v2 when AppSec is disabled"""

    def setup_user_login_success_header_collection_appsec_disabled(self):
        data = {"login": LOGIN_SAFE, "user_id": USER_ID_SAFE}

        self.r = weblog.post("/user_login_success_event_v2", json=data, headers=HEADERS)

    def test_user_login_success_header_collection_appsec_disabled(self):
        # Validate that headers are NOT collected when AppSec is disabled and login success SDK is used

        assert self.r.status_code == 200

        def validate_user_login_success_no_header_collection(span):
            if span.get("parent_id") not in (0, None):
                return None

            # When AppSec is disabled, headers should NOT be collected
            for header in HEADERS:
                key = f"http.request.headers.{header.lower()}"
                # Assert that headers are NOT present in the span
                assert key not in span.get("meta", {}), f"Header {key} should not be collected when AppSec is disabled"

            return True

        interfaces.library.validate_spans(self.r, validator=validate_user_login_success_no_header_collection)


@features.event_tracking_sdk_v2
@scenarios.ato_sdk
class Test_UserLoginSuccessEventV2_Metrics_AppsecDisabled:
    """Test metrics created in AppSec User Login Success Event SDK v2 when AppSec is disabled"""

    def setup_user_login_success_event_appsec_disabled(self):
        data = {"login": LOGIN_SAFE, "user_id": USER_ID_SAFE}

        self.r = weblog.post("/user_login_success_event_v2", json=data)

    def test_user_login_success_event_appsec_disabled(self):
        # Call the user login success SDK when AppSec is disabled and validate metrics

        assert self.r.status_code == 200

        # Metrics should still be sent even when AppSec is disabled
        def validate_login_success_metrics(log):
            metric = log.get("metric")
            if metric is not None and metric.get("name") == "appsec.sdk.event":
                return validate_metric_type_and_version("login_success", "v2", metric)
            return False

        interfaces.library.validate_telemetry(validate_login_success_metrics)


@features.event_tracking_sdk_v2
@scenarios.ato_sdk
class Test_UserLoginSuccessEventV2_NoLibddwaf_AppsecDisabled:
    """Test that libddwaf is NOT called in AppSec User Login Success Event SDK v2 when AppSec is disabled"""

    def setup_user_login_success_no_libddwaf_appsec_disabled(self):
        headers = {
            "X-Forwarded-For": "1.2.3.4",
        }

        # Use safe values - when AppSec is disabled, libddwaf should not be called regardless
        data = {"login": LOGIN_SAFE, "user_id": USER_ID_SAFE}

        self.r = weblog.post("/user_login_success_event_v2", json=data, headers=headers)

    def test_user_login_success_no_libddwaf_appsec_disabled(self):
        # Call the user login success SDK when AppSec is disabled and validate no libddwaf calls

        assert self.r.status_code == 200

        # No security events should be generated when AppSec is disabled
        def validate_no_security_events(span):
            if span.get("parent_id") not in (0, None):
                return None

            # Ensure no appsec security events are present
            meta = span.get("meta", {})
            for key in meta:
                assert not key.startswith(
                    "_dd.appsec.event_rules"
                ), f"Security event {key} should not be present when AppSec is disabled"

            return True

        interfaces.library.validate_spans(self.r, validator=validate_no_security_events)


@features.event_tracking_sdk_v2
@scenarios.ato_sdk
class Test_UserLoginFailureEventV2_Tags_AppsecDisabled:
    """Test tags created in AppSec User Login Failure Event SDK v2 when AppSec is disabled"""

    def get_user_login_failure_tags_validator_appsec_disabled(
        self, login, exists, metadata=None, unexpected_metadata=None
    ):
        def validate(span):
            expected_tags = {
                "appsec.events.users.login.failure.usr.login": login,
                "appsec.events.users.login.failure.usr.exists": exists,
                "appsec.events.users.login.failure.track": "true",
                "_dd.appsec.events.users.login.failure.sdk": "true",
            }

            return validate_tags_and_metadata(
                span, "appsec.events.users.login.failure", expected_tags, metadata, unexpected_metadata
            )

        return validate

    def setup_user_login_failure_event_exists_appsec_disabled(self):
        headers = {
            "X-Forwarded-For": "1.2.3.4",
        }

        metadata = {"metadata0": "value0", "metadata1": "value1"}

        data = {"login": LOGIN_SAFE, "exists": True, "metadata": metadata}

        self.r = weblog.post("/user_login_failure_event_v2", json=data, headers=headers)

    def test_user_login_failure_event_exists_appsec_disabled(self):
        # Call the user login failure SDK with existing account when AppSec is disabled and validate tags

        assert self.r.status_code == 200

        metadata = {"metadata0": "value0", "metadata1": "value1"}

        interfaces.library.validate_spans(
            self.r,
            validator=self.get_user_login_failure_tags_validator_appsec_disabled(LOGIN_SAFE, "true", metadata=metadata),
        )

    def setup_user_login_failure_event_does_not_exist_appsec_disabled(self):
        headers = {
            "X-Forwarded-For": "1.2.3.4",
        }

        metadata = {"metadata0": "value0", "metadata1": "value1"}

        data = {"login": LOGIN_SAFE, "exists": False, "metadata": metadata}

        self.r = weblog.post("/user_login_failure_event_v2", json=data, headers=headers)

    def test_user_login_failure_event_does_not_exist_appsec_disabled(self):
        # Call the user login failure SDK with account that does not exist when AppSec is disabled and validate tags

        assert self.r.status_code == 200

        metadata = {"metadata0": "value0", "metadata1": "value1"}

        interfaces.library.validate_spans(
            self.r,
            validator=self.get_user_login_failure_tags_validator_appsec_disabled(
                LOGIN_SAFE, "false", metadata=metadata
            ),
        )

    def setup_user_login_failure_event_no_metadata_appsec_disabled(self):
        headers = {
            "X-Forwarded-For": "1.2.3.4",
        }

        data = {"login": LOGIN_SAFE, "exists": True}

        self.r = weblog.post("/user_login_failure_event_v2", json=data, headers=headers)

    def test_user_login_failure_event_no_metadata_appsec_disabled(self):
        # Call the user login failure SDK with no metadata when AppSec is disabled and validate tags

        assert self.r.status_code == 200

        interfaces.library.validate_spans(
            self.r, validator=self.get_user_login_failure_tags_validator_appsec_disabled(LOGIN_SAFE, "true")
        )


@features.event_tracking_sdk_v2
@scenarios.ato_sdk
class Test_UserLoginFailureEventV2_HeaderCollection_AppsecDisabled:
    """Test that headers are NOT collected in AppSec User Login Failure Event SDK v2 when AppSec is disabled"""

    def setup_user_login_failure_header_collection_appsec_disabled(self):
        data = {"login": LOGIN_SAFE, "exists": True}

        self.r = weblog.post("/user_login_failure_event_v2", json=data, headers=HEADERS)

    def test_user_login_failure_header_collection_appsec_disabled(self):
        # Validate that headers are NOT collected when AppSec is disabled and user login failure SDK is used

        assert self.r.status_code == 200

        def validate_user_login_failure_no_header_collection(span):
            if span.get("parent_id") not in (0, None):
                return None

            # When AppSec is disabled, headers should NOT be collected
            for header in HEADERS:
                key = f"http.request.headers.{header.lower()}"
                # Assert that headers are NOT present in the span
                assert key not in span.get("meta", {}), f"Header {key} should not be collected when AppSec is disabled"

            return True

        interfaces.library.validate_spans(self.r, validator=validate_user_login_failure_no_header_collection)


@features.event_tracking_sdk_v2
@scenarios.ato_sdk
class Test_UserLoginFailureEventV2_Metrics_AppsecDisabled:
    """Test metrics created in AppSec User Login Failure Event SDK v2 when AppSec is disabled"""

    def setup_user_login_failure_event_appsec_disabled(self):
        data = {"login": LOGIN_SAFE, "exists": True}

        self.r = weblog.post("/user_login_failure_event_v2", json=data)

    def test_user_login_failure_event_appsec_disabled(self):
        # Call the user login failure SDK when AppSec is disabled and validate metrics

        assert self.r.status_code == 200

        # Metrics should still be sent even when AppSec is disabled
        def validate_login_failure_metrics(log):
            metric = log.get("metric")
            if metric is not None and metric.get("name") == "appsec.sdk.event":
                return validate_metric_type_and_version("login_failure", "v2", metric)
            return False

        interfaces.library.validate_telemetry(validate_login_failure_metrics)


@features.event_tracking_sdk_v2
@scenarios.ato_sdk
class Test_UserLoginFailureEventV2_NoLibddwaf_AppsecDisabled:
    """Test that libddwaf is NOT called in AppSec User Login Failure Event SDK v2 when AppSec is disabled"""

    def setup_user_login_failure_no_libddwaf_appsec_disabled(self):
        headers = {
            "X-Forwarded-For": "1.2.3.4",
        }

        # Use safe values - when AppSec is disabled, libddwaf should not be called regardless
        data = {"login": LOGIN_SAFE, "exists": True}

        self.r = weblog.post("/user_login_failure_event_v2", json=data, headers=headers)

    def test_user_login_failure_no_libddwaf_appsec_disabled(self):
        # Call the user login failure SDK when AppSec is disabled and validate no libddwaf calls

        assert self.r.status_code == 200

        # No security events should be generated when AppSec is disabled
        def validate_no_security_events(span):
            if span.get("parent_id") not in (0, None):
                return None

            # Ensure no appsec security events are present
            meta = span.get("meta", {})
            for key in meta:
                assert not key.startswith(
                    "_dd.appsec.event_rules"
                ), f"Security event {key} should not be present when AppSec is disabled"

            return True

        interfaces.library.validate_spans(self.r, validator=validate_no_security_events)
