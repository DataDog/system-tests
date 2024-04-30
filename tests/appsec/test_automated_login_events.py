# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

from utils import weblog, interfaces, context, missing_feature, scenarios, rfc, bug, features


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
        "User-Agent": "Arachni/v1",  # "Benign User Agent 1.0",
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

            if context.library == "dotnet":
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
    def test_login_success_basic(self):
        assert self.r_success.status_code == 200
        for _, _, span in interfaces.library.get_spans(request=self.r_success):
            meta = span.get("meta", {})
            assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "extended"
            assert meta["appsec.events.users.login.success.track"] == "true"
            assert meta["usr.id"] == "social-security-id"
            assert meta["usr.email"] == "testuser@ddog.com"

            if context.library == "dotnet":
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

    # @missing_feature(library="dotnet")
    # @missing_feature(library="golang", reason="certain XFF headers aren't collected")
    # @missing_feature(library="java")
    # @missing_feature(library="nodejs")
    # @missing_feature(library="python")
    # @missing_feature(library="php")
    # @missing_feature(library="ruby")
    def test_login_success_headers(self):
        # Validate that all relevant headers are included on user login success on extended mode

        def validate_login_success_headers(span):
            for header, _ in self.HEADERS.items():
                assert f"http.request.headers.{header.lower()}" in span["meta"], f"Can't find {header} in span's meta"
            return True

        interfaces.library.validate_spans(self.r_hdr_success, validate_login_success_headers)

    def setup_login_failure_headers(self):
        self.r_hdr_failure = weblog.post(
            "/login?auth=local",
            data={self.username_key: "invalidUser", self.password_key: self.PASSWORD},
            headers=self.HEADERS,
        )

    # @missing_feature(library="dotnet")
    # @missing_feature(library="golang", reason="certain XFF headers aren't collected")
    # @missing_feature(library="java")
    # @missing_feature(library="nodejs")
    # @missing_feature(library="python")
    # @missing_feature(library="php")
    # @missing_feature(library="ruby")
    def test_login_failure_headers(self):
        # Validate that all relevant headers are included on user login failure on extended mode

        def validate_login_failure_headers(span):
            for header, _ in self.HEADERS.items():
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
