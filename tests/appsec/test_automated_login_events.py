# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

from utils import (
    weblog,
    interfaces,
    context,
    missing_feature,
    scenarios,
    rfc,
    bug,
    features,
    irrelevant,
    remote_config as rc,
)


@rfc("https://docs.google.com/document/d/1-trUpphvyZY7k5ldjhW-MgqWl0xOm7AMEQDJEAZ63_Q/edit#heading=h.8d3o7vtyu1y1")
@features.user_monitoring
class Test_Login_Events:
    "Test login success/failure use cases"

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

    @property
    def username_key(self):
        """ In Rails the parametesr are group by scope. In the case of the test the scope is user. The syntax to group parameters in a POST request is scope[parameter] """
        return "user[username]" if "rails" in context.weblog_variant else "username"

    @property
    def password_key(self):
        """ In Rails the parametesr are group by scope. In the case of the test the scope is user. The syntax to group parameters in a POST request is scope[parameter] """
        return "user[password]" if "rails" in context.weblog_variant else "password"

    USER = "test"
    UUID_USER = "testuuid"
    PASSWORD = "1234"
    INVALID_USER = "invalidUser"

    BASIC_AUTH_USER_HEADER = "Basic dGVzdDoxMjM0"  # base64(test:1234)
    BASIC_AUTH_USER_UUID_HEADER = "Basic dGVzdHV1aWQ6MTIzNA=="  # base64(testuuid:1234)
    BASIC_AUTH_INVALID_USER_HEADER = "Basic aW52YWxpZFVzZXI6MTIzNA=="  # base64(invalidUser:1234)
    BASIC_AUTH_INVALID_PASSWORD_HEADER = "Basic dGVzdDoxMjM0NQ=="  # base64(test:12345)

    def setup_login_pii_success_local(self):
        self.r_pii_success = weblog.post(
            "/login?auth=local", data={self.username_key: self.USER, self.password_key: self.PASSWORD}
        )

    @bug(context.library < "nodejs@4.9.0", reason="Reports empty space in usr.id when id is a PII")
    @irrelevant(
        context.library == "python" and context.scenario.weblog_variant in ["django-poc", "python3.12"],
        reason="APM reports all user id for now on Django",
    )
    def test_login_pii_success_local(self):
        assert self.r_pii_success.status_code == 200
        for _, _, span in interfaces.library.get_spans(request=self.r_pii_success):
            meta = span.get("meta", {})
            assert "usr.id" not in meta
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "safe"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert_priority(span, meta)

    def setup_login_pii_success_basic(self):
        self.r_pii_success = weblog.get("/login?auth=basic", headers={"Authorization": self.BASIC_AUTH_USER_HEADER})

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    @bug(context.library < "nodejs@4.9.0", reason="Reports empty space in usr.id when id is a PII")
    @irrelevant(
        context.library == "python" and context.scenario.weblog_variant in ["django-poc", "python3.12"],
        reason="APM reports all user id for now on Django",
    )
    @irrelevant(
        context.library == "java",
        reason="Basic auth makes insecure protocol test fail due to dedup, fixed in the next tracer release",
    )
    def test_login_pii_success_basic(self):
        assert self.r_pii_success.status_code == 200
        for _, _, span in interfaces.library.get_spans(request=self.r_pii_success):
            meta = span.get("meta", {})
            assert "usr.id" not in meta
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "safe"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert_priority(span, meta)

    def setup_login_success_local(self):
        self.r_success = weblog.post(
            "/login?auth=local", data={self.username_key: self.UUID_USER, self.password_key: self.PASSWORD}
        )

    def test_login_success_local(self):
        assert self.r_success.status_code == 200
        for _, _, span in interfaces.library.get_spans(request=self.r_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "safe"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == "591dc126-8431-4d0f-9509-b23318d3dce4"
            assert_priority(span, meta)

    def setup_login_success_basic(self):
        self.r_success = weblog.get("/login?auth=basic", headers={"Authorization": self.BASIC_AUTH_USER_UUID_HEADER})

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    @irrelevant(
        context.library == "java",
        reason="Basic auth makes insecure protocol test fail due to dedup, fixed in the next tracer release",
    )
    def test_login_success_basic(self):
        assert self.r_success.status_code == 200
        for _, _, span in interfaces.library.get_spans(request=self.r_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "safe"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == "591dc126-8431-4d0f-9509-b23318d3dce4"
            assert_priority(span, meta)

    def setup_login_wrong_user_failure_local(self):
        self.r_wrong_user_failure = weblog.post(
            "/login?auth=local", data={self.username_key: self.INVALID_USER, self.password_key: self.PASSWORD}
        )

    @bug(context.library < "nodejs@4.9.0", reason="Reports empty space in usr.id when id is a PII")
    def test_login_wrong_user_failure_local(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, _, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            if context.library != "nodejs":
                # Currently in nodejs there is no way to check if the user exists upon authentication failure so
                # this assertion is disabled for this library.
                assert meta["appsec.events.users.login.failure.usr.exists"] == "false"

            assert "appsec.events.users.login.failure.usr.id" not in meta
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "safe"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert_priority(span, meta)

    def setup_login_wrong_user_failure_basic(self):
        self.r_wrong_user_failure = weblog.get(
            "/login?auth=basic", headers={"Authorization": self.BASIC_AUTH_INVALID_USER_HEADER}
        )

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    @bug(context.library < "nodejs@4.9.0", reason="Reports empty space in usr.id when id is a PII")
    @irrelevant(
        context.library == "java",
        reason="Basic auth makes insecure protocol test fail due to dedup, fixed in the next tracer release",
    )
    def test_login_wrong_user_failure_basic(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, _, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            if context.library != "nodejs":
                # Currently in nodejs there is no way to check if the user exists upon authentication failure so
                # this assertion is disabled for this library.
                assert meta["appsec.events.users.login.failure.usr.exists"] == "false"

            assert "appsec.events.users.login.failure.usr.id" not in meta
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "safe"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert_priority(span, meta)

    def setup_login_wrong_password_failure_local(self):
        self.r_wrong_user_failure = weblog.post(
            "/login?auth=local", data={self.username_key: self.USER, self.password_key: "12345"}
        )

    @bug(context.library < "nodejs@4.9.0", reason="Reports empty space in usr.id when id is a PII")
    def test_login_wrong_password_failure_local(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, _, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            if context.library != "nodejs":
                # Currently in nodejs there is no way to check if the user exists upon authentication failure so
                # this assertion is disabled for this library.
                assert meta["appsec.events.users.login.failure.usr.exists"] == "true"

            assert "appsec.events.users.login.failure.usr.id" not in meta
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "safe"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert_priority(span, meta)

    def setup_login_wrong_password_failure_basic(self):
        self.r_wrong_user_failure = weblog.get(
            "/login?auth=basic", headers={"Authorization": self.BASIC_AUTH_INVALID_PASSWORD_HEADER}
        )

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    @bug(context.library < "nodejs@4.9.0", reason="Reports empty space in usr.id when id is a PII")
    @irrelevant(
        context.library == "java",
        reason="Basic auth makes insecure protocol test fail due to dedup, fixed in the next tracer release",
    )
    def test_login_wrong_password_failure_basic(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, _, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            if context.library != "nodejs":
                # Currently in nodejs there is no way to check if the user exists upon authentication failure so
                # this assertion is disabled for this library.
                assert meta["appsec.events.users.login.failure.usr.exists"] == "true"

            assert "appsec.events.users.login.failure.usr.id" not in meta
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "safe"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert_priority(span, meta)

    def setup_login_sdk_success_local(self):
        self.r_sdk_success = weblog.post(
            "/login?auth=local&sdk_event=success&sdk_user=sdkUser",
            data={self.username_key: self.USER, self.password_key: self.PASSWORD},
        )

    def test_login_sdk_success_local(self):
        assert self.r_sdk_success.status_code == 200
        for _, _, span in interfaces.library.get_spans(request=self.r_sdk_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "safe"
            assert meta["_dd.appsec.events.users.login.success.sdk"] == "true"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == "sdkUser"
            assert_priority(span, meta)

    def setup_login_sdk_success_basic(self):
        self.r_sdk_success = weblog.get(
            "/login?auth=basic&sdk_event=success&sdk_user=sdkUser",
            headers={"Authorization": self.BASIC_AUTH_USER_HEADER},
        )

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    @irrelevant(
        context.library == "java",
        reason="Basic auth makes insecure protocol test fail due to dedup, fixed in the next tracer release",
    )
    def test_login_sdk_success_basic(self):
        assert self.r_sdk_success.status_code == 200
        for _, _, span in interfaces.library.get_spans(request=self.r_sdk_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "safe"
            assert meta["_dd.appsec.events.users.login.success.sdk"] == "true"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == "sdkUser"
            assert_priority(span, meta)

    def setup_login_sdk_failure_local(self):
        self.r_sdk_failure = weblog.post(
            "/login?auth=local&sdk_event=failure&sdk_user=sdkUser&sdk_user_exists=true",
            data={self.username_key: self.INVALID_USER, self.password_key: self.PASSWORD},
        )

    def test_login_sdk_failure_local(self):
        assert self.r_sdk_failure.status_code == 401
        for _, _, span in interfaces.library.get_spans(request=self.r_sdk_failure):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "safe"
            assert meta["_dd.appsec.events.users.login.failure.sdk"] == "true"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert meta["appsec.events.users.login.failure.usr.id"] == "sdkUser"
            assert meta["appsec.events.users.login.failure.usr.exists"] == "true"
            assert_priority(span, meta)

    def setup_login_sdk_failure_basic(self):
        self.r_sdk_failure = weblog.get(
            "/login?auth=basic&sdk_event=failure&sdk_user=sdkUser&sdk_user_exists=true",
            headers={"Authorization": self.BASIC_AUTH_INVALID_USER_HEADER},
        )

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    @irrelevant(
        context.library == "java",
        reason="Basic auth makes insecure protocol test fail due to dedup, fixed in the next tracer release",
    )
    def test_login_sdk_failure_basic(self):
        assert self.r_sdk_failure.status_code == 401
        for _, _, span in interfaces.library.get_spans(request=self.r_sdk_failure):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "safe"
            assert meta["_dd.appsec.events.users.login.failure.sdk"] == "true"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert meta["appsec.events.users.login.failure.usr.id"] == "sdkUser"
            assert meta["appsec.events.users.login.failure.usr.exists"] == "true"
            assert_priority(span, meta)


@rfc("https://docs.google.com/document/d/1-trUpphvyZY7k5ldjhW-MgqWl0xOm7AMEQDJEAZ63_Q/edit#heading=h.8d3o7vtyu1y1")
@scenarios.appsec_auto_events_extended
@features.user_monitoring
class Test_Login_Events_Extended:
    "Test login success/failure use cases"

    @property
    def username_key(self):
        """ In Rails the parametesr are group by scope. In the case of the test the scope is user. The syntax to group parameters in a POST request is scope[parameter] """
        return "user[username]" if "rails" in context.weblog_variant else "username"

    @property
    def password_key(self):
        """ In Rails the parametesr are group by scope. In the case of the test the scope is user. The syntax to group parameters in a POST request is scope[parameter] """
        return "user[password]" if "rails" in context.weblog_variant else "password"

    USER = "test"
    UUID_USER = "testuuid"
    PASSWORD = "1234"

    BASIC_AUTH_USER_HEADER = "Basic dGVzdDoxMjM0"  # base64(test:1234)
    BASIC_AUTH_USER_UUID_HEADER = "Basic dGVzdHV1aWQ6MTIzNA=="  # base64(testuuid:1234)

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

    def setup_login_success_local(self):
        self.r_success = weblog.post(
            "/login?auth=local", data={self.username_key: self.USER, self.password_key: self.PASSWORD}
        )

    def test_login_success_local(self):
        assert self.r_success.status_code == 200
        for _, _, span in interfaces.library.get_spans(request=self.r_success):
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
            else:
                assert meta["usr.email"] == "testuser@ddog.com"
                assert meta["usr.username"] == "test"
                assert meta["usr.login"] == "test"

            assert_priority(span, meta)

    def setup_login_success_basic(self):
        self.r_success = weblog.get("/login?auth=basic", headers={"Authorization": self.BASIC_AUTH_USER_HEADER})

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    @irrelevant(
        context.library == "java",
        reason="Basic auth makes insecure protocol test fail due to dedup, fixed in the next tracer release",
    )
    def test_login_success_basic(self):
        assert self.r_success.status_code == 200
        for _, _, span in interfaces.library.get_spans(request=self.r_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "extended"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == "social-security-id"
            assert meta["usr.email"] == "testuser@ddog.com"

            if context.library in ("dotnet", "python"):
                # theres no login field in dotnet
                # usr.name was in the sdk before so it was kept as is
                assert meta["usr.name"] == "test"
            elif context.library == "ruby":
                # theres no login field in ruby
                assert meta["usr.username"] == "test"
            else:
                assert meta["usr.username"] == "test"
                assert meta["usr.login"] == "test"

            assert_priority(span, meta)

    def setup_login_wrong_user_failure_local(self):
        self.r_wrong_user_failure = weblog.post(
            "/login?auth=local", data={self.username_key: "invalidUser", self.password_key: self.PASSWORD}
        )

    def test_login_wrong_user_failure_local(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, _, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            if context.library != "nodejs":
                # Currently in nodejs there is no way to check if the user exists upon authentication failure so
                # this assertion is disabled for this library.
                assert meta["appsec.events.users.login.failure.usr.exists"] == "false"

            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "extended"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            if context.library == "ruby":
                # In ruby we do not have access to the user object since it fails with invalid username
                # For that reason we can not extract id, email or username
                assert meta.get("appsec.events.users.login.failure.usr.id") == None
                assert meta.get("appsec.events.users.login.failure.usr.email") == None
                assert meta.get("appsec.events.users.login.failure.usr.username") == None
            elif context.library == "dotnet":
                # in dotnet if the user doesn't exist, there is no id (generated upon user creation)
                assert meta["appsec.events.users.login.failure.username"] == "invalidUser"
            else:
                assert meta["appsec.events.users.login.failure.usr.id"] == "invalidUser"
            assert_priority(span, meta)

    def setup_login_wrong_user_failure_basic(self):
        self.r_wrong_user_failure = weblog.get(
            "/login?auth=basic", headers={"Authorization": "Basic aW52YWxpZFVzZXI6MTIzNA=="}
        )

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    def test_login_wrong_user_failure_basic(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, _, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            if context.library != "nodejs":
                # Currently in nodejs there is no way to check if the user exists upon authentication failure so
                # this assertion is disabled for this library.
                assert meta["appsec.events.users.login.failure.usr.exists"] == "false"

            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "extended"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            if context.library == "ruby":
                # In ruby we do not have access to the user object since it fails with invalid username
                # For that reason we can not extract id, email or username
                assert meta.get("appsec.events.users.login.failure.usr.id") == None
                assert meta.get("appsec.events.users.login.failure.usr.email") == None
                assert meta.get("appsec.events.users.login.failure.usr.username") == None
            elif context.library == "dotnet":
                # in dotnet if the user doesn't exist, there is no id (generated upon user creation)
                assert meta["appsec.events.users.login.failure.username"] == "invalidUser"
            else:
                assert meta["appsec.events.users.login.failure.usr.id"] == "invalidUser"
            assert_priority(span, meta)

    def setup_login_wrong_password_failure_local(self):
        self.r_wrong_user_failure = weblog.post(
            "/login?auth=local", data={self.username_key: self.USER, self.password_key: "12345"}
        )

    def test_login_wrong_password_failure_local(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, _, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            if context.library == "nodejs":
                # Currently in nodejs there is no way to check if the user exists upon authentication failure so
                # this assertion is disabled for this library.
                assert meta["appsec.events.users.login.failure.usr.id"] == "test"
            else:
                assert meta["appsec.events.users.login.failure.usr.exists"] == "true"
                assert meta["appsec.events.users.login.failure.usr.id"] == "social-security-id"
                assert meta["appsec.events.users.login.failure.email"] == "testuser@ddog.com"
                assert meta["appsec.events.users.login.failure.username"] == "test"

            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "extended"
            assert meta["appsec.events.users.login.failure.track"] == "true"

            assert_priority(span, meta)

    def setup_login_wrong_password_failure_basic(self):
        self.r_wrong_user_failure = weblog.get("/login?auth=basic", headers={"Authorization": "Basic dGVzdDoxMjM0NQ=="})

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    @irrelevant(
        context.library == "java",
        reason="Basic auth makes insecure protocol test fail due to dedup, fixed in the next tracer release",
    )
    def test_login_wrong_password_failure_basic(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, _, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            if context.library != "nodejs":
                # Currently in nodejs there is no way to check if the user exists upon authentication failure so
                # this assertion is disabled for this library.
                assert meta["appsec.events.users.login.failure.usr.exists"] == "true"
                assert meta["appsec.events.users.login.failure.usr.id"] == "social-security-id"
                assert meta["appsec.events.users.login.failure.email"] == "testuser@ddog.com"
                assert meta["appsec.events.users.login.failure.username"] == "test"
            else:
                assert meta["appsec.events.users.login.failure.usr.id"] == "test"

            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "extended"
            assert meta["appsec.events.users.login.failure.track"] == "true"

            assert_priority(span, meta)

    def setup_login_sdk_success_local(self):
        self.r_sdk_success = weblog.post(
            "/login?auth=local&sdk_event=success&sdk_user=sdkUser",
            data={self.username_key: self.USER, self.password_key: self.PASSWORD},
        )

    def test_login_sdk_success_local(self):
        assert self.r_sdk_success.status_code == 200
        for _, _, span in interfaces.library.get_spans(request=self.r_sdk_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "extended"
            assert meta["_dd.appsec.events.users.login.success.sdk"] == "true"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == "sdkUser"
            assert_priority(span, meta)

    def setup_login_sdk_success_basic(self):
        self.r_sdk_success = weblog.get(
            "/login?auth=basic&sdk_event=success&sdk_user=sdkUser",
            headers={"Authorization": self.BASIC_AUTH_USER_HEADER},
        )

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    @irrelevant(
        context.library == "java",
        reason="Basic auth makes insecure protocol test fail due to dedup, fixed in the next tracer release",
    )
    def test_login_sdk_success_basic(self):
        assert self.r_sdk_success.status_code == 200
        for _, _, span in interfaces.library.get_spans(request=self.r_sdk_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "extended"
            assert meta["_dd.appsec.events.users.login.success.sdk"] == "true"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == "sdkUser"
            assert_priority(span, meta)

    def setup_login_sdk_failure_basic(self):
        self.r_sdk_failure = weblog.get(
            "/login?auth=basic&sdk_event=failure&sdk_user=sdkUser&sdk_user_exists=true",
            headers={"Authorization": "Basic aW52YWxpZFVzZXI6MTIzNA=="},
        )

    @missing_feature(context.library == "php", reason="Basic auth not implemented")
    @irrelevant(
        context.library == "java",
        reason="Basic auth makes insecure protocol test fail due to dedup, fixed in the next tracer release",
    )
    def test_login_sdk_failure_basic(self):
        assert self.r_sdk_failure.status_code == 401
        for _, _, span in interfaces.library.get_spans(request=self.r_sdk_failure):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "extended"
            assert meta["_dd.appsec.events.users.login.failure.sdk"] == "true"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert meta["appsec.events.users.login.failure.usr.id"] == "sdkUser"
            assert meta["appsec.events.users.login.failure.usr.exists"] == "true"
            assert_priority(span, meta)

    def setup_login_sdk_failure_local(self):
        self.r_sdk_failure = weblog.post(
            "/login?auth=local&sdk_event=failure&sdk_user=sdkUser&sdk_user_exists=true",
            data={self.username_key: "invalidUser", self.password_key: self.PASSWORD},
        )

    def test_login_sdk_failure_local(self):
        assert self.r_sdk_failure.status_code == 401
        for _, _, span in interfaces.library.get_spans(request=self.r_sdk_failure):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "extended"
            assert meta["_dd.appsec.events.users.login.failure.sdk"] == "true"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert meta["appsec.events.users.login.failure.usr.id"] == "sdkUser"
            assert meta["appsec.events.users.login.failure.usr.exists"] == "true"
            assert_priority(span, meta)

    def setup_login_success_headers(self):
        self.r_hdr_success = weblog.post(
            "/login?auth=local",
            data={self.username_key: self.USER, self.password_key: self.PASSWORD},
            headers=self.HEADERS,
        )

    @missing_feature(library="dotnet")
    @missing_feature(library="java")
    @missing_feature(library="nodejs")
    @missing_feature(library="php")
    @missing_feature(library="ruby")
    def test_login_success_headers(self):
        # Validate that all relevant headers are included on user login success on extended mode

        def validate_login_success_headers(span):
            if span.get("parent_id") not in (0, None):
                return

            for header in self.HEADERS:
                assert f"http.request.headers.{header.lower()}" in span["meta"], f"Can't find {header} in span's meta"
            return True

        interfaces.library.validate_spans(self.r_hdr_success, validate_login_success_headers)

    def setup_login_failure_headers(self):
        self.r_hdr_failure = weblog.post(
            "/login?auth=local",
            data={self.username_key: "invalidUser", self.password_key: self.PASSWORD},
            headers=self.HEADERS,
        )

    @missing_feature(library="dotnet")
    @missing_feature(library="java")
    @missing_feature(library="nodejs")
    @missing_feature(library="php")
    @missing_feature(library="ruby")
    def test_login_failure_headers(self):
        # Validate that all relevant headers are included on user login failure on extended mode

        def validate_login_failure_headers(span):
            if span.get("parent_id") not in (0, None):
                return

            for header in self.HEADERS:
                assert f"http.request.headers.{header.lower()}" in span["meta"], f"Can't find {header} in span's meta"
            return True

        interfaces.library.validate_spans(self.r_hdr_failure, validate_login_failure_headers)


@rfc("https://docs.google.com/document/d/19VHLdJLVFwRb_JrE87fmlIM5CL5LdOBv4AmLxgdo9qI/edit")
@features.user_monitoring
class Test_V2_Login_Events:
    """
    Test login success/failure use cases
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

    @property
    def username_key(self):
        """ In Rails the parametesr are group by scope. In the case of the test the scope is user. The syntax to group parameters in a POST request is scope[parameter] """
        return "user[username]" if "rails" in context.weblog_variant else "username"

    @property
    def password_key(self):
        """ In Rails the parametesr are group by scope. In the case of the test the scope is user. The syntax to group parameters in a POST request is scope[parameter] """
        return "user[password]" if "rails" in context.weblog_variant else "password"

    USER = "test"
    UUID_USER = "testuuid"
    PASSWORD = "1234"
    INVALID_USER = "invalidUser"

    BASIC_AUTH_USER_HEADER = "Basic dGVzdDoxMjM0"  # base64(test:1234)
    BASIC_AUTH_USER_UUID_HEADER = "Basic dGVzdHV1aWQ6MTIzNA=="  # base64(testuuid:1234)
    BASIC_AUTH_INVALID_USER_HEADER = "Basic aW52YWxpZFVzZXI6MTIzNA=="  # base64(invalidUser:1234)
    BASIC_AUTH_INVALID_PASSWORD_HEADER = "Basic dGVzdDoxMjM0NQ=="  # base64(test:12345)

    def setup_login_pii_success_local(self):
        self.r_pii_success = weblog.post(
            "/login?auth=local", data={self.username_key: self.USER, self.password_key: self.PASSWORD}
        )

    def test_login_pii_success_local(self):
        assert self.r_pii_success.status_code == 200
        for _, _, span in interfaces.library.get_spans(request=self.r_pii_success):
            meta = span.get("meta", {})
            assert "usr.id" in meta
            assert meta["usr.id"] == "social-security-id"
            # deprecated tags
            assert "appsec.events.users.login.success.email" not in meta
            assert "appsec.events.users.login.success.username" not in meta
            assert "appsec.events.users.login.success.login" not in meta
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "identification"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert_priority(span, meta)

    def setup_login_pii_success_basic(self):
        self.r_pii_success = weblog.get("/login?auth=basic", headers={"Authorization": self.BASIC_AUTH_USER_HEADER})

    @irrelevant(
        context.library == "java",
        reason="Basic auth makes insecure protocol test fail due to dedup, fixed in the next tracer release",
    )
    def test_login_pii_success_basic(self):
        assert self.r_pii_success.status_code == 200
        for _, _, span in interfaces.library.get_spans(request=self.r_pii_success):
            meta = span.get("meta", {})
            assert "usr.id" in meta
            assert meta["usr.id"] == "social-security-id"
            # deprecated tags
            assert "appsec.events.users.login.success.email" not in meta
            assert "appsec.events.users.login.success.username" not in meta
            assert "appsec.events.users.login.success.login" not in meta
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "identification"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert_priority(span, meta)

    def setup_login_success_local(self):
        self.r_success = weblog.post(
            "/login?auth=local", data={self.username_key: self.UUID_USER, self.password_key: self.PASSWORD}
        )

    def test_login_success_local(self):
        assert self.r_success.status_code == 200
        for _, _, span in interfaces.library.get_spans(request=self.r_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "identification"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == "591dc126-8431-4d0f-9509-b23318d3dce4"
            # deprecated tags
            assert "appsec.events.users.login.success.email" not in meta
            assert "appsec.events.users.login.success.username" not in meta
            assert "appsec.events.users.login.success.login" not in meta
            assert_priority(span, meta)

    def setup_login_success_basic(self):
        self.r_success = weblog.get("/login?auth=basic", headers={"Authorization": self.BASIC_AUTH_USER_UUID_HEADER})

    @irrelevant(
        context.library == "java",
        reason="Basic auth makes insecure protocol test fail due to dedup, fixed in the next tracer release",
    )
    def test_login_success_basic(self):
        assert self.r_success.status_code == 200
        for _, _, span in interfaces.library.get_spans(request=self.r_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "identification"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == "591dc126-8431-4d0f-9509-b23318d3dce4"
            # deprecated tags
            assert "appsec.events.users.login.success.email" not in meta
            assert "appsec.events.users.login.success.username" not in meta
            assert "appsec.events.users.login.success.login" not in meta
            assert_priority(span, meta)

    def setup_login_wrong_user_failure_local(self):
        self.r_wrong_user_failure = weblog.post(
            "/login?auth=local", data={self.username_key: self.INVALID_USER, self.password_key: self.PASSWORD}
        )

    def test_login_wrong_user_failure_local(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, _, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            if context.library != "nodejs":
                # Currently in nodejs there is no way to check if the user exists upon authentication failure so
                # this assertion is disabled for this library.
                assert meta["appsec.events.users.login.failure.usr.exists"] == "false"

            assert meta["appsec.events.users.login.failure.usr.id"] == "invalidUser"
            assert "appsec.events.users.login.failure.usr.email" not in meta
            assert "appsec.events.users.login.failure.usr.login" not in meta
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "identification"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert_priority(span, meta)

    def setup_login_wrong_user_failure_basic(self):
        self.r_wrong_user_failure = weblog.get(
            "/login?auth=basic", headers={"Authorization": self.BASIC_AUTH_INVALID_USER_HEADER}
        )

    @irrelevant(
        context.library == "java",
        reason="Basic auth makes insecure protocol test fail due to dedup, fixed in the next tracer release",
    )
    def test_login_wrong_user_failure_basic(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, _, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            if context.library != "nodejs":
                # Currently in nodejs there is no way to check if the user exists upon authentication failure so
                # this assertion is disabled for this library.
                assert meta["appsec.events.users.login.failure.usr.exists"] == "false"

            assert meta["appsec.events.users.login.failure.usr.id"] == "invalidUser"
            assert "appsec.events.users.login.failure.usr.email" not in meta
            assert "appsec.events.users.login.failure.usr.login" not in meta
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "identification"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert_priority(span, meta)

    def setup_login_wrong_password_failure_local(self):
        self.r_wrong_user_failure = weblog.post(
            "/login?auth=local", data={self.username_key: self.USER, self.password_key: "12345"}
        )

    def test_login_wrong_password_failure_local(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, _, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            if context.library != "nodejs":
                # Currently in nodejs there is no way to check if the user exists upon authentication failure so
                # this assertion is disabled for this library.
                assert meta["appsec.events.users.login.failure.usr.exists"] == "true"

            assert "appsec.events.users.login.failure.usr.id" in meta
            assert meta["appsec.events.users.login.failure.usr.id"] == "social-security-id"
            # deprecated
            assert "appsec.events.users.login.failure.usr.email" not in meta
            assert "appsec.events.users.login.failure.usr.login" not in meta
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "identification"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert_priority(span, meta)

    def setup_login_wrong_password_failure_basic(self):
        self.r_wrong_user_failure = weblog.get(
            "/login?auth=basic", headers={"Authorization": self.BASIC_AUTH_INVALID_PASSWORD_HEADER}
        )

    @irrelevant(
        context.library == "java",
        reason="Basic auth makes insecure protocol test fail due to dedup, fixed in the next tracer release",
    )
    def test_login_wrong_password_failure_basic(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, _, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            if context.library != "nodejs":
                # Currently in nodejs there is no way to check if the user exists upon authentication failure so
                # this assertion is disabled for this library.
                assert meta["appsec.events.users.login.failure.usr.exists"] == "true"

            assert "appsec.events.users.login.failure.usr.id" in meta
            assert meta["appsec.events.users.login.failure.usr.id"] == "social-security-id"
            assert "appsec.events.users.login.failure.usr.email" not in meta
            assert "appsec.events.users.login.failure.usr.login" not in meta
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "identification"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert_priority(span, meta)

    def setup_login_sdk_success_local(self):
        self.r_sdk_success = weblog.post(
            "/login?auth=local&sdk_event=success&sdk_user=sdkUser",
            data={self.username_key: self.USER, self.password_key: self.PASSWORD},
        )

    def test_login_sdk_success_local(self):
        assert self.r_sdk_success.status_code == 200
        for _, _, span in interfaces.library.get_spans(request=self.r_sdk_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "identification"
            assert meta["_dd.appsec.events.users.login.success.sdk"] == "true"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == "sdkUser"
            assert_priority(span, meta)

    def setup_login_sdk_success_basic(self):
        self.r_sdk_success = weblog.get(
            "/login?auth=basic&sdk_event=success&sdk_user=sdkUser",
            headers={"Authorization": self.BASIC_AUTH_USER_HEADER},
        )

    @irrelevant(
        context.library == "java",
        reason="Basic auth makes insecure protocol test fail due to dedup, fixed in the next tracer release",
    )
    def test_login_sdk_success_basic(self):
        assert self.r_sdk_success.status_code == 200
        for _, _, span in interfaces.library.get_spans(request=self.r_sdk_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "identification"
            assert meta["_dd.appsec.events.users.login.success.sdk"] == "true"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == "sdkUser"
            assert_priority(span, meta)

    def setup_login_sdk_failure_local(self):
        self.r_sdk_failure = weblog.post(
            "/login?auth=local&sdk_event=failure&sdk_user=sdkUser&sdk_user_exists=true",
            data={self.username_key: self.INVALID_USER, self.password_key: self.PASSWORD},
        )

    def test_login_sdk_failure_local(self):
        assert self.r_sdk_failure.status_code == 401
        for _, _, span in interfaces.library.get_spans(request=self.r_sdk_failure):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "identification"
            assert meta["_dd.appsec.events.users.login.failure.sdk"] == "true"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert meta["appsec.events.users.login.failure.usr.id"] == "sdkUser"
            assert meta["appsec.events.users.login.failure.usr.exists"] == "true"
            assert_priority(span, meta)

    def setup_login_sdk_failure_basic(self):
        self.r_sdk_failure = weblog.get(
            "/login?auth=basic&sdk_event=failure&sdk_user=sdkUser&sdk_user_exists=true",
            headers={"Authorization": self.BASIC_AUTH_INVALID_USER_HEADER},
        )

    @irrelevant(
        context.library == "java",
        reason="Basic auth makes insecure protocol test fail due to dedup, fixed in the next tracer release",
    )
    def test_login_sdk_failure_basic(self):
        assert self.r_sdk_failure.status_code == 401
        for _, _, span in interfaces.library.get_spans(request=self.r_sdk_failure):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "identification"
            assert meta["_dd.appsec.events.users.login.failure.sdk"] == "true"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert meta["appsec.events.users.login.failure.usr.id"] == "sdkUser"
            assert meta["appsec.events.users.login.failure.usr.exists"] == "true"
            assert_priority(span, meta)


@rfc("https://docs.google.com/document/d/19VHLdJLVFwRb_JrE87fmlIM5CL5LdOBv4AmLxgdo9qI/edit")
@scenarios.appsec_auto_events_extended
@features.user_monitoring
class Test_V2_Login_Events_Anon:
    """Test login success/failure use cases
       As default mode is identification, this scenario will test anonymization. 
    """

    @property
    def username_key(self):
        """ In Rails the parametesr are group by scope. In the case of the test the scope is user. The syntax to group parameters in a POST request is scope[parameter] """
        return "user[username]" if "rails" in context.weblog_variant else "username"

    @property
    def password_key(self):
        """ In Rails the parametesr are group by scope. In the case of the test the scope is user. The syntax to group parameters in a POST request is scope[parameter] """
        return "user[password]" if "rails" in context.weblog_variant else "password"

    USER = "test"
    USER_HASH = "anon_5f31ffaf95946d2dc703ddc96a100de5"
    UUID_USER = "testuuid"
    PASSWORD = "1234"

    BASIC_AUTH_USER_HEADER = "Basic dGVzdDoxMjM0"  # base64(test:1234)
    BASIC_AUTH_USER_UUID_HEADER = "Basic dGVzdHV1aWQ6MTIzNA=="  # base64(testuuid:1234)

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

    def setup_login_success_local(self):
        self.r_success = weblog.post(
            "/login?auth=local", data={self.username_key: self.USER, self.password_key: self.PASSWORD}
        )

    def test_login_success_local(self):
        assert self.r_success.status_code == 200
        for _, _, span in interfaces.library.get_spans(request=self.r_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "anonymization"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == self.USER_HASH

            # deprecated
            "appsec.events.users.login.success.username" not in meta
            "appsec.events.users.login.success.email" not in meta
            "usr.email" not in meta
            "usr.username" not in meta
            "usr.login" not in meta

            assert_priority(span, meta)

    def setup_login_success_basic(self):
        self.r_success = weblog.get("/login?auth=basic", headers={"Authorization": self.BASIC_AUTH_USER_HEADER})

    @irrelevant(
        context.library == "java",
        reason="Basic auth makes insecure protocol test fail due to dedup, fixed in the next tracer release",
    )
    def test_login_success_basic(self):
        assert self.r_success.status_code == 200
        for _, _, span in interfaces.library.get_spans(request=self.r_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "anonymization"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == self.USER_HASH

            # deprecated
            "appsec.events.users.login.success.username" not in meta
            "appsec.events.users.login.success.email" not in meta
            "usr.email" not in meta
            "usr.username" not in meta
            "usr.login" not in meta

            assert_priority(span, meta)

    def setup_login_wrong_user_failure_local(self):
        self.r_wrong_user_failure = weblog.post(
            "/login?auth=local", data={self.username_key: "invalidUser", self.password_key: self.PASSWORD}
        )

    def test_login_wrong_user_failure_local(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, _, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            assert meta["appsec.events.users.login.failure.usr.exists"] == "false"

            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "anonymization"
            assert meta["appsec.events.users.login.failure.track"] == "true"

            assert meta["appsec.events.users.login.failure.usr.id"] == "anon_2141e3bee69f7de45b4f1d8d1f29258a"
            assert "appsec.events.users.login.failure.email" not in meta
            assert "appsec.events.users.login.failure.username" not in meta

            assert_priority(span, meta)

    def setup_login_wrong_user_failure_basic(self):
        self.r_wrong_user_failure = weblog.get(
            "/login?auth=basic", headers={"Authorization": "Basic aW52YWxpZFVzZXI6MTIzNA=="}
        )

    @irrelevant(
        context.library == "java",
        reason="Basic auth makes insecure protocol test fail due to dedup, fixed in the next tracer release",
    )
    def test_login_wrong_user_failure_basic(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, _, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            assert meta["appsec.events.users.login.failure.usr.exists"] == "false"

            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "anonymization"
            assert meta["appsec.events.users.login.failure.track"] == "true"

            assert meta["appsec.events.users.login.failure.usr.id"] == "anon_2141e3bee69f7de45b4f1d8d1f29258a"
            assert "appsec.events.users.login.failure.email" not in meta
            assert "appsec.events.users.login.failure.username" not in meta

            assert_priority(span, meta)

    def setup_login_wrong_password_failure_local(self):
        self.r_wrong_user_failure = weblog.post(
            "/login?auth=local", data={self.username_key: self.USER, self.password_key: "12345"}
        )

    def test_login_wrong_password_failure_local(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, _, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            assert meta["appsec.events.users.login.failure.usr.exists"] == "true"
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "anonymization"
            assert meta["appsec.events.users.login.failure.track"] == "true"

            assert meta["appsec.events.users.login.failure.usr.id"] == self.USER_HASH
            assert "appsec.events.users.login.failure.email" not in meta
            assert "appsec.events.users.login.failure.username" not in meta

            assert_priority(span, meta)

    def setup_login_wrong_password_failure_basic(self):
        self.r_wrong_user_failure = weblog.get("/login?auth=basic", headers={"Authorization": "Basic dGVzdDoxMjM0NQ=="})

    @irrelevant(
        context.library == "java",
        reason="Basic auth makes insecure protocol test fail due to dedup, fixed in the next tracer release",
    )
    def test_login_wrong_password_failure_basic(self):
        assert self.r_wrong_user_failure.status_code == 401
        for _, _, span in interfaces.library.get_spans(request=self.r_wrong_user_failure):
            meta = span.get("meta", {})
            assert meta["appsec.events.users.login.failure.usr.exists"] == "true"
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "anonymization"
            assert meta["appsec.events.users.login.failure.track"] == "true"

            assert meta["appsec.events.users.login.failure.usr.id"] == self.USER_HASH
            assert "appsec.events.users.login.failure.email" not in meta
            assert "appsec.events.users.login.failure.username" not in meta

            assert_priority(span, meta)

    def setup_login_sdk_success_local(self):
        self.r_sdk_success = weblog.post(
            "/login?auth=local&sdk_event=success&sdk_user=sdkUser",
            data={self.username_key: self.USER, self.password_key: self.PASSWORD},
        )

    def test_login_sdk_success_local(self):
        assert self.r_sdk_success.status_code == 200
        for _, _, span in interfaces.library.get_spans(request=self.r_sdk_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "anonymization"
            assert meta["_dd.appsec.events.users.login.success.sdk"] == "true"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == "sdkUser"
            assert_priority(span, meta)

    def setup_login_sdk_success_basic(self):
        self.r_sdk_success = weblog.get(
            "/login?auth=basic&sdk_event=success&sdk_user=sdkUser",
            headers={"Authorization": self.BASIC_AUTH_USER_HEADER},
        )

    @irrelevant(
        context.library == "java",
        reason="Basic auth makes insecure protocol test fail due to dedup, fixed in the next tracer release",
    )
    def test_login_sdk_success_basic(self):
        assert self.r_sdk_success.status_code == 200
        for _, _, span in interfaces.library.get_spans(request=self.r_sdk_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "anonymization"
            assert meta["_dd.appsec.events.users.login.success.sdk"] == "true"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == "sdkUser"
            assert_priority(span, meta)

    def setup_login_sdk_failure_basic(self):
        self.r_sdk_failure = weblog.get(
            "/login?auth=basic&sdk_event=failure&sdk_user=sdkUser&sdk_user_exists=true",
            headers={"Authorization": "Basic aW52YWxpZFVzZXI6MTIzNA=="},
        )

    @irrelevant(
        context.library == "java",
        reason="Basic auth makes insecure protocol test fail due to dedup, fixed in the next tracer release",
    )
    def test_login_sdk_failure_basic(self):
        assert self.r_sdk_failure.status_code == 401
        for _, _, span in interfaces.library.get_spans(request=self.r_sdk_failure):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "anonymization"
            assert meta["_dd.appsec.events.users.login.failure.sdk"] == "true"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert meta["appsec.events.users.login.failure.usr.id"] == "sdkUser"
            assert meta["appsec.events.users.login.failure.usr.exists"] == "true"
            assert_priority(span, meta)

    def setup_login_sdk_failure_local(self):
        self.r_sdk_failure = weblog.post(
            "/login?auth=local&sdk_event=failure&sdk_user=sdkUser&sdk_user_exists=true",
            data={self.username_key: "invalidUser", self.password_key: self.PASSWORD},
        )

    def test_login_sdk_failure_local(self):
        assert self.r_sdk_failure.status_code == 401
        for _, _, span in interfaces.library.get_spans(request=self.r_sdk_failure):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "anonymization"
            assert meta["_dd.appsec.events.users.login.failure.sdk"] == "true"
            assert meta["appsec.events.users.login.failure.track"] == "true"
            assert meta["appsec.events.users.login.failure.usr.id"] == "sdkUser"
            assert meta["appsec.events.users.login.failure.usr.exists"] == "true"
            assert_priority(span, meta)

    def setup_login_success_headers(self):
        self.r_hdr_success = weblog.post(
            "/login?auth=local",
            data={self.username_key: self.USER, self.password_key: self.PASSWORD},
            headers=self.HEADERS,
        )

    def test_login_success_headers(self):
        # Validate that all relevant headers are included on user login success on extended mode

        def validate_login_success_headers(span):
            if span.get("parent_id") not in (0, None):
                return

            for header in self.HEADERS:
                assert f"http.request.headers.{header.lower()}" in span["meta"], f"Can't find {header} in span's meta"
            return True

        interfaces.library.validate_spans(self.r_hdr_success, validate_login_success_headers)

    def setup_login_failure_headers(self):
        self.r_hdr_failure = weblog.post(
            "/login?auth=local",
            data={self.username_key: "invalidUser", self.password_key: self.PASSWORD},
            headers=self.HEADERS,
        )

    def test_login_failure_headers(self):
        # Validate that all relevant headers are included on user login failure on extended mode

        def validate_login_failure_headers(span):
            if span.get("parent_id") not in (0, None):
                return

            for header in self.HEADERS:
                assert f"http.request.headers.{header.lower()}" in span["meta"], f"Can't find {header} in span's meta"
            return True

        interfaces.library.validate_spans(self.r_hdr_failure, validate_login_failure_headers)


def assert_priority(span, meta):
    MANUAL_KEEP_SAMPLING_PRIORITY = 2
    if span["metrics"].get("_sampling_priority_v1") != MANUAL_KEEP_SAMPLING_PRIORITY:
        assert "manual.keep" in meta, "manual.keep should be in meta when _sampling_priority_v1 is not MANUAL_KEEP"
        assert (
            meta["manual.keep"] == "true"
        ), 'meta.manual.keep should be "true" when _sampling_priority_v1 is not MANUAL_KEEP'


@rfc("https://docs.google.com/document/d/19VHLdJLVFwRb_JrE87fmlIM5CL5LdOBv4AmLxgdo9qI/edit")
@features.user_monitoring
@scenarios.appsec_auto_events_rc
class Test_V2_Login_Events_RC:
    USER = "test"
    PASSWORD = "1234"
    # ["disabled", "identification", "anonymization", "anonymization+disabled(conflict)", "anonymization"]
    PAYLOADS = [
        {
            "targets": "eyJzaWduZWQiOnsiX3R5cGUiOiJ0YXJnZXRzIiwiY3VzdG9tIjp7Im9wYXF1ZV9iYWNrZW5kX3N0YXRlIjoiZXlKbWIyOGlPaUFpWW1GeUluMD0ifSwiZXhwaXJlcyI6IjMwMDAtMDEtMDFUMDA6MDA6MDBaIiwic3BlY192ZXJzaW9uIjoiMS4wIiwidGFyZ2V0cyI6eyJkYXRhZG9nLzIvQVNNX0ZFQVRVUkVTL2F1dG8tdXNlci1pbnN0cnVtL2NvbmZpZyI6eyJjdXN0b20iOnsidiI6MX0sImhhc2hlcyI6eyJzaGEyNTYiOiJlZDRiNmZmNWRkMmQ3MWI5NjE0YjcxMzMwMTg4MjU2MmNmNGQ4ODk3YWRlMzIzYTZkMmQ5ZGViZDRhNzNhZDA0In0sImxlbmd0aCI6NTZ9fSwidmVyc2lvbiI6MX0sInNpZ25hdHVyZXMiOlt7ImtleWlkIjoiZWQ3NjcyYzlhMjRhYmRhNzg4NzJlZTMyZWU3MWM3Y2IxZDUyMzVlOGRiNGVjYmYxY2EyOGI5YzUwZWI3NWQ5ZSIsInNpZyI6IjIyZDhlOTE0ZWM1NmE0MmQ4MTE4MmE4Y2RkODQyMTI0OTIyMDhlZDllNjRjZjQ2Mjg1ZTIxY2NjMjdhY2NhZDRlZDc3N2Y5MDkwNGVlYmZiODhiNDQ2ZGUxMGNkMjk1YzNjZDJlNjM1NmY4MjMzNDk5MzM1OTQ4YTRkMDI1ZTBkIn1dfQ==",
            "target_files": [
                {
                    "path": "datadog/2/ASM_FEATURES/auto-user-instrum/config",
                    "raw": "ewogICJhdXRvX3VzZXJfaW5zdHJ1bSI6IHsKICAgICJtb2RlIjogImRpc2FibGVkIgogIH0KfQo=",
                }
            ],
            "client_configs": ["datadog/2/ASM_FEATURES/auto-user-instrum/config"],
        },
        {
            "targets": "eyJzaWduZWQiOnsiX3R5cGUiOiJ0YXJnZXRzIiwiY3VzdG9tIjp7Im9wYXF1ZV9iYWNrZW5kX3N0YXRlIjoiZXlKbWIyOGlPaUFpWW1GeUluMD0ifSwiZXhwaXJlcyI6IjMwMDAtMDEtMDFUMDA6MDA6MDBaIiwic3BlY192ZXJzaW9uIjoiMS4wIiwidGFyZ2V0cyI6eyJkYXRhZG9nLzIvQVNNX0ZFQVRVUkVTL2F1dG8tdXNlci1pbnN0cnVtL2NvbmZpZyI6eyJjdXN0b20iOnsidiI6Mn0sImhhc2hlcyI6eyJzaGEyNTYiOiIyZWY2ZDVjMGZhNTQ4NTY0YTRjNWI3NTBjZmRkMDhkOWE4ODk2MmNhZTZkY2M5NDk0MjM4OWMxZDkwOTNkMTBhIn0sImxlbmd0aCI6NjJ9fSwidmVyc2lvbiI6Mn0sInNpZ25hdHVyZXMiOlt7ImtleWlkIjoiZWQ3NjcyYzlhMjRhYmRhNzg4NzJlZTMyZWU3MWM3Y2IxZDUyMzVlOGRiNGVjYmYxY2EyOGI5YzUwZWI3NWQ5ZSIsInNpZyI6ImYzOTMxZDliODk4NWIzNTgxNjc1NWI4N2RjNmFmM2UxYzMzYWJmMjhjZDhkYzVmYWM2ZmMwMzgyZjNlMjUwOGU4ZmZmNzMxMDI2NWFhNDk3NjU2NjAyZDIxMTlhODFhNTViMjkwM2VkMjJlM2IzMzU0MmNhMWZiYmUxYWRhMjBhIn1dfQ==",
            "target_files": [
                {
                    "path": "datadog/2/ASM_FEATURES/auto-user-instrum/config",
                    "raw": "ewogICJhdXRvX3VzZXJfaW5zdHJ1bSI6IHsKICAgICJtb2RlIjogImlkZW50aWZpY2F0aW9uIgogIH0KfQo=",
                }
            ],
            "client_configs": ["datadog/2/ASM_FEATURES/auto-user-instrum/config"],
        },
        {
            "targets": "eyJzaWduZWQiOnsiX3R5cGUiOiJ0YXJnZXRzIiwiY3VzdG9tIjp7Im9wYXF1ZV9iYWNrZW5kX3N0YXRlIjoiZXlKbWIyOGlPaUFpWW1GeUluMD0ifSwiZXhwaXJlcyI6IjMwMDAtMDEtMDFUMDA6MDA6MDBaIiwic3BlY192ZXJzaW9uIjoiMS4wIiwidGFyZ2V0cyI6eyJkYXRhZG9nLzIvQVNNX0ZFQVRVUkVTL2F1dG8tdXNlci1pbnN0cnVtL2NvbmZpZyI6eyJjdXN0b20iOnsidiI6M30sImhhc2hlcyI6eyJzaGEyNTYiOiIwMjRiOGM4MmQxODBkZjc2NzMzNzVjYzYzZDdiYmRjMzRiNWE4YzE3NWQzNzE3ZGQwYjYyMzg2OTRhY2FiNWI3In0sImxlbmd0aCI6NjF9fSwidmVyc2lvbiI6M30sInNpZ25hdHVyZXMiOlt7ImtleWlkIjoiZWQ3NjcyYzlhMjRhYmRhNzg4NzJlZTMyZWU3MWM3Y2IxZDUyMzVlOGRiNGVjYmYxY2EyOGI5YzUwZWI3NWQ5ZSIsInNpZyI6IjZlN2FkNDY1MDBiOGU0MTlkZDEyOTQyMjRiMGMzODM0OTZkZjc5OTJhOTliNDkwYWY0MmU1YjRkOTdjZWYxNTI3ZmRjNTAxMGVmYmI2NmYyY2VjMjgyY2Y4NzU5YmFlZThmOWY0ZjA4OWJjODJjNDk3NDUzYjc3YmM4Y2RiYTBkIn1dfQ==",
            "target_files": [
                {
                    "path": "datadog/2/ASM_FEATURES/auto-user-instrum/config",
                    "raw": "ewogICJhdXRvX3VzZXJfaW5zdHJ1bSI6IHsKICAgICJtb2RlIjogImFub255bWl6YXRpb24iCiAgfQp9Cg==",
                }
            ],
            "client_configs": ["datadog/2/ASM_FEATURES/auto-user-instrum/config"],
        },
        {
            "targets": "eyJzaWduZWQiOnsiX3R5cGUiOiJ0YXJnZXRzIiwiY3VzdG9tIjp7Im9wYXF1ZV9iYWNrZW5kX3N0YXRlIjoiZXlKbWIyOGlPaUFpWW1GeUluMD0ifSwiZXhwaXJlcyI6IjMwMDAtMDEtMDFUMDA6MDA6MDBaIiwic3BlY192ZXJzaW9uIjoiMS4wIiwidGFyZ2V0cyI6eyJkYXRhZG9nLzIvQVNNX0ZFQVRVUkVTL2F1dG8tdXNlci1pbnN0cnVtLWNvbmZsaWN0L2NvbmZpZyI6eyJjdXN0b20iOnsidiI6Mn0sImhhc2hlcyI6eyJzaGEyNTYiOiJlZDRiNmZmNWRkMmQ3MWI5NjE0YjcxMzMwMTg4MjU2MmNmNGQ4ODk3YWRlMzIzYTZkMmQ5ZGViZDRhNzNhZDA0In0sImxlbmd0aCI6NTZ9LCJkYXRhZG9nLzIvQVNNX0ZFQVRVUkVTL2F1dG8tdXNlci1pbnN0cnVtL2NvbmZpZyI6eyJjdXN0b20iOnsidiI6M30sImhhc2hlcyI6eyJzaGEyNTYiOiIwMjRiOGM4MmQxODBkZjc2NzMzNzVjYzYzZDdiYmRjMzRiNWE4YzE3NWQzNzE3ZGQwYjYyMzg2OTRhY2FiNWI3In0sImxlbmd0aCI6NjF9fSwidmVyc2lvbiI6NH0sInNpZ25hdHVyZXMiOlt7ImtleWlkIjoiZWQ3NjcyYzlhMjRhYmRhNzg4NzJlZTMyZWU3MWM3Y2IxZDUyMzVlOGRiNGVjYmYxY2EyOGI5YzUwZWI3NWQ5ZSIsInNpZyI6IjY4ZDYxM2MxNDlmZDUxM2IzOTFhZWM4ZWJjOTNhZDg2NWViZjA5NDYxMWYzNjRmMmE5YjZjNTJmMjQyMTUyN2U5YjM5ZWZhYTk4N2JmZWViZmUyYTVmZDcxMmI1MTA4Mzk3YWEwODNhNzZkZGExMzUyM2U5M2EyZWJiYjdlZTAyIn1dfQ==",
            "target_files": [
                {
                    "path": "datadog/2/ASM_FEATURES/auto-user-instrum-conflict/config",
                    "raw": "ewogICJhdXRvX3VzZXJfaW5zdHJ1bSI6IHsKICAgICJtb2RlIjogImRpc2FibGVkIgogIH0KfQo=",
                }
            ],
            "client_configs": [
                "datadog/2/ASM_FEATURES/auto-user-instrum-conflict/config",
                "datadog/2/ASM_FEATURES/auto-user-instrum/config",
            ],
        },
        {
            "targets": "eyJzaWduZWQiOnsiX3R5cGUiOiJ0YXJnZXRzIiwiY3VzdG9tIjp7Im9wYXF1ZV9iYWNrZW5kX3N0YXRlIjoiZXlKbWIyOGlPaUFpWW1GeUluMD0ifSwiZXhwaXJlcyI6IjMwMDAtMDEtMDFUMDA6MDA6MDBaIiwic3BlY192ZXJzaW9uIjoiMS4wIiwidGFyZ2V0cyI6eyJkYXRhZG9nLzIvQVNNX0ZFQVRVUkVTL2F1dG8tdXNlci1pbnN0cnVtL2NvbmZpZyI6eyJjdXN0b20iOnsidiI6M30sImhhc2hlcyI6eyJzaGEyNTYiOiIwMjRiOGM4MmQxODBkZjc2NzMzNzVjYzYzZDdiYmRjMzRiNWE4YzE3NWQzNzE3ZGQwYjYyMzg2OTRhY2FiNWI3In0sImxlbmd0aCI6NjF9fSwidmVyc2lvbiI6NX0sInNpZ25hdHVyZXMiOlt7ImtleWlkIjoiZWQ3NjcyYzlhMjRhYmRhNzg4NzJlZTMyZWU3MWM3Y2IxZDUyMzVlOGRiNGVjYmYxY2EyOGI5YzUwZWI3NWQ5ZSIsInNpZyI6IjkzYmY3N2JmMmVjZTg3NzhhNjlkMWEyOTM3YzM5MTFhYjZiNzIxMDU0ZDNlNmNjMzJkMTA2YWIzOWVlM2I0ZDc5MTllNmZmNWU3NWYyN2U5Y2ViNWY3NTJiZjA2OGYwNjk4MjI3Yjg1MTdiNzBiOTdiMzdlMGI2M2QyMzU5ODAwIn1dfQ==",
            "client_configs": ["datadog/2/ASM_FEATURES/auto-user-instrum/config"],
        },
    ]

    @property
    def username_key(self):
        """ In Rails the parametesr are group by scope. In the case of the test the scope is user. The syntax to group parameters in a POST request is scope[parameter] """
        return "user[username]" if "rails" in context.weblog_variant else "username"

    @property
    def password_key(self):
        """ In Rails the parametesr are group by scope. In the case of the test the scope is user. The syntax to group parameters in a POST request is scope[parameter] """
        return "user[password]" if "rails" in context.weblog_variant else "password"

    def _send_rc_and_execute_request(self, rc_payload):
        config_states = rc.send_command(raw_payload=rc_payload)
        request = weblog.post(
            "/login?auth=local", data={self.username_key: self.USER, self.password_key: self.PASSWORD}
        )
        return {"config_states": config_states, "request": request}

    def _assert_response(self, test, validation):
        config_states, request = test["config_states"], test["request"]

        for config_state in config_states.values():
            assert config_state["apply_state"] == rc.ApplyState.ACKNOWLEDGED, config_state

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
        # after adding conflict (anonymization+disabled), fallback to local tracer value (identification)
        self._assert_response(self.tests[3], validate_iden)
        # after removing conflict, use the previous remote config value
        self._assert_response(self.tests[4], validate_anon)
