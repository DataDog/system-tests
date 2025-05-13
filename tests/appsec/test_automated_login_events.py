# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

from utils import bug
from utils import context
from utils import features
from utils import interfaces
from utils import irrelevant
from utils import missing_feature
from utils import remote_config as rc
from utils import rfc
from utils import scenarios
from utils import weblog
from utils.dd_constants import Capabilities, SamplingPriority


def login_data(context, username, password):
    """In Rails the parameters are group by scope. In the case of the test the scope is user.
    The syntax to group parameters in a POST request is scope[parameter]
    """
    username_key = "user[username]" if "rails" in context.weblog_variant else "username"
    password_key = "user[password]" if "rails" in context.weblog_variant else "password"
    return {username_key: username, password_key: password}


USER = "test"
UUID_USER = "testuuid"
PASSWORD = "1234"
INVALID_USER = "invalidUser"
NEW_USER = "testnew"
USER_HASH = "anon_5f31ffaf95946d2dc703ddc96a100de5"
USERNAME_HASH = "anon_9f86d081884c7d659a2feaa0c55ad015"
INVALID_USER_HASH = "anon_2141e3bee69f7de45b4f1d8d1f29258a"
NEW_USER_HASH = "anon_6724757d2d9a8113ec9ec57003bf7b3e"
NEW_USERNAME_HASH = "anon_3de740d12dc67b5b1db699424c130847"

BASIC_AUTH_USER_HEADER = "Basic dGVzdDoxMjM0"  # base64(test:1234)
BASIC_AUTH_USER_UUID_HEADER = "Basic dGVzdHV1aWQ6MTIzNA=="  # base64(testuuid:1234)
BASIC_AUTH_INVALID_USER_HEADER = "Basic aW52YWxpZFVzZXI6MTIzNA=="  # base64(invalidUser:1234)
BASIC_AUTH_INVALID_PASSWORD_HEADER = "Basic dGVzdDoxMjM0NQ=="  # base64(test:12345)

HEADERS = {
    "Accept": "text/html",
    "Accept-Encoding": "br;q=1.0, gzip;q=0.8, *;q=0.1",
    "Accept-Language": "en-GB, *;q=0.5",
    "Content-Language": "en-GB",
    "Content-Length": "0",
    "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
    # removed because the request is not using this encoding to make the request and makes the test fail
    # "Content-Encoding": "deflate, gzip",
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

# when to trigger the SDK in login endpoints (before/after automated instrumentation)
SDK_TRIGGERS = ["before", "after"]


@rfc("https://docs.google.com/document/d/1-trUpphvyZY7k5ldjhW-MgqWl0xOm7AMEQDJEAZ63_Q/edit#heading=h.8d3o7vtyu1y1")
@features.user_monitoring
class Test_Login_Events:
    """Test login success/failure use cases"""

    # User entries in the internal DB:
    # users = [
    #     {
    #         id: 'social-security-id',
    #         username: 'test',
    #         password: '1234',
    #         email: 'testuser@ddog.com'
    #     },
    #     {
    #         id: '591dc126-8431-4d0f-9509-b23318d3dce4',
    #         username: 'testuuid',
    #         password: '1234',
    #         email: 'testuseruuid@ddog.com'
    #     }
    # ]

    def setup_login_pii_success_local(self):
        self.r_pii_success = weblog.post("/login?auth=local", data=login_data(context, USER, PASSWORD))

    @bug(context.library < "nodejs@4.9.0", reason="APMRP-360")
    @irrelevant(
        context.library == "python" and context.weblog_variant in ["django-poc", "python3.12"],
        reason="APM reports all user id for now on Django",
    )
    def test_login_pii_success_local(self):
        assert self.r_pii_success.status_code == 200
        for _, trace, span in interfaces.library.get_spans(request=self.r_pii_success):
            meta = span.get("meta", {})
            assert "usr.id" not in meta
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "safe"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert_priority(span, trace)

    def setup_login_pii_success_basic(self):
        self.r_pii_success = weblog.get("/login?auth=basic", headers={"Authorization": BASIC_AUTH_USER_HEADER})

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    @bug(context.library < "nodejs@4.9.0", reason="APMRP-360")
    @irrelevant(
        context.library == "python" and context.weblog_variant in ["django-poc", "python3.12"],
        reason="APM reports all user id for now on Django",
    )
    def test_login_pii_success_basic(self):
        assert self.r_pii_success.status_code == 200
        for _, trace, span in interfaces.library.get_spans(request=self.r_pii_success):
            meta = span.get("meta", {})
            assert "usr.id" not in meta
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "safe"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert_priority(span, trace)

    def setup_login_success_local(self):
        self.r_success = weblog.post("/login?auth=local", data=login_data(context, UUID_USER, PASSWORD))

    def test_login_success_local(self):
        assert self.r_success.status_code == 200
        for _, trace, span in interfaces.library.get_spans(request=self.r_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "safe"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == "591dc126-8431-4d0f-9509-b23318d3dce4"
            assert_priority(span, trace)

    def setup_login_success_basic(self):
        self.r_success = weblog.get("/login?auth=basic", headers={"Authorization": BASIC_AUTH_USER_UUID_HEADER})

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    def test_login_success_basic(self):
        assert self.r_success.status_code == 200
        for _, trace, span in interfaces.library.get_spans(request=self.r_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "safe"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == "591dc126-8431-4d0f-9509-b23318d3dce4"
            assert_priority(span, trace)

    def setup_login_wrong_user_failure_local(self):
        self.r_wrong_user_failure = weblog.post("/login?auth=local", data=login_data(context, INVALID_USER, PASSWORD))

    @bug(context.library < "nodejs@4.9.0", reason="APMRP-360")
    @missing_feature(weblog_variant="spring-boot-openliberty", reason="weblog returns error 500")
    def test_login_wrong_user_failure_local(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            if context.library not in ("nodejs", "java"):
                # Currently in nodejs/java there is no way to check if the user exists upon authentication failure so
                # this assertion is disabled for this library.
                assert meta["appsec.events.users.login.failure.usr.exists"] == "false"

            assert "appsec.events.users.login.failure.usr.id" not in meta
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "safe"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert_priority(span, trace)

    def setup_login_wrong_user_failure_basic(self):
        self.r_wrong_user_failure = weblog.get(
            "/login?auth=basic", headers={"Authorization": BASIC_AUTH_INVALID_USER_HEADER}
        )

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    @bug(context.library < "nodejs@4.9.0", reason="APMRP-360")
    @missing_feature(weblog_variant="spring-boot-openliberty", reason="weblog returns error 500")
    def test_login_wrong_user_failure_basic(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            if context.library not in ("nodejs", "java"):
                # Currently in nodejs/java there is no way to check if the user exists upon authentication failure so
                # this assertion is disabled for this library.
                assert meta["appsec.events.users.login.failure.usr.exists"] == "false"

            assert "appsec.events.users.login.failure.usr.id" not in meta
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "safe"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert_priority(span, trace)

    def setup_login_wrong_password_failure_local(self):
        self.r_wrong_user_failure = weblog.post("/login?auth=local", data=login_data(context, USER, "12345"))

    @bug(context.library < "nodejs@4.9.0", reason="APMRP-360")
    @missing_feature(weblog_variant="spring-boot-openliberty", reason="weblog returns error 500")
    def test_login_wrong_password_failure_local(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            if context.library not in ("nodejs", "java"):
                # Currently in nodejs/java there is no way to check if the user exists upon authentication failure so
                # this assertion is disabled for this library.
                assert meta["appsec.events.users.login.failure.usr.exists"] == "true"

            assert "appsec.events.users.login.failure.usr.id" not in meta
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "safe"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert_priority(span, trace)

    def setup_login_wrong_password_failure_basic(self):
        self.r_wrong_user_failure = weblog.get(
            "/login?auth=basic", headers={"Authorization": BASIC_AUTH_INVALID_PASSWORD_HEADER}
        )

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    @bug(context.library < "nodejs@4.9.0", reason="APMRP-360")
    @missing_feature(weblog_variant="spring-boot-openliberty", reason="weblog returns error 500")
    def test_login_wrong_password_failure_basic(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            if context.library not in ("nodejs", "java"):
                # Currently in nodejs/java there is no way to check if the user exists upon authentication failure so
                # this assertion is disabled for this library.
                assert meta["appsec.events.users.login.failure.usr.exists"] == "true"

            assert "appsec.events.users.login.failure.usr.id" not in meta
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "safe"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert_priority(span, trace)

    def setup_login_sdk_success_local(self):
        self.r_sdk_success = weblog.post(
            "/login?auth=local&sdk_event=success&sdk_user=sdkUser",
            data=login_data(context, USER, PASSWORD),
        )

    def test_login_sdk_success_local(self):
        assert self.r_sdk_success.status_code == 200
        for _, trace, span in interfaces.library.get_spans(request=self.r_sdk_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "safe"
            assert meta["_dd.appsec.events.users.login.success.sdk"] == "true"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == "sdkUser"
            assert_priority(span, trace)

    def setup_login_sdk_success_basic(self):
        self.r_sdk_success = weblog.get(
            "/login?auth=basic&sdk_event=success&sdk_user=sdkUser",
            headers={"Authorization": BASIC_AUTH_USER_HEADER},
        )

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    def test_login_sdk_success_basic(self):
        assert self.r_sdk_success.status_code == 200
        for _, trace, span in interfaces.library.get_spans(request=self.r_sdk_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "safe"
            assert meta["_dd.appsec.events.users.login.success.sdk"] == "true"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == "sdkUser"
            assert_priority(span, trace)

    def setup_login_sdk_failure_local(self):
        self.r_sdk_failure = weblog.post(
            "/login?auth=local&sdk_event=failure&sdk_user=sdkUser&sdk_user_exists=true",
            data=login_data(context, INVALID_USER, PASSWORD),
        )

    @missing_feature(weblog_variant="spring-boot-openliberty", reason="weblog returns error 500")
    def test_login_sdk_failure_local(self):
        assert self.r_sdk_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_sdk_failure):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "safe"
            assert meta["_dd.appsec.events.users.login.failure.sdk"] == "true"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert meta["appsec.events.users.login.failure.usr.id"] == "sdkUser"
            assert meta["appsec.events.users.login.failure.usr.exists"] == "true"
            assert_priority(span, trace)

    def setup_login_sdk_failure_basic(self):
        self.r_sdk_failure = weblog.get(
            "/login?auth=basic&sdk_event=failure&sdk_user=sdkUser&sdk_user_exists=true",
            headers={"Authorization": BASIC_AUTH_INVALID_USER_HEADER},
        )

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    @missing_feature(weblog_variant="spring-boot-openliberty", reason="weblog returns error 500")
    def test_login_sdk_failure_basic(self):
        assert self.r_sdk_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_sdk_failure):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "safe"
            assert meta["_dd.appsec.events.users.login.failure.sdk"] == "true"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert meta["appsec.events.users.login.failure.usr.id"] == "sdkUser"
            assert meta["appsec.events.users.login.failure.usr.exists"] == "true"
            assert_priority(span, trace)


@rfc("https://docs.google.com/document/d/1-trUpphvyZY7k5ldjhW-MgqWl0xOm7AMEQDJEAZ63_Q/edit#heading=h.8d3o7vtyu1y1")
@scenarios.appsec_auto_events_extended
@features.user_monitoring
class Test_Login_Events_Extended:
    """Test login success/failure use cases"""

    def setup_login_success_local(self):
        self.r_success = weblog.post("/login?auth=local", data=login_data(context, USER, PASSWORD))

    def test_login_success_local(self):
        assert self.r_success.status_code == 200
        for _, trace, span in interfaces.library.get_spans(request=self.r_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "extended"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == "social-security-id"

            if context.library in ("dotnet", "python"):
                # theres no login field in dotnet
                # usr.name was in the sdk before so it was kept as is
                assert meta["usr.email"] == "testuser@ddog.com"
                assert meta["usr.name"] == "test"
            elif context.library == "php":
                assert meta["appsec.events.users.login.success.username"] == "test"
                assert meta["appsec.events.users.login.success.email"] == "testuser@ddog.com"
            elif context.library == "ruby":
                # theres no login field in ruby
                assert meta["usr.email"] == "testuser@ddog.com"
                assert meta["usr.username"] == "test"
            elif context.library != "java":
                # there are no extra fields in java
                assert meta["usr.email"] == "testuser@ddog.com"
                assert meta["usr.username"] == "test"
                assert meta["usr.login"] == "test"

            assert_priority(span, trace)

    def setup_login_success_basic(self):
        self.r_success = weblog.get("/login?auth=basic", headers={"Authorization": BASIC_AUTH_USER_HEADER})

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    def test_login_success_basic(self):
        assert self.r_success.status_code == 200
        for _, trace, span in interfaces.library.get_spans(request=self.r_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "extended"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == "social-security-id"

            if context.library in ("dotnet", "python"):
                # theres no login field in dotnet
                # usr.name was in the sdk before so it was kept as is
                assert meta["usr.name"] == "test"
                assert meta["usr.email"] == "testuser@ddog.com"
            elif context.library == "ruby":
                # theres no login field in ruby
                assert meta["usr.username"] == "test"
                assert meta["usr.email"] == "testuser@ddog.com"
            elif context.library != "java":
                # there are no extra fields in java
                assert meta["usr.username"] == "test"
                assert meta["usr.login"] == "test"
                assert meta["usr.email"] == "testuser@ddog.com"

            assert_priority(span, trace)

    def setup_login_wrong_user_failure_local(self):
        self.r_wrong_user_failure = weblog.post("/login?auth=local", data=login_data(context, INVALID_USER, PASSWORD))

    @missing_feature(weblog_variant="spring-boot-openliberty", reason="weblog returns error 500")
    def test_login_wrong_user_failure_local(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            if context.library not in ("nodejs", "java"):
                # Currently in nodejs/java there is no way to check if the user exists upon authentication failure so
                # this assertion is disabled for this library.
                assert meta["appsec.events.users.login.failure.usr.exists"] == "false"

            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "extended"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            if context.library == "ruby":
                # In ruby we do not have access to the user object since it fails with invalid username
                # For that reason we can not extract id, email or username
                assert meta.get("appsec.events.users.login.failure.usr.id") is None
                assert meta.get("appsec.events.users.login.failure.usr.email") is None
                assert meta.get("appsec.events.users.login.failure.usr.username") is None
            elif context.library == "dotnet":
                # in dotnet if the user doesn't exist, there is no id (generated upon user creation)
                assert meta["appsec.events.users.login.failure.username"] == INVALID_USER
            else:
                assert meta["appsec.events.users.login.failure.usr.id"] == INVALID_USER
            assert_priority(span, trace)

    def setup_login_wrong_user_failure_basic(self):
        self.r_wrong_user_failure = weblog.get(
            "/login?auth=basic", headers={"Authorization": BASIC_AUTH_INVALID_USER_HEADER}
        )

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    @missing_feature(weblog_variant="spring-boot-openliberty", reason="weblog returns error 500")
    def test_login_wrong_user_failure_basic(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            if context.library not in ("nodejs", "java"):
                # Currently in nodejs/java there is no way to check if the user exists upon authentication failure so
                # this assertion is disabled for this library.
                assert meta["appsec.events.users.login.failure.usr.exists"] == "false"

            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "extended"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            if context.library == "ruby":
                # In ruby we do not have access to the user object since it fails with invalid username
                # For that reason we can not extract id, email or username
                assert meta.get("appsec.events.users.login.failure.usr.id") is None
                assert meta.get("appsec.events.users.login.failure.usr.email") is None
                assert meta.get("appsec.events.users.login.failure.usr.username") is None
            elif context.library == "dotnet":
                # in dotnet if the user doesn't exist, there is no id (generated upon user creation)
                assert meta["appsec.events.users.login.failure.username"] == INVALID_USER
            else:
                assert meta["appsec.events.users.login.failure.usr.id"] == INVALID_USER
            assert_priority(span, trace)

    def setup_login_wrong_password_failure_local(self):
        self.r_wrong_user_failure = weblog.post("/login?auth=local", data=login_data(context, USER, "12345"))

    @missing_feature(weblog_variant="spring-boot-openliberty", reason="weblog returns error 500")
    def test_login_wrong_password_failure_local(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            if context.library in ("nodejs", "java"):
                # Currently in nodejs/java there is no way to check if the user exists upon authentication failure so
                # this assertion is disabled for this library.
                assert meta["appsec.events.users.login.failure.usr.id"] == "test"
            else:
                assert meta["appsec.events.users.login.failure.usr.exists"] == "true"
                assert meta["appsec.events.users.login.failure.usr.id"] == "social-security-id"
                assert meta["appsec.events.users.login.failure.email"] == "testuser@ddog.com"
                assert meta["appsec.events.users.login.failure.username"] == "test"

            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "extended"
            assert meta["appsec.events.users.login.failure.track"] == "true"

            assert_priority(span, trace)

    def setup_login_wrong_password_failure_basic(self):
        self.r_wrong_user_failure = weblog.get(
            "/login?auth=basic", headers={"Authorization": BASIC_AUTH_INVALID_PASSWORD_HEADER}
        )

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    @missing_feature(weblog_variant="spring-boot-openliberty", reason="weblog returns error 500")
    def test_login_wrong_password_failure_basic(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            if context.library not in ("nodejs", "java"):
                # Currently in nodejs/java there is no way to check if the user exists upon authentication failure so
                # this assertion is disabled for this library.
                assert meta["appsec.events.users.login.failure.usr.exists"] == "true"
                assert meta["appsec.events.users.login.failure.usr.id"] == "social-security-id"
                assert meta["appsec.events.users.login.failure.email"] == "testuser@ddog.com"
                assert meta["appsec.events.users.login.failure.username"] == "test"
            else:
                assert meta["appsec.events.users.login.failure.usr.id"] == "test"

            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "extended"
            assert meta["appsec.events.users.login.failure.track"] == "true"

            assert_priority(span, trace)

    def setup_login_sdk_success_local(self):
        self.r_sdk_success = weblog.post(
            "/login?auth=local&sdk_event=success&sdk_user=sdkUser",
            data=login_data(context, USER, PASSWORD),
        )

    def test_login_sdk_success_local(self):
        assert self.r_sdk_success.status_code == 200
        for _, trace, span in interfaces.library.get_spans(request=self.r_sdk_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "extended"
            assert meta["_dd.appsec.events.users.login.success.sdk"] == "true"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == "sdkUser"
            assert_priority(span, trace)

    def setup_login_sdk_success_basic(self):
        self.r_sdk_success = weblog.get(
            "/login?auth=basic&sdk_event=success&sdk_user=sdkUser",
            headers={"Authorization": BASIC_AUTH_USER_HEADER},
        )

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    def test_login_sdk_success_basic(self):
        assert self.r_sdk_success.status_code == 200
        for _, trace, span in interfaces.library.get_spans(request=self.r_sdk_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "extended"
            assert meta["_dd.appsec.events.users.login.success.sdk"] == "true"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == "sdkUser"
            assert_priority(span, trace)

    def setup_login_sdk_failure_basic(self):
        self.r_sdk_failure = weblog.get(
            "/login?auth=basic&sdk_event=failure&sdk_user=sdkUser&sdk_user_exists=true",
            headers={"Authorization": BASIC_AUTH_INVALID_USER_HEADER},
        )

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    @missing_feature(weblog_variant="spring-boot-openliberty", reason="weblog returns error 500")
    def test_login_sdk_failure_basic(self):
        assert self.r_sdk_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_sdk_failure):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "extended"
            assert meta["_dd.appsec.events.users.login.failure.sdk"] == "true"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert meta["appsec.events.users.login.failure.usr.id"] == "sdkUser"
            assert meta["appsec.events.users.login.failure.usr.exists"] == "true"
            assert_priority(span, trace)

    def setup_login_sdk_failure_local(self):
        self.r_sdk_failure = weblog.post(
            "/login?auth=local&sdk_event=failure&sdk_user=sdkUser&sdk_user_exists=true",
            data=login_data(context, INVALID_USER, PASSWORD),
        )

    @missing_feature(weblog_variant="spring-boot-openliberty", reason="weblog returns error 500")
    def test_login_sdk_failure_local(self):
        assert self.r_sdk_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_sdk_failure):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "extended"
            assert meta["_dd.appsec.events.users.login.failure.sdk"] == "true"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert meta["appsec.events.users.login.failure.usr.id"] == "sdkUser"
            assert meta["appsec.events.users.login.failure.usr.exists"] == "true"
            assert_priority(span, trace)

    def setup_login_success_headers(self):
        self.r_hdr_success = weblog.post(
            "/login?auth=local",
            data=login_data(context, USER, PASSWORD),
            headers=HEADERS,
        )

    @missing_feature(context.library < "dotnet@3.7.0")
    @missing_feature(context.library < "nodejs@5.18.0")
    @missing_feature(library="php")
    @missing_feature(library="ruby")
    def test_login_success_headers(self):
        # Validate that all relevant headers are included on user login success on extended mode

        def validate_login_success_headers(span):
            if span.get("parent_id") not in (0, None):
                return None

            for header in HEADERS:
                assert f"http.request.headers.{header.lower()}" in span["meta"], f"Can't find {header} in span's meta"
            return True

        interfaces.library.validate_spans(self.r_hdr_success, validator=validate_login_success_headers)

    def setup_login_failure_headers(self):
        self.r_hdr_failure = weblog.post(
            "/login?auth=local",
            data=login_data(context, INVALID_USER, PASSWORD),
            headers=HEADERS,
        )

    @missing_feature(context.library < "dotnet@3.7.0")
    @missing_feature(context.library < "nodejs@5.18.0")
    @missing_feature(library="php")
    @missing_feature(library="ruby")
    def test_login_failure_headers(self):
        # Validate that all relevant headers are included on user login failure on extended mode

        def validate_login_failure_headers(span):
            if span.get("parent_id") not in (0, None):
                return None

            for header in HEADERS:
                assert f"http.request.headers.{header.lower()}" in span["meta"], f"Can't find {header} in span's meta"
            return True

        interfaces.library.validate_spans(self.r_hdr_failure, validator=validate_login_failure_headers)


@rfc("https://docs.google.com/document/d/19VHLdJLVFwRb_JrE87fmlIM5CL5LdOBv4AmLxgdo9qI/edit")
@features.user_monitoring
@features.user_id_collection_modes
class Test_V2_Login_Events:
    """Test login success/failure use cases
    By default, mode is identification
    """

    # User entries in the internal DB:
    # users = [
    #     {
    #         id: 'social-security-id',
    #         username: 'test',
    #         password: '1234',
    #         email: 'testuser@ddog.com'
    #     },
    #     {
    #         id: '591dc126-8431-4d0f-9509-b23318d3dce4',
    #         username: 'testuuid',
    #         password: '1234',
    #         email: 'testuseruuid@ddog.com'
    #     }
    # ]

    def setup_login_pii_success_local(self):
        self.r_pii_success = weblog.post("/login?auth=local", data=login_data(context, USER, PASSWORD))

    def test_login_pii_success_local(self):
        assert self.r_pii_success.status_code == 200
        for _, trace, span in interfaces.library.get_spans(request=self.r_pii_success):
            meta = span.get("meta", {})
            assert "usr.id" in meta
            assert meta["usr.id"] == "social-security-id"
            # deprecated tags
            assert "appsec.events.users.login.success.email" not in meta
            assert "appsec.events.users.login.success.username" not in meta
            assert "appsec.events.users.login.success.login" not in meta
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "identification"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert_priority(span, trace)

    def setup_login_pii_success_basic(self):
        self.r_pii_success = weblog.get("/login?auth=basic", headers={"Authorization": BASIC_AUTH_USER_HEADER})

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    def test_login_pii_success_basic(self):
        assert self.r_pii_success.status_code == 200
        for _, trace, span in interfaces.library.get_spans(request=self.r_pii_success):
            meta = span.get("meta", {})
            assert "usr.id" in meta
            assert meta["usr.id"] == "social-security-id"
            # deprecated tags
            assert "appsec.events.users.login.success.email" not in meta
            assert "appsec.events.users.login.success.username" not in meta
            assert "appsec.events.users.login.success.login" not in meta
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "identification"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert_priority(span, trace)

    def setup_login_success_local(self):
        self.r_success = weblog.post("/login?auth=local", data=login_data(context, UUID_USER, PASSWORD))

    def test_login_success_local(self):
        assert self.r_success.status_code == 200
        for _, trace, span in interfaces.library.get_spans(request=self.r_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "identification"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == "591dc126-8431-4d0f-9509-b23318d3dce4"
            # deprecated tags
            assert "appsec.events.users.login.success.email" not in meta
            assert "appsec.events.users.login.success.username" not in meta
            assert "appsec.events.users.login.success.login" not in meta
            assert_priority(span, trace)

    def setup_login_success_basic(self):
        self.r_success = weblog.get("/login?auth=basic", headers={"Authorization": BASIC_AUTH_USER_UUID_HEADER})

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    def test_login_success_basic(self):
        assert self.r_success.status_code == 200
        for _, trace, span in interfaces.library.get_spans(request=self.r_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "identification"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == "591dc126-8431-4d0f-9509-b23318d3dce4"
            # deprecated tags
            assert "appsec.events.users.login.success.email" not in meta
            assert "appsec.events.users.login.success.username" not in meta
            assert "appsec.events.users.login.success.login" not in meta
            assert_priority(span, trace)

    def setup_login_wrong_user_failure_local(self):
        self.r_wrong_user_failure = weblog.post("/login?auth=local", data=login_data(context, INVALID_USER, PASSWORD))

    @irrelevant(
        context.library >= "dotnet@3.7.0", reason="Released v3 with logins from 3.7, now it's ...failure.usr.login"
    )
    def test_login_wrong_user_failure_local(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            if context.library not in ("nodejs", "java"):
                # Currently in nodejs/java there is no way to check if the user exists upon authentication failure so
                # this assertion is disabled for this library.
                assert meta["appsec.events.users.login.failure.usr.exists"] == "false"

            assert meta["appsec.events.users.login.failure.usr.id"] == INVALID_USER
            assert "appsec.events.users.login.failure.usr.email" not in meta
            assert "appsec.events.users.login.failure.usr.login" not in meta
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "identification"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert_priority(span, trace)

    def setup_login_wrong_user_failure_basic(self):
        self.r_wrong_user_failure = weblog.get(
            "/login?auth=basic", headers={"Authorization": BASIC_AUTH_INVALID_USER_HEADER}
        )

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    @irrelevant(
        context.library >= "dotnet@3.7.0", reason="Released v3 with logins from 3.7, now it's ...failure.usr.login"
    )
    def test_login_wrong_user_failure_basic(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            if context.library not in ("nodejs", "java"):
                # Currently in nodejs/java there is no way to check if the user exists upon authentication failure so
                # this assertion is disabled for this library.
                assert meta["appsec.events.users.login.failure.usr.exists"] == "false"

            assert meta["appsec.events.users.login.failure.usr.id"] == INVALID_USER
            assert "appsec.events.users.login.failure.usr.email" not in meta
            assert "appsec.events.users.login.failure.usr.login" not in meta
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "identification"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert_priority(span, trace)

    def setup_login_wrong_password_failure_local(self):
        self.r_wrong_user_failure = weblog.post("/login?auth=local", data=login_data(context, USER, "12345"))

    @irrelevant(
        context.library >= "dotnet@3.7.0", reason="Released v3 with logins from 3.7, now exists ...failure.usr.login"
    )
    def test_login_wrong_password_failure_local(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            if context.library not in ("nodejs", "java"):
                # Currently in nodejs/java there is no way to check if the user exists upon authentication failure so
                # this assertion is disabled for this library.
                assert meta["appsec.events.users.login.failure.usr.exists"] == "true"

            assert "appsec.events.users.login.failure.usr.id" in meta
            if context.library == "java":
                # in case of failure java only has access to the original username sent in the request
                assert meta["appsec.events.users.login.failure.usr.id"] == "test"
            else:
                assert meta["appsec.events.users.login.failure.usr.id"] == "social-security-id"
            # deprecated
            assert "appsec.events.users.login.failure.usr.email" not in meta
            assert "appsec.events.users.login.failure.usr.login" not in meta
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "identification"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert_priority(span, trace)

    def setup_login_wrong_password_failure_basic(self):
        self.r_wrong_user_failure = weblog.get(
            "/login?auth=basic", headers={"Authorization": BASIC_AUTH_INVALID_PASSWORD_HEADER}
        )

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    @irrelevant(
        context.library >= "dotnet@3.7.0", reason="Released v3 with logins from 3.7, now exists ...failure.usr.login"
    )
    def test_login_wrong_password_failure_basic(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            if context.library not in ("nodejs", "java"):
                # Currently in nodejs/java there is no way to check if the user exists upon authentication failure so
                # this assertion is disabled for this library.
                assert meta["appsec.events.users.login.failure.usr.exists"] == "true"

            assert "appsec.events.users.login.failure.usr.id" in meta
            if context.library == "java":
                # in case of failure java only has access to the original username sent in the request
                assert meta["appsec.events.users.login.failure.usr.id"] == "test"
            else:
                assert meta["appsec.events.users.login.failure.usr.id"] == "social-security-id"
            assert "appsec.events.users.login.failure.usr.email" not in meta
            assert "appsec.events.users.login.failure.usr.login" not in meta
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "identification"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert_priority(span, trace)

    def setup_login_sdk_success_local(self):
        self.r_sdk_success = weblog.post(
            "/login?auth=local&sdk_event=success&sdk_user=sdkUser",
            data=login_data(context, USER, PASSWORD),
        )

    def test_login_sdk_success_local(self):
        assert self.r_sdk_success.status_code == 200
        for _, trace, span in interfaces.library.get_spans(request=self.r_sdk_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "identification"
            assert meta["_dd.appsec.events.users.login.success.sdk"] == "true"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == "sdkUser"
            assert_priority(span, trace)

    def setup_login_sdk_success_basic(self):
        self.r_sdk_success = weblog.get(
            "/login?auth=basic&sdk_event=success&sdk_user=sdkUser",
            headers={"Authorization": BASIC_AUTH_USER_HEADER},
        )

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    def test_login_sdk_success_basic(self):
        assert self.r_sdk_success.status_code == 200
        for _, trace, span in interfaces.library.get_spans(request=self.r_sdk_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "identification"
            assert meta["_dd.appsec.events.users.login.success.sdk"] == "true"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == "sdkUser"
            assert_priority(span, trace)

    def setup_login_sdk_failure_local(self):
        self.r_sdk_failure = weblog.post(
            "/login?auth=local&sdk_event=failure&sdk_user=sdkUser&sdk_user_exists=true",
            data=login_data(context, INVALID_USER, PASSWORD),
        )

    def test_login_sdk_failure_local(self):
        assert self.r_sdk_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_sdk_failure):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "identification"
            assert meta["_dd.appsec.events.users.login.failure.sdk"] == "true"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert meta["appsec.events.users.login.failure.usr.id"] == "sdkUser"
            assert meta["appsec.events.users.login.failure.usr.exists"] == "true"
            assert_priority(span, trace)

    def setup_login_sdk_failure_basic(self):
        self.r_sdk_failure = weblog.get(
            "/login?auth=basic&sdk_event=failure&sdk_user=sdkUser&sdk_user_exists=true",
            headers={"Authorization": BASIC_AUTH_INVALID_USER_HEADER},
        )

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    def test_login_sdk_failure_basic(self):
        assert self.r_sdk_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_sdk_failure):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "identification"
            assert meta["_dd.appsec.events.users.login.failure.sdk"] == "true"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert meta["appsec.events.users.login.failure.usr.id"] == "sdkUser"
            assert meta["appsec.events.users.login.failure.usr.exists"] == "true"
            assert_priority(span, trace)


@rfc("https://docs.google.com/document/d/19VHLdJLVFwRb_JrE87fmlIM5CL5LdOBv4AmLxgdo9qI/edit")
@scenarios.appsec_auto_events_extended
@features.user_monitoring
@features.user_id_collection_modes
class Test_V2_Login_Events_Anon:
    """Test login success/failure use cases
    As default mode is identification, this scenario will test anonymization.
    """

    def setup_login_success_local(self):
        self.r_success = weblog.post("/login?auth=local", data=login_data(context, USER, PASSWORD))

    def test_login_success_local(self):
        assert self.r_success.status_code == 200
        for _, trace, span in interfaces.library.get_spans(request=self.r_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "anonymization"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == USER_HASH

            # deprecated
            # "appsec.events.users.login.success.username" not in meta
            # "appsec.events.users.login.success.email" not in meta
            # "usr.email" not in meta
            # "usr.username" not in meta
            # "usr.login" not in meta

            assert_priority(span, trace)

    def setup_login_success_basic(self):
        self.r_success = weblog.get("/login?auth=basic", headers={"Authorization": BASIC_AUTH_USER_HEADER})

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    def test_login_success_basic(self):
        assert self.r_success.status_code == 200
        for _, trace, span in interfaces.library.get_spans(request=self.r_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "anonymization"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == USER_HASH

            # deprecated
            # "appsec.events.users.login.success.username" not in meta
            # "appsec.events.users.login.success.email" not in meta
            # "usr.email" not in meta
            # "usr.username" not in meta
            # "usr.login" not in meta

            assert_priority(span, trace)

    def setup_login_wrong_user_failure_local(self):
        self.r_wrong_user_failure = weblog.post("/login?auth=local", data=login_data(context, INVALID_USER, PASSWORD))

    @irrelevant(
        context.library >= "dotnet@3.7.0",
        reason="Released v3 with logins from 3.7, now login reported when user exists is false",
    )
    def test_login_wrong_user_failure_local(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            assert meta["appsec.events.users.login.failure.usr.exists"] == "false"

            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "anonymization"
            assert meta["appsec.events.users.login.failure.track"] == "true"

            assert meta["appsec.events.users.login.failure.usr.id"] == INVALID_USER_HASH
            assert "appsec.events.users.login.failure.email" not in meta
            assert "appsec.events.users.login.failure.username" not in meta

            assert_priority(span, trace)

    def setup_login_wrong_user_failure_basic(self):
        self.r_wrong_user_failure = weblog.get(
            "/login?auth=basic", headers={"Authorization": BASIC_AUTH_INVALID_USER_HEADER}
        )

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    @irrelevant(
        context.library >= "dotnet@3.7.0",
        reason="Released v3 with logins from 3.7, now login reported when user exists is false",
    )
    def test_login_wrong_user_failure_basic(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            assert meta["appsec.events.users.login.failure.usr.exists"] == "false"

            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "anonymization"
            assert meta["appsec.events.users.login.failure.track"] == "true"

            assert meta["appsec.events.users.login.failure.usr.id"] == INVALID_USER_HASH
            assert "appsec.events.users.login.failure.email" not in meta
            assert "appsec.events.users.login.failure.username" not in meta

            assert_priority(span, trace)

    def setup_login_wrong_password_failure_local(self):
        self.r_wrong_user_failure = weblog.post("/login?auth=local", data=login_data(context, USER, "12345"))

    def test_login_wrong_password_failure_local(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            if context.library != "java":
                # Currently in java there is no way to check if the user exists upon authentication failure so
                # this assertion is disabled for this library.
                assert meta["appsec.events.users.login.failure.usr.exists"] == "true"

            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "anonymization"
            assert meta["appsec.events.users.login.failure.track"] == "true"

            if context.library == "java":
                # in case of failure java only has access to the original username sent in the request
                assert meta["appsec.events.users.login.failure.usr.id"] == USERNAME_HASH
            else:
                assert meta["appsec.events.users.login.failure.usr.id"] == USER_HASH
            assert "appsec.events.users.login.failure.email" not in meta
            assert "appsec.events.users.login.failure.username" not in meta

            assert_priority(span, trace)

    def setup_login_wrong_password_failure_basic(self):
        self.r_wrong_user_failure = weblog.get(
            "/login?auth=basic", headers={"Authorization": BASIC_AUTH_INVALID_PASSWORD_HEADER}
        )

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    def test_login_wrong_password_failure_basic(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            if context.library != "java":
                # Currently in java there is no way to check if the user exists upon authentication failure so
                # this assertion is disabled for this library.
                assert meta["appsec.events.users.login.failure.usr.exists"] == "true"

            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "anonymization"
            assert meta["appsec.events.users.login.failure.track"] == "true"

            if context.library == "java":
                # in case of failure java only has access to the original username sent in the request
                assert meta["appsec.events.users.login.failure.usr.id"] == USERNAME_HASH
            else:
                assert meta["appsec.events.users.login.failure.usr.id"] == USER_HASH
            assert "appsec.events.users.login.failure.email" not in meta
            assert "appsec.events.users.login.failure.username" not in meta

            assert_priority(span, trace)

    def setup_login_sdk_success_local(self):
        self.r_sdk_success = weblog.post(
            "/login?auth=local&sdk_event=success&sdk_user=sdkUser",
            data=login_data(context, USER, PASSWORD),
        )

    def test_login_sdk_success_local(self):
        assert self.r_sdk_success.status_code == 200
        for _, trace, span in interfaces.library.get_spans(request=self.r_sdk_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "anonymization"
            assert meta["_dd.appsec.events.users.login.success.sdk"] == "true"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == "sdkUser"
            assert_priority(span, trace)

    def setup_login_sdk_success_basic(self):
        self.r_sdk_success = weblog.get(
            "/login?auth=basic&sdk_event=success&sdk_user=sdkUser",
            headers={"Authorization": BASIC_AUTH_USER_HEADER},
        )

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    def test_login_sdk_success_basic(self):
        assert self.r_sdk_success.status_code == 200
        for _, trace, span in interfaces.library.get_spans(request=self.r_sdk_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "anonymization"
            assert meta["_dd.appsec.events.users.login.success.sdk"] == "true"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == "sdkUser"
            assert_priority(span, trace)

    def setup_login_sdk_failure_basic(self):
        self.r_sdk_failure = weblog.get(
            "/login?auth=basic&sdk_event=failure&sdk_user=sdkUser&sdk_user_exists=true",
            headers={"Authorization": BASIC_AUTH_INVALID_USER_HEADER},
        )

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    def test_login_sdk_failure_basic(self):
        assert self.r_sdk_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_sdk_failure):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "anonymization"
            assert meta["_dd.appsec.events.users.login.failure.sdk"] == "true"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert meta["appsec.events.users.login.failure.usr.id"] == "sdkUser"
            assert meta["appsec.events.users.login.failure.usr.exists"] == "true"
            assert_priority(span, trace)

    def setup_login_sdk_failure_local(self):
        self.r_sdk_failure = weblog.post(
            "/login?auth=local&sdk_event=failure&sdk_user=sdkUser&sdk_user_exists=true",
            data=login_data(context, INVALID_USER, PASSWORD),
        )

    def test_login_sdk_failure_local(self):
        assert self.r_sdk_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_sdk_failure):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "anonymization"
            assert meta["_dd.appsec.events.users.login.failure.sdk"] == "true"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert meta["appsec.events.users.login.failure.usr.id"] == "sdkUser"
            assert meta["appsec.events.users.login.failure.usr.exists"] == "true"
            assert_priority(span, trace)

    def setup_login_success_headers(self):
        self.r_hdr_success = weblog.post(
            "/login?auth=local",
            data=login_data(context, USER, PASSWORD),
            headers=HEADERS,
        )

    @missing_feature(context.library < "dotnet@3.7.0")
    def test_login_success_headers(self):
        # Validate that all relevant headers are included on user login success on extended mode

        def validate_login_success_headers(span):
            if span.get("parent_id") not in (0, None):
                return None

            for header in HEADERS:
                assert f"http.request.headers.{header.lower()}" in span["meta"], f"Can't find {header} in span's meta"
            return True

        interfaces.library.validate_spans(self.r_hdr_success, validator=validate_login_success_headers)

    def setup_login_failure_headers(self):
        self.r_hdr_failure = weblog.post(
            "/login?auth=local",
            data=login_data(context, INVALID_USER, PASSWORD),
            headers=HEADERS,
        )

    @missing_feature(context.library < "dotnet@3.7.0")
    def test_login_failure_headers(self):
        # Validate that all relevant headers are included on user login failure on extended mode

        def validate_login_failure_headers(span):
            if span.get("parent_id") not in (0, None):
                return None

            for header in HEADERS:
                assert f"http.request.headers.{header.lower()}" in span["meta"], f"Can't find {header} in span's meta"
            return True

        interfaces.library.validate_spans(self.r_hdr_failure, validator=validate_login_failure_headers)


def assert_priority(span, trace):
    if "_sampling_priority_v1" not in span["metrics"]:
        # some tracers like java only send the priority in the first and last span of the trace
        assert trace[0]["metrics"].get("_sampling_priority_v1") == SamplingPriority.USER_KEEP
    else:
        assert span["metrics"].get("_sampling_priority_v1") == SamplingPriority.USER_KEEP


@rfc("https://docs.google.com/document/d/19VHLdJLVFwRb_JrE87fmlIM5CL5LdOBv4AmLxgdo9qI/edit")
@features.user_monitoring
@scenarios.appsec_auto_events_rc
class Test_V2_Login_Events_RC:
    # ["disabled", "identification", "anonymization"]
    PAYLOADS = [
        {
            "targets": "eyJzaWduZWQiOnsiX3R5cGUiOiJ0YXJnZXRzIiwiY3VzdG9tIjp7Im9wYXF1ZV9iYWNrZW5kX3N0YXRlIjoiZXlKbWIyOGl"
            "PaUFpWW1GeUluMD0ifSwiZXhwaXJlcyI6IjMwMDAtMDEtMDFUMDA6MDA6MDBaIiwic3BlY192ZXJzaW9uIjoiMS4wIiwidGFyZ2V0cyI6e"
            "yJkYXRhZG9nLzIvQVNNX0ZFQVRVUkVTL2F1dG8tdXNlci1pbnN0cnVtL2NvbmZpZyI6eyJjdXN0b20iOnsidiI6MX0sImhhc2hlcyI6eyJ"
            "zaGEyNTYiOiJlZDRiNmZmNWRkMmQ3MWI5NjE0YjcxMzMwMTg4MjU2MmNmNGQ4ODk3YWRlMzIzYTZkMmQ5ZGViZDRhNzNhZDA0In0sImxlb"
            "md0aCI6NTZ9fSwidmVyc2lvbiI6MX0sInNpZ25hdHVyZXMiOlt7ImtleWlkIjoiZWQ3NjcyYzlhMjRhYmRhNzg4NzJlZTMyZWU3MWM3Y2I"
            "xZDUyMzVlOGRiNGVjYmYxY2EyOGI5YzUwZWI3NWQ5ZSIsInNpZyI6IjIyZDhlOTE0ZWM1NmE0MmQ4MTE4MmE4Y2RkODQyMTI0OTIyMDhlZ"
            "DllNjRjZjQ2Mjg1ZTIxY2NjMjdhY2NhZDRlZDc3N2Y5MDkwNGVlYmZiODhiNDQ2ZGUxMGNkMjk1YzNjZDJlNjM1NmY4MjMzNDk5MzM1OTQ"
            "4YTRkMDI1ZTBkIn1dfQ==",
            "target_files": [
                {
                    "path": "datadog/2/ASM_FEATURES/auto-user-instrum/config",
                    "raw": "ewogICJhdXRvX3VzZXJfaW5zdHJ1bSI6IHsKICAgICJtb2RlIjogImRpc2FibGVkIgogIH0KfQo=",
                }
            ],
            "client_configs": ["datadog/2/ASM_FEATURES/auto-user-instrum/config"],
        },
        {
            "targets": "eyJzaWduZWQiOnsiX3R5cGUiOiJ0YXJnZXRzIiwiY3VzdG9tIjp7Im9wYXF1ZV9iYWNrZW5kX3N0YXRlIjoiZXlKbWIyOGl"
            "PaUFpWW1GeUluMD0ifSwiZXhwaXJlcyI6IjMwMDAtMDEtMDFUMDA6MDA6MDBaIiwic3BlY192ZXJzaW9uIjoiMS4wIiwidGFyZ2V0cyI6e"
            "yJkYXRhZG9nLzIvQVNNX0ZFQVRVUkVTL2F1dG8tdXNlci1pbnN0cnVtL2NvbmZpZyI6eyJjdXN0b20iOnsidiI6Mn0sImhhc2hlcyI6eyJ"
            "zaGEyNTYiOiIyZWY2ZDVjMGZhNTQ4NTY0YTRjNWI3NTBjZmRkMDhkOWE4ODk2MmNhZTZkY2M5NDk0MjM4OWMxZDkwOTNkMTBhIn0sImxlb"
            "md0aCI6NjJ9fSwidmVyc2lvbiI6Mn0sInNpZ25hdHVyZXMiOlt7ImtleWlkIjoiZWQ3NjcyYzlhMjRhYmRhNzg4NzJlZTMyZWU3MWM3Y2I"
            "xZDUyMzVlOGRiNGVjYmYxY2EyOGI5YzUwZWI3NWQ5ZSIsInNpZyI6ImYzOTMxZDliODk4NWIzNTgxNjc1NWI4N2RjNmFmM2UxYzMzYWJmM"
            "jhjZDhkYzVmYWM2ZmMwMzgyZjNlMjUwOGU4ZmZmNzMxMDI2NWFhNDk3NjU2NjAyZDIxMTlhODFhNTViMjkwM2VkMjJlM2IzMzU0MmNhMWZ"
            "iYmUxYWRhMjBhIn1dfQ==",
            "target_files": [
                {
                    "path": "datadog/2/ASM_FEATURES/auto-user-instrum/config",
                    "raw": "ewogICJhdXRvX3VzZXJfaW5zdHJ1bSI6IHsKICAgICJtb2RlIjogImlkZW50aWZpY2F0aW9uIgogIH0KfQo=",
                }
            ],
            "client_configs": ["datadog/2/ASM_FEATURES/auto-user-instrum/config"],
        },
        {
            "targets": "eyJzaWduZWQiOnsiX3R5cGUiOiJ0YXJnZXRzIiwiY3VzdG9tIjp7Im9wYXF1ZV9iYWNrZW5kX3N0YXRlIjoiZXlKbWIyOGl"
            "PaUFpWW1GeUluMD0ifSwiZXhwaXJlcyI6IjMwMDAtMDEtMDFUMDA6MDA6MDBaIiwic3BlY192ZXJzaW9uIjoiMS4wIiwidGFyZ2V0cyI6e"
            "yJkYXRhZG9nLzIvQVNNX0ZFQVRVUkVTL2F1dG8tdXNlci1pbnN0cnVtL2NvbmZpZyI6eyJjdXN0b20iOnsidiI6M30sImhhc2hlcyI6eyJ"
            "zaGEyNTYiOiIwMjRiOGM4MmQxODBkZjc2NzMzNzVjYzYzZDdiYmRjMzRiNWE4YzE3NWQzNzE3ZGQwYjYyMzg2OTRhY2FiNWI3In0sImxlb"
            "md0aCI6NjF9fSwidmVyc2lvbiI6M30sInNpZ25hdHVyZXMiOlt7ImtleWlkIjoiZWQ3NjcyYzlhMjRhYmRhNzg4NzJlZTMyZWU3MWM3Y2I"
            "xZDUyMzVlOGRiNGVjYmYxY2EyOGI5YzUwZWI3NWQ5ZSIsInNpZyI6IjZlN2FkNDY1MDBiOGU0MTlkZDEyOTQyMjRiMGMzODM0OTZkZjc5O"
            "TJhOTliNDkwYWY0MmU1YjRkOTdjZWYxNTI3ZmRjNTAxMGVmYmI2NmYyY2VjMjgyY2Y4NzU5YmFlZThmOWY0ZjA4OWJjODJjNDk3NDUzYjc"
            "3YmM4Y2RiYTBkIn1dfQ==",
            "target_files": [
                {
                    "path": "datadog/2/ASM_FEATURES/auto-user-instrum/config",
                    "raw": "ewogICJhdXRvX3VzZXJfaW5zdHJ1bSI6IHsKICAgICJtb2RlIjogImFub255bWl6YXRpb24iCiAgfQp9Cg==",
                }
            ],
            "client_configs": ["datadog/2/ASM_FEATURES/auto-user-instrum/config"],
        },
    ]

    def _send_rc_and_execute_request(self, rc_payload):
        config_states = rc.send_state(raw_payload=rc_payload)
        request = weblog.post("/login?auth=local", data=login_data(context, USER, PASSWORD))
        return {"config_states": config_states, "request": request}

    def _assert_response(self, test, validation):
        config_states, request = test["config_states"], test["request"]

        assert config_states.state == rc.ApplyState.ACKNOWLEDGED
        assert request.status_code == 200

        spans = [s for _, _, s in interfaces.library.get_spans(request=request)]
        assert spans, "No spans to validate"
        for span in spans:
            meta = span.get("meta", {})
            validation(meta)

    def setup_rc(self):
        self.tests = [self._send_rc_and_execute_request(rc) for rc in self.PAYLOADS]

    def test_rc(self):
        def validate_disabled(meta):
            assert "_dd.appsec.events.users.login.success.auto.mode" not in meta

        def validate_anon(meta):
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "anonymization"

        def validate_iden(meta):
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "identification"

        self._assert_response(self.tests[0], validate_disabled)
        self._assert_response(self.tests[1], validate_iden)
        self._assert_response(self.tests[2], validate_anon)


libs_without_user_id = ["java"]
libs_without_user_exist = ["nodejs", "java"]
libs_without_user_id_on_failure = ["nodejs", "java"]


@rfc("https://docs.google.com/document/d/1RT38U6dTTcB-8muiYV4-aVDCsT_XrliyakjtAPyjUpw")
@features.user_monitoring
@features.user_id_collection_modes
class Test_V3_Login_Events:
    """Test login success/failure use cases
    By default, mode is identification
    """

    # User entries in the internal DB:
    # users = [
    #     {
    #         id: 'social-security-id',
    #         username: 'test',
    #         password: '1234',
    #         email: 'testuser@ddog.com'
    #     },
    #     {
    #         id: '591dc126-8431-4d0f-9509-b23318d3dce4',
    #         username: 'testuuid',
    #         password: '1234',
    #         email: 'testuseruuid@ddog.com'
    #     }
    # ]
    #
    # These users can be created with signup events:
    # users = [
    #     {
    #         id: 'new-user',
    #         username: 'testnew',
    #         password: '1234',
    #         email: 'testnewuser@ddog.com'
    #     }
    # ]

    def setup_login_success_local(self):
        self.r_success = weblog.post("/login?auth=local", data=login_data(context, USER, PASSWORD))

    def test_login_success_local(self):
        assert self.r_success.status_code == 200
        for _, trace, span in interfaces.library.get_spans(request=self.r_success):
            assert_priority(span, trace)
            meta = span.get("meta", {})

            # mandatory
            assert meta["appsec.events.users.login.success.usr.login"] == USER
            assert meta["_dd.appsec.usr.login"] == USER
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "identification"
            assert meta["appsec.events.users.login.success.track"] == "true"

            # optional (to review for each library)
            if context.library not in libs_without_user_id:
                assert meta["usr.id"] == "social-security-id"
                assert meta["_dd.appsec.usr.id"] == "social-security-id"

    def setup_login_success_basic(self):
        self.r_success = weblog.get("/login?auth=basic", headers={"Authorization": BASIC_AUTH_USER_HEADER})

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    def test_login_success_basic(self):
        assert self.r_success.status_code == 200
        for _, trace, span in interfaces.library.get_spans(request=self.r_success):
            assert_priority(span, trace)
            meta = span.get("meta", {})

            # mandatory
            assert meta["appsec.events.users.login.success.usr.login"] == USER
            assert meta["_dd.appsec.usr.login"] == USER
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "identification"
            assert meta["appsec.events.users.login.success.track"] == "true"

            # optional (to review for each library)
            if context.library not in libs_without_user_id:
                assert meta["usr.id"] == "social-security-id"
                assert meta["_dd.appsec.usr.id"] == "social-security-id"

    def setup_login_wrong_user_failure_local(self):
        self.r_wrong_user_failure = weblog.post("/login?auth=local", data=login_data(context, INVALID_USER, PASSWORD))

    def test_login_wrong_user_failure_local(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            assert_priority(span, trace)
            meta = span.get("meta", {})

            # mandatory
            assert meta["appsec.events.users.login.failure.usr.login"] == INVALID_USER
            assert meta["_dd.appsec.usr.login"] == INVALID_USER
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "identification"
            assert meta["appsec.events.users.login.failure.track"] == "true"

            # optional (to review for each library)
            if context.library not in libs_without_user_exist:
                assert meta["appsec.events.users.login.failure.usr.exists"] == "false"

    def setup_login_wrong_user_failure_basic(self):
        self.r_wrong_user_failure = weblog.get(
            "/login?auth=basic", headers={"Authorization": BASIC_AUTH_INVALID_USER_HEADER}
        )

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    def test_login_wrong_user_failure_basic(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            assert_priority(span, trace)
            meta = span.get("meta", {})

            # mandatory
            assert meta["appsec.events.users.login.failure.usr.login"] == INVALID_USER
            assert meta["_dd.appsec.usr.login"] == INVALID_USER
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "identification"
            assert meta["appsec.events.users.login.failure.track"] == "true"

            # optional (to review for each library)
            if context.library not in libs_without_user_exist:
                assert meta["appsec.events.users.login.failure.usr.exists"] == "false"

    def setup_login_wrong_password_failure_local(self):
        self.r_wrong_user_failure = weblog.post("/login?auth=local", data=login_data(context, USER, "12345"))

    def test_login_wrong_password_failure_local(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            assert_priority(span, trace)
            meta = span.get("meta", {})

            # mandatory
            assert meta["appsec.events.users.login.failure.usr.login"] == USER
            assert meta["_dd.appsec.usr.login"] == USER
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "identification"
            assert meta["appsec.events.users.login.failure.track"] == "true"

            # optional (to review for each library)
            if context.library not in libs_without_user_exist:
                assert meta["appsec.events.users.login.failure.usr.exists"] == "true"

            if context.library not in libs_without_user_id_on_failure:
                assert meta["appsec.events.users.login.failure.usr.id"] == "social-security-id"
                assert meta["_dd.appsec.usr.id"] == "social-security-id"

    def setup_login_wrong_password_failure_basic(self):
        self.r_wrong_user_failure = weblog.get(
            "/login?auth=basic", headers={"Authorization": BASIC_AUTH_INVALID_PASSWORD_HEADER}
        )

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    def test_login_wrong_password_failure_basic(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            assert_priority(span, trace)
            meta = span.get("meta", {})

            # mandatory
            assert meta["appsec.events.users.login.failure.usr.login"] == USER
            assert meta["_dd.appsec.usr.login"] == USER
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "identification"
            assert meta["appsec.events.users.login.failure.track"] == "true"

            # optional (to review for each library)
            if context.library not in libs_without_user_exist:
                assert meta["appsec.events.users.login.failure.usr.exists"] == "true"

            if context.library not in libs_without_user_id_on_failure:
                assert meta["appsec.events.users.login.failure.usr.id"] == "social-security-id"
                assert meta["_dd.appsec.usr.id"] == "social-security-id"

    def setup_login_sdk_success_local(self):
        self.r_sdk_success = [
            weblog.post(
                f"/login?auth=local&sdk_trigger={trigger}&sdk_event=success&sdk_user=sdkUser",
                data=login_data(context, USER, PASSWORD),
            )
            for trigger in SDK_TRIGGERS
        ]

    def test_login_sdk_success_local(self):
        for request in self.r_sdk_success:
            assert request.status_code == 200
            for _, trace, span in interfaces.library.get_spans(request=request):
                assert_priority(span, trace)
                meta = span.get("meta", {})

                # mandatory
                assert meta["appsec.events.users.login.success.usr.login"] == "sdkUser"
                assert meta["_dd.appsec.usr.login"] == USER
                assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "identification"
                assert meta["appsec.events.users.login.success.track"] == "true"
                assert meta["_dd.appsec.events.users.login.success.sdk"] == "true"

                # optional (to review for each library)
                if context.library not in libs_without_user_id:
                    assert meta["usr.id"] == "sdkUser"
                    assert meta["_dd.appsec.usr.id"] == "social-security-id"

    def setup_login_sdk_success_basic(self):
        self.r_sdk_success = [
            weblog.get(
                f"/login?auth=basic&sdk_trigger={trigger}&sdk_event=success&sdk_user=sdkUser",
                headers={"Authorization": BASIC_AUTH_USER_HEADER},
            )
            for trigger in SDK_TRIGGERS
        ]

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    def test_login_sdk_success_basic(self):
        for request in self.r_sdk_success:
            assert request.status_code == 200
            for _, trace, span in interfaces.library.get_spans(request=request):
                assert_priority(span, trace)
                meta = span.get("meta", {})

                # mandatory
                assert meta["appsec.events.users.login.success.usr.login"] == "sdkUser"
                assert meta["_dd.appsec.usr.login"] == USER
                assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "identification"
                assert meta["appsec.events.users.login.success.track"] == "true"
                assert meta["_dd.appsec.events.users.login.success.sdk"] == "true"

                # optional (to review for each library)
                if context.library not in libs_without_user_id:
                    assert meta["usr.id"] == "sdkUser"
                    assert meta["_dd.appsec.usr.id"] == "social-security-id"

    def setup_login_sdk_failure_local(self):
        self.r_sdk_failure = [
            weblog.post(
                f"/login?auth=local&sdk_trigger={trigger}&sdk_event=failure&sdk_user=sdkUser&sdk_user_exists=true",
                data=login_data(context, INVALID_USER, PASSWORD),
            )
            for trigger in SDK_TRIGGERS
        ]

    @bug(context.library < "java@1.47.0", reason="APPSEC-56744")
    def test_login_sdk_failure_local(self):
        for request in self.r_sdk_failure:
            assert request.status_code == 401
            for _, trace, span in interfaces.library.get_spans(request=request):
                assert_priority(span, trace)
                meta = span.get("meta", {})

                # mandatory
                assert meta["appsec.events.users.login.failure.usr.login"] == "sdkUser"
                assert meta["_dd.appsec.usr.login"] == INVALID_USER
                assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "identification"
                assert meta["appsec.events.users.login.failure.track"] == "true"
                assert meta["_dd.appsec.events.users.login.failure.sdk"] == "true"
                assert meta["appsec.events.users.login.failure.usr.exists"] == "true"

    def setup_login_sdk_failure_basic(self):
        self.r_sdk_failure = [
            weblog.get(
                f"/login?auth=basic&sdk_trigger={trigger}&sdk_event=failure&sdk_user=sdkUser&sdk_user_exists=true",
                headers={"Authorization": BASIC_AUTH_INVALID_USER_HEADER},
            )
            for trigger in SDK_TRIGGERS
        ]

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    @bug(context.library < "java@1.47.0", reason="APPSEC-56744")
    def test_login_sdk_failure_basic(self):
        for request in self.r_sdk_failure:
            assert request.status_code == 401
            for _, trace, span in interfaces.library.get_spans(request=request):
                assert_priority(span, trace)
                meta = span.get("meta", {})

                # mandatory
                assert meta["appsec.events.users.login.failure.usr.login"] == "sdkUser"
                assert meta["_dd.appsec.usr.login"] == INVALID_USER
                assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "identification"
                assert meta["appsec.events.users.login.failure.track"] == "true"
                assert meta["_dd.appsec.events.users.login.failure.sdk"] == "true"
                assert meta["appsec.events.users.login.failure.usr.exists"] == "true"

    def setup_signup_local(self):
        self.r_success = weblog.post("/signup", data=login_data(context, NEW_USER, PASSWORD))

    @missing_feature(context.library == "nodejs", reason="Signup events not implemented")
    @irrelevant(
        context.library == "python" and context.weblog_variant not in ["django-poc", "python3.12", "django-py3.13"],
        reason="No signup in framework",
    )
    @missing_feature(
        context.library < "python@3.2.0.dev"
        and context.weblog_variant in ["django-poc", "python3.12", "django-py3.13"],
        reason="Signup events not implemented yet",
    )
    def test_signup_local(self):
        assert self.r_success.status_code == 200
        for _, trace, span in interfaces.library.get_spans(request=self.r_success):
            assert_priority(span, trace)
            meta = span.get("meta", {})

            # mandatory
            assert meta["appsec.events.users.signup.usr.login"] == NEW_USER
            assert meta["_dd.appsec.usr.login"] == NEW_USER
            assert meta["_dd.appsec.events.users.signup.auto.mode"] == "identification"
            assert meta["appsec.events.users.signup.track"] == "true"

            # optional (to review for each library)
            if context.library not in libs_without_user_id:
                assert meta["appsec.events.users.signup.usr.id"] == "new-user"
                assert meta["_dd.appsec.usr.id"] == "new-user"

    def setup_login_success_headers(self):
        self.r_hdr_success = weblog.post(
            "/login?auth=local",
            data=login_data(context, USER, PASSWORD),
            headers=HEADERS,
        )

    @missing_feature(context.library < "dotnet@3.7.0")
    def test_login_success_headers(self):
        # Validate that all relevant headers are included on user login success on extended mode

        def validate_login_success_headers(span):
            if span.get("parent_id") not in (0, None):
                return None

            for header in HEADERS:
                assert f"http.request.headers.{header.lower()}" in span["meta"], f"Can't find {header} in span's meta"
            return True

        interfaces.library.validate_spans(self.r_hdr_success, validator=validate_login_success_headers)

    def setup_login_failure_headers(self):
        self.r_hdr_failure = weblog.post(
            "/login?auth=local",
            data=login_data(context, INVALID_USER, PASSWORD),
            headers=HEADERS,
        )

    @missing_feature(context.library < "dotnet@3.7.0")
    def test_login_failure_headers(self):
        # Validate that all relevant headers are included on user login failure on extended mode

        def validate_login_failure_headers(span):
            if span.get("parent_id") not in (0, None):
                return None

            for header in HEADERS:
                assert f"http.request.headers.{header.lower()}" in span["meta"], f"Can't find {header} in span's meta"
            return True

        interfaces.library.validate_spans(self.r_hdr_failure, validator=validate_login_failure_headers)


@rfc("https://docs.google.com/document/d/1RT38U6dTTcB-8muiYV4-aVDCsT_XrliyakjtAPyjUpw")
@scenarios.appsec_auto_events_extended
@features.user_monitoring
@features.user_id_collection_modes
class Test_V3_Login_Events_Anon:
    """Test login success/failure use cases
    As default mode is identification, this scenario will test anonymization.
    """

    def setup_login_success_local(self):
        self.r_success = weblog.post("/login?auth=local", data=login_data(context, USER, PASSWORD))

    def test_login_success_local(self):
        assert self.r_success.status_code == 200
        for _, trace, span in interfaces.library.get_spans(request=self.r_success):
            assert_priority(span, trace)
            meta = span.get("meta", {})

            # mandatory
            assert meta["appsec.events.users.login.success.usr.login"] == USERNAME_HASH
            assert meta["_dd.appsec.usr.login"] == USERNAME_HASH
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "anonymization"
            assert meta["appsec.events.users.login.success.track"] == "true"

            # optional (to review for each library)
            if context.library not in libs_without_user_id:
                assert meta["usr.id"] == USER_HASH
                assert meta["_dd.appsec.usr.id"] == USER_HASH

    def setup_login_success_basic(self):
        self.r_success = weblog.get("/login?auth=basic", headers={"Authorization": BASIC_AUTH_USER_HEADER})

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    def test_login_success_basic(self):
        assert self.r_success.status_code == 200
        for _, trace, span in interfaces.library.get_spans(request=self.r_success):
            assert_priority(span, trace)
            meta = span.get("meta", {})

            # mandatory
            assert meta["appsec.events.users.login.success.usr.login"] == USERNAME_HASH
            assert meta["_dd.appsec.usr.login"] == USERNAME_HASH
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "anonymization"
            assert meta["appsec.events.users.login.success.track"] == "true"

            # optional (to review for each library)
            if context.library not in libs_without_user_id:
                assert meta["usr.id"] == USER_HASH
                assert meta["_dd.appsec.usr.id"] == USER_HASH

    def setup_login_wrong_user_failure_local(self):
        self.r_wrong_user_failure = weblog.post("/login?auth=local", data=login_data(context, INVALID_USER, PASSWORD))

    def test_login_wrong_user_failure_local(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            assert_priority(span, trace)
            meta = span.get("meta", {})

            # mandatory
            assert meta["appsec.events.users.login.failure.usr.login"] == INVALID_USER_HASH
            assert meta["_dd.appsec.usr.login"] == INVALID_USER_HASH
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "anonymization"
            assert meta["appsec.events.users.login.failure.track"] == "true"

            # optional (to review for each library)
            if context.library not in libs_without_user_exist:
                assert meta["appsec.events.users.login.failure.usr.exists"] == "false"

    def setup_login_wrong_user_failure_basic(self):
        self.r_wrong_user_failure = weblog.get(
            "/login?auth=basic", headers={"Authorization": BASIC_AUTH_INVALID_USER_HEADER}
        )

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    def test_login_wrong_user_failure_basic(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            assert_priority(span, trace)
            meta = span.get("meta", {})

            # mandatory
            assert meta["appsec.events.users.login.failure.usr.login"] == INVALID_USER_HASH
            assert meta["_dd.appsec.usr.login"] == INVALID_USER_HASH
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "anonymization"
            assert meta["appsec.events.users.login.failure.track"] == "true"

            # optional (to review for each library)
            if context.library not in libs_without_user_exist:
                assert meta["appsec.events.users.login.failure.usr.exists"] == "false"

    def setup_login_wrong_password_failure_local(self):
        self.r_wrong_user_failure = weblog.post("/login?auth=local", data=login_data(context, USER, "12345"))

    def test_login_wrong_password_failure_local(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            assert_priority(span, trace)
            meta = span.get("meta", {})

            # mandatory
            assert meta["appsec.events.users.login.failure.usr.login"] == USERNAME_HASH
            assert meta["_dd.appsec.usr.login"] == USERNAME_HASH
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "anonymization"
            assert meta["appsec.events.users.login.failure.track"] == "true"

            # optional (to review for each library)
            if context.library not in libs_without_user_exist:
                assert meta["appsec.events.users.login.failure.usr.exists"] == "true"

            if context.library not in libs_without_user_id_on_failure:
                assert meta["appsec.events.users.login.failure.usr.id"] == USER_HASH
                assert meta["_dd.appsec.usr.id"] == USER_HASH

    def setup_login_wrong_password_failure_basic(self):
        self.r_wrong_user_failure = weblog.get(
            "/login?auth=basic", headers={"Authorization": BASIC_AUTH_INVALID_PASSWORD_HEADER}
        )

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    def test_login_wrong_password_failure_basic(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, trace, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            assert_priority(span, trace)
            meta = span.get("meta", {})

            # mandatory
            assert meta["appsec.events.users.login.failure.usr.login"] == USERNAME_HASH
            assert meta["_dd.appsec.usr.login"] == USERNAME_HASH
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "anonymization"
            assert meta["appsec.events.users.login.failure.track"] == "true"

            # optional (to review for each library)
            if context.library not in libs_without_user_exist:
                assert meta["appsec.events.users.login.failure.usr.exists"] == "true"

            if context.library not in libs_without_user_id_on_failure:
                assert meta["appsec.events.users.login.failure.usr.id"] == USER_HASH
                assert meta["_dd.appsec.usr.id"] == USER_HASH

    def setup_login_sdk_success_local(self):
        self.r_sdk_success = [
            weblog.post(
                f"/login?auth=local&sdk_trigger={trigger}&sdk_event=success&sdk_user=sdkUser",
                data=login_data(context, USER, PASSWORD),
            )
            for trigger in SDK_TRIGGERS
        ]

    def test_login_sdk_success_local(self):
        for request in self.r_sdk_success:
            assert request.status_code == 200
            for _, trace, span in interfaces.library.get_spans(request=request):
                assert_priority(span, trace)
                meta = span.get("meta", {})

                # mandatory
                assert meta["appsec.events.users.login.success.usr.login"] == "sdkUser"
                assert meta["_dd.appsec.usr.login"] == USERNAME_HASH
                assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "anonymization"
                assert meta["appsec.events.users.login.success.track"] == "true"
                assert meta["_dd.appsec.events.users.login.success.sdk"] == "true"

                # optional (to review for each library)
                if context.library not in libs_without_user_id:
                    assert meta["usr.id"] == "sdkUser"
                    assert meta["_dd.appsec.usr.id"] == USER_HASH

    def setup_login_sdk_success_basic(self):
        self.r_sdk_success = [
            weblog.get(
                f"/login?auth=basic&sdk_trigger={trigger}&sdk_event=success&sdk_user=sdkUser",
                headers={"Authorization": BASIC_AUTH_USER_HEADER},
            )
            for trigger in SDK_TRIGGERS
        ]

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    def test_login_sdk_success_basic(self):
        for request in self.r_sdk_success:
            assert request.status_code == 200
            for _, trace, span in interfaces.library.get_spans(request=request):
                assert_priority(span, trace)
                meta = span.get("meta", {})

                # mandatory
                assert meta["appsec.events.users.login.success.usr.login"] == "sdkUser"
                assert meta["_dd.appsec.usr.login"] == USERNAME_HASH
                assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "anonymization"
                assert meta["appsec.events.users.login.success.track"] == "true"
                assert meta["_dd.appsec.events.users.login.success.sdk"] == "true"

                # optional (to review for each library)
                if context.library not in libs_without_user_id:
                    assert meta["usr.id"] == "sdkUser"
                    assert meta["_dd.appsec.usr.id"] == USER_HASH

    def setup_login_sdk_failure_local(self):
        self.r_sdk_failure = [
            weblog.post(
                f"/login?auth=local&sdk_trigger={trigger}&sdk_event=failure&sdk_user=sdkUser&sdk_user_exists=true",
                data=login_data(context, INVALID_USER, PASSWORD),
            )
            for trigger in SDK_TRIGGERS
        ]

    @bug(context.library < "java@1.47.0", reason="APPSEC-56744")
    def test_login_sdk_failure_local(self):
        for request in self.r_sdk_failure:
            assert request.status_code == 401
            for _, trace, span in interfaces.library.get_spans(request=request):
                assert_priority(span, trace)
                meta = span.get("meta", {})

                # mandatory
                assert meta["appsec.events.users.login.failure.usr.login"] == "sdkUser"
                assert meta["_dd.appsec.usr.login"] == INVALID_USER_HASH
                assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "anonymization"
                assert meta["appsec.events.users.login.failure.track"] == "true"
                assert meta["_dd.appsec.events.users.login.failure.sdk"] == "true"
                assert meta["appsec.events.users.login.failure.usr.exists"] == "true"

    def setup_login_sdk_failure_basic(self):
        self.r_sdk_failure = [
            weblog.get(
                f"/login?auth=basic&sdk_trigger={trigger}&sdk_event=failure&sdk_user=sdkUser&sdk_user_exists=true",
                headers={"Authorization": BASIC_AUTH_INVALID_USER_HEADER},
            )
            for trigger in SDK_TRIGGERS
        ]

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    @bug(context.library < "java@1.47.0", reason="APPSEC-56744")
    def test_login_sdk_failure_basic(self):
        for request in self.r_sdk_failure:
            assert request.status_code == 401
            for _, trace, span in interfaces.library.get_spans(request=request):
                assert_priority(span, trace)
                meta = span.get("meta", {})

                # mandatory
                assert meta["appsec.events.users.login.failure.usr.login"] == "sdkUser"
                assert meta["_dd.appsec.usr.login"] == INVALID_USER_HASH
                assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "anonymization"
                assert meta["appsec.events.users.login.failure.track"] == "true"
                assert meta["_dd.appsec.events.users.login.failure.sdk"] == "true"
                assert meta["appsec.events.users.login.failure.usr.exists"] == "true"

    def setup_signup_local(self):
        self.r_success = weblog.post("/signup", data=login_data(context, NEW_USER, PASSWORD))

    @missing_feature(context.library == "nodejs", reason="Signup events not implemented")
    @irrelevant(
        context.library == "python" and context.weblog_variant not in ["django-poc", "python3.12", "django-py3.13"],
        reason="No signup in framework",
    )
    @missing_feature(
        context.library < "python@3.2.0.dev"
        and context.weblog_variant in ["django-poc", "python3.12", "django-py3.13"],
        reason="Signup events not implemented yet",
    )
    def test_signup_local(self):
        assert self.r_success.status_code == 200
        for _, trace, span in interfaces.library.get_spans(request=self.r_success):
            assert_priority(span, trace)
            meta = span.get("meta", {})

            # mandatory
            assert meta["appsec.events.users.signup.usr.login"] == NEW_USERNAME_HASH
            assert meta["_dd.appsec.usr.login"] == NEW_USERNAME_HASH
            assert meta["_dd.appsec.events.users.signup.auto.mode"] == "anonymization"
            assert meta["appsec.events.users.signup.track"] == "true"

            # optional (to review for each library)
            if context.library not in libs_without_user_id:
                assert meta["appsec.events.users.signup.usr.id"] == NEW_USER_HASH
                assert meta["_dd.appsec.usr.id"] == NEW_USER_HASH


DISABLED = ("datadog/2/ASM_FEATURES/auto-user-instrum/config", {"auto_user_instrum": {"mode": "disabled"}})
IDENTIFICATION = ("datadog/2/ASM_FEATURES/auto-user-instrum/config", {"auto_user_instrum": {"mode": "identification"}})
ANONYMIZATION = ("datadog/2/ASM_FEATURES/auto-user-instrum/config", {"auto_user_instrum": {"mode": "anonymization"}})


@rfc("https://docs.google.com/document/d/1RT38U6dTTcB-8muiYV4-aVDCsT_XrliyakjtAPyjUpw")
@features.user_monitoring
@scenarios.appsec_auto_events_rc
class Test_V3_Login_Events_RC:
    def _send_rc_and_execute_request(self, config):
        config_state = rc.rc_state.set_config(*config).apply()
        request = weblog.post("/login?auth=local", data=login_data(context, USER, PASSWORD))
        return {"config_state": config_state, "request": request}

    def _assert_response(self, test, validation):
        config_state, request = test["config_state"], test["request"]

        assert config_state.state == rc.ApplyState.ACKNOWLEDGED
        assert request.status_code == 200

        spans = [s for _, _, s in interfaces.library.get_spans(request=request)]
        assert spans, "No spans to validate"
        for span in spans:
            meta = span.get("meta", {})
            validation(meta)

    def setup_rc(self):
        self.disabled = self._send_rc_and_execute_request(DISABLED)
        self.identification = self._send_rc_and_execute_request(IDENTIFICATION)
        self.anonymization = self._send_rc_and_execute_request(ANONYMIZATION)

    def test_rc(self):
        def validate_disabled(meta):
            assert "_dd.appsec.events.users.login.success.auto.mode" not in meta

        def validate_anon(meta):
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "anonymization"

        def validate_iden(meta):
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "identification"

        self._assert_response(self.disabled, validate_disabled)
        self._assert_response(self.identification, validate_iden)
        self._assert_response(self.anonymization, validate_anon)


CONFIG_ENABLED = (
    "datadog/2/ASM_FEATURES/asm_features_activation/config",
    {"asm": {"enabled": True}},
)

BLOCK_USER_RULE = (
    "datadog/2/ASM_DD/rules/config",
    {
        "version": "2.1",
        "metadata": {"rules_version": "1.2.6"},
        "rules": [
            {
                "id": "block-user-id",
                "name": "Block User IDs",
                "tags": {"type": "block_user", "category": "security_response"},
                "conditions": [
                    {
                        "parameters": {"inputs": [{"address": "usr.id"}], "data": "blocked_user_id"},
                        "operator": "exact_match",
                    }
                ],
                "transformers": [],
                "on_match": ["block"],
            },
            {
                "id": "block-user-login",
                "name": "Block User Logins",
                "tags": {"type": "block_user", "category": "security_response"},
                "conditions": [
                    {
                        "parameters": {"inputs": [{"address": "usr.login"}], "data": "blocked_user_login"},
                        "operator": "exact_match",
                    }
                ],
                "transformers": [],
                "on_match": ["block"],
            },
        ],
    },
)

BLOCK_USER_ID = (
    "datadog/2/ASM_DATA/blocked_user_id/config",
    {
        "rules_data": [
            {
                "id": "blocked_user_id",
                "type": "data_with_expiration",
                "data": [{"value": "social-security-id", "expiration": 0}, {"value": "sdkUser", "expiration": 0}],
            },
        ],
    },
)

BLOCK_USER_LOGIN = (
    "datadog/2/ASM_DATA/blocked_user_login/config",
    {
        "rules_data": [
            {
                "id": "blocked_user_login",
                "type": "data_with_expiration",
                "data": [{"value": "test", "expiration": 0}, {"value": "sdkUser", "expiration": 0}],
            },
        ],
    },
)


@rfc("https://docs.google.com/document/d/1RT38U6dTTcB-8muiYV4-aVDCsT_XrliyakjtAPyjUpw")
@features.user_monitoring
@scenarios.appsec_and_rc_enabled
class Test_V3_Login_Events_Blocking:
    def setup_login_event_blocking_auto_id(self):
        rc.rc_state.reset().apply()

        self.r_login = weblog.post("/login?auth=local", data=login_data(context, USER, PASSWORD))

        self.config_state_1 = rc.rc_state.set_config(*BLOCK_USER_RULE).apply()
        self.config_state_2 = rc.rc_state.set_config(*BLOCK_USER_ID).apply()

        self.r_login_blocked = weblog.post("/login?auth=local", data=login_data(context, USER, PASSWORD))

    @irrelevant(context.library == "java", reason="Blocking by user ID not available in java")
    def test_login_event_blocking_auto_id(self):
        assert self.r_login.status_code == 200

        assert self.config_state_1.state == rc.ApplyState.ACKNOWLEDGED
        assert self.config_state_2.state == rc.ApplyState.ACKNOWLEDGED

        if context.library not in libs_without_user_id:
            interfaces.library.assert_waf_attack(self.r_login_blocked, rule="block-user-id")
            assert self.r_login_blocked.status_code == 403

    def setup_login_event_blocking_auto_login(self):
        rc.rc_state.reset().apply()

        self.r_login = weblog.post("/login?auth=local", data=login_data(context, USER, PASSWORD))

        self.config_state_1 = rc.rc_state.set_config(*BLOCK_USER_RULE).apply()
        self.config_state_2 = rc.rc_state.set_config(*BLOCK_USER_LOGIN).apply()

        self.r_login_blocked = weblog.post("/login?auth=local", data=login_data(context, USER, PASSWORD))

    def test_login_event_blocking_auto_login(self):
        assert self.r_login.status_code == 200

        assert self.config_state_1.state == rc.ApplyState.ACKNOWLEDGED
        assert self.config_state_2.state == rc.ApplyState.ACKNOWLEDGED

        interfaces.library.assert_waf_attack(self.r_login_blocked, rule="block-user-login")
        assert self.r_login_blocked.status_code == 403

    def setup_login_event_blocking_sdk(self):
        rc.rc_state.reset().apply()

        self.r_login = [
            weblog.post(
                f"/login?auth=local&sdk_trigger={trigger}&sdk_event=success&sdk_user=sdkUser",
                data=login_data(context, UUID_USER, PASSWORD),
            )
            for trigger in SDK_TRIGGERS
        ]

        self.config_state_1 = rc.rc_state.set_config(*BLOCK_USER_RULE).apply()
        self.config_state_2 = rc.rc_state.set_config(*BLOCK_USER_ID).apply()

        self.r_login_blocked = [
            weblog.post(
                f"/login?auth=local&sdk_trigger={trigger}&sdk_event=success&sdk_user=sdkUser",
                data=login_data(context, UUID_USER, PASSWORD),
            )
            for trigger in SDK_TRIGGERS
        ]

    def test_login_event_blocking_sdk(self):
        for request in self.r_login:
            assert request.status_code == 200

        assert self.config_state_1.state == rc.ApplyState.ACKNOWLEDGED
        assert self.config_state_2.state == rc.ApplyState.ACKNOWLEDGED

        for request in self.r_login_blocked:
            interfaces.library.assert_waf_attack(request, rule="block-user-id")
            assert request.status_code == 403


@rfc("https://docs.google.com/document/d/1RT38U6dTTcB-8muiYV4-aVDCsT_XrliyakjtAPyjUpw")
@features.user_monitoring
@scenarios.remote_config_mocked_backend_asm_dd
class Test_V3_Auto_User_Instrum_Mode_Capability:
    """Validate that ASM_AUTO_USER_INSTRUM_MODE (31) capability is sent"""

    def test_capability_auto_user_instrum_mode(self):
        interfaces.library.assert_rc_capability(Capabilities.ASM_AUTO_USER_INSTRUM_MODE)
