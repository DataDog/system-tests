# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

from utils import weblog, interfaces, context, missing_feature, released, scenarios, coverage, rfc, bug


@rfc("https://docs.google.com/document/d/1-trUpphvyZY7k5ldjhW-MgqWl0xOm7AMEQDJEAZ63_Q/edit#heading=h.8d3o7vtyu1y1")
@coverage.good
@released(cpp="?", golang="?", java="?", nodejs="4.4.0", dotnet="2.32.0", php="?", python="?", ruby="?")
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

    USER = "test"
    UUID_USER = "testuuid"
    PASSWORD = "1234"
    INVALID_USER = "invalidUser"

    BASIC_AUTH_USER_HEADER = "Basic dGVzdDoxMjM0"  # base64(test:1234)
    BASIC_AUTH_USER_UUID_HEADER = "Basic dGVzdHV1aWQ6MTIzNA=="  # base64(testuuid:1234)
    BASIC_AUTH_INVALID_USER_HEADER = "Basic aW52YWxpZFVzZXI6MTIzNA=="  # base64(invalidUser:1234)
    BASIC_AUTH_INVALID_PASSWORD_HEADER = "Basic dGVzdDoxMjM0NQ=="  # base64(test:12345)

    MANUAL_KEEP_SAMPLING_PRIORITY = 2

    def setup_login_pii_success(self):
        self.r_pii_success = [
            weblog.post("/login?auth=local", data={"username": self.USER, "password": self.PASSWORD}),
            weblog.get("/login?auth=basic", headers={"Authorization": self.BASIC_AUTH_USER_HEADER}),
        ]

    @bug(context.library == "nodejs", reason="usr.id present in meta")
    def test_login_pii_success(self):
        for r in self.r_pii_success:
            assert r.status_code == 200
            for _, _, span in interfaces.library.get_spans(request=r):
                meta = span.get("meta", {})
                assert "usr.id" not in meta
                assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "safe"
                assert meta["appsec.events.users.login.success.track"] == "true"
                self.assert_priority(span, meta)

    def setup_login_success(self):
        self.r_success = [
            weblog.post("/login?auth=local", data={"username": self.UUID_USER, "password": self.PASSWORD},),
            weblog.get("/login?auth=basic", headers={"Authorization": self.BASIC_AUTH_USER_UUID_HEADER}),
        ]

    def test_login_success(self):
        for r in self.r_success:
            assert r.status_code == 200
            for _, _, span in interfaces.library.get_spans(request=r):
                meta = span.get("meta", {})
                assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "safe"
                assert meta["appsec.events.users.login.success.track"] == "true"
                assert meta["usr.id"] == "591dc126-8431-4d0f-9509-b23318d3dce4"
                self.assert_priority(span, meta)

    def setup_login_wrong_user_failure(self):
        self.r_wrong_user_failure = [
            weblog.post("/login?auth=local", data={"username": self.INVALID_USER, "password": self.PASSWORD}),
            weblog.get("/login?auth=basic", headers={"Authorization": self.BASIC_AUTH_INVALID_USER_HEADER}),
        ]

    @bug(context.library == "nodejs", reason="usr.id present in meta")
    def test_login_wrong_user_failure(self):
        for r in self.r_wrong_user_failure:
            assert r.status_code == 401
            for _, _, span in interfaces.library.get_spans(request=r):
                meta = span.get("meta", {})
                if context.library != "nodejs":
                    # Currently in nodejs there is no way to check if the user exists upon authentication failure so
                    # this assertion is disabled for this library.
                    assert meta["appsec.events.users.login.failure.usr.exists"] == "false"

                assert "appsec.events.users.login.failure.usr.id" not in meta
                assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "safe"
                assert meta["appsec.events.users.login.failure.track"] == "true"
                self.assert_priority(span, meta)

    def setup_login_wrong_password_failure(self):
        self.r_wrong_user_failure = [
            weblog.post("/login?auth=local", data={"username": self.USER, "password": "12345"}),
            weblog.get("/login?auth=basic", headers={"Authorization": self.BASIC_AUTH_INVALID_PASSWORD_HEADER}),
        ]

    @bug(context.library == "nodejs", reason="usr.id present in meta")
    def test_login_wrong_password_failure(self):
        for r in self.r_wrong_user_failure:
            assert r.status_code == 401
            for _, _, span in interfaces.library.get_spans(request=r):
                meta = span.get("meta", {})
                if context.library != "nodejs":
                    # Currently in nodejs there is no way to check if the user exists upon authentication failure so
                    # this assertion is disabled for this library.
                    assert meta["appsec.events.users.login.failure.usr.exists"] == "true"

                assert "appsec.events.users.login.failure.usr.id" not in meta
                assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "safe"
                assert meta["appsec.events.users.login.failure.track"] == "true"
                self.assert_priority(span, meta)

    def setup_login_sdk_success(self):
        self.r_sdk_success = [
            weblog.post(
                "/login?auth=local&sdk_event=success&sdk_user=sdkUser",
                data={"username": self.USER, "password": self.PASSWORD},
            ),
            weblog.get(
                "/login?auth=basic&sdk_event=success&sdk_user=sdkUser",
                headers={"Authorization": self.BASIC_AUTH_USER_HEADER},
            ),
        ]

    def test_login_sdk_success(self):
        for r in self.r_sdk_success:
            assert r.status_code == 200
            for _, _, span in interfaces.library.get_spans(request=r):
                meta = span.get("meta", {})
                assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "safe"
                assert meta["_dd.appsec.events.users.login.success.sdk"] == "true"
                assert meta["appsec.events.users.login.success.track"] == "true"
                assert meta["usr.id"] == "sdkUser"
                self.assert_priority(span, meta)

    def setup_login_sdk_failure(self):
        self.r_sdk_failure = [
            weblog.post(
                "/login?auth=local&sdk_event=failure&sdk_user=sdkUser&sdk_user_exists=true",
                data={"username": self.INVALID_USER, "password": self.PASSWORD},
            ),
            weblog.get(
                "/login?auth=basic&sdk_event=failure&sdk_user=sdkUser&sdk_user_exists=true",
                headers={"Authorization": self.BASIC_AUTH_INVALID_USER_HEADER},
            ),
        ]

    def test_login_sdk_failure(self):
        for r in self.r_sdk_failure:
            assert r.status_code == 401
            for _, _, span in interfaces.library.get_spans(request=r):
                meta = span.get("meta", {})
                assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "safe"
                assert meta["_dd.appsec.events.users.login.failure.sdk"] == "true"
                assert meta["appsec.events.users.login.failure.track"] == "true"
                assert meta["appsec.events.users.login.failure.usr.id"] == "sdkUser"
                assert meta["appsec.events.users.login.failure.usr.exists"] == "true"
                self.assert_priority(span, meta)

    def assert_priority(self, span, meta):
        if span["metrics"].get("_sampling_priority_v1") != self.MANUAL_KEEP_SAMPLING_PRIORITY:
            assert "manual.keep" in meta, "manual.keep should be in meta when _sampling_priority_v1 is not MANUAL_KEEP"
            assert (
                meta["manual.keep"] == "true"
            ), 'meta.manual.keep should be "true" when _sampling_priority_v1 is not MANUAL_KEEP'


@rfc("https://docs.google.com/document/d/1-trUpphvyZY7k5ldjhW-MgqWl0xOm7AMEQDJEAZ63_Q/edit#heading=h.8d3o7vtyu1y1")
@coverage.good
@scenarios.appsec_auto_events_extended
@released(cpp="?", golang="?", java="?", nodejs="4.4.0", dotnet="?", php="?", python="?", ruby="?")
class Test_Login_Events_Extended:
    "Test login success/failure use cases"
    USER = "test"
    UUID_USER = "testuuid"
    PASSWORD = "1234"

    BASIC_AUTH_USER_HEADER = "Basic dGVzdDoxMjM0"  # base64(test:1234)
    BASIC_AUTH_USER_UUID_HEADER = "Basic dGVzdHV1aWQ6MTIzNA=="  # base64(testuuid:1234)

    def setup_login_success(self):
        self.r_success = [
            weblog.post("/login?auth=local", data={"username": self.USER, "password": self.PASSWORD}),
            weblog.get("/login?auth=basic", headers={"Authorization": self.BASIC_AUTH_USER_HEADER}),
        ]

    def test_login_success(self):
        for r in self.r_success:
            assert r.status_code == 200
            for _, _, span in interfaces.library.get_spans(request=r):
                meta = span.get("meta", {})
                assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "extended"
                assert meta["appsec.events.users.login.success.track"] == "true"
                assert meta["usr.id"] == "social-security-id"
                assert meta["usr.email"] == "testuser@ddog.com"
                assert meta["usr.username"] == "test"
                assert meta["usr.login"] == "test"
                assert meta["manual.keep"] == "true"

    def setup_login_wrong_user_failure(self):
        self.r_wrong_user_failure = [
            weblog.post("/login?auth=local", data={"username": "invalidUser", "password": self.PASSWORD}),
            weblog.get("/login?auth=basic", headers={"Authorization": "Basic aW52YWxpZFVzZXI6MTIzNA=="}),
        ]

    def test_login_wrong_user_failure(self):
        for r in self.r_wrong_user_failure:
            assert r.status_code == 401
            for _, _, span in interfaces.library.get_spans(request=r):
                meta = span.get("meta", {})
                if context.library != "nodejs":
                    # Currently in nodejs there is no way to check if the user exists upon authentication failure so
                    # this assertion is disabled for this library.
                    assert meta["appsec.events.users.login.failure.usr.exists"] == "false"

                assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "extended"
                assert meta["appsec.events.users.login.failure.track"] == "true"
                assert meta["appsec.events.users.login.failure.usr.id"] == "invalidUser"
                assert meta["manual.keep"] == "true"

    def setup_login_wrong_password_failure(self):
        self.r_wrong_user_failure = [
            weblog.post("/login?auth=local", data={"username": self.USER, "password": "12345"}),
            weblog.get("/login?auth=basic", headers={"Authorization": "Basic dGVzdDoxMjM0NQ=="}),
        ]

    def test_login_wrong_password_failure(self):
        for r in self.r_wrong_user_failure:
            assert r.status_code == 401
            for _, _, span in interfaces.library.get_spans(request=r):
                meta = span.get("meta", {})
                if context.library != "nodejs":
                    # Currently in nodejs there is no way to check if the user exists upon authentication failure so
                    # this assertion is disabled for this library.
                    assert meta["appsec.events.users.login.failure.usr.exists"] == "true"

                assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "extended"
                assert meta["appsec.events.users.login.failure.track"] == "true"
                assert meta["appsec.events.users.login.failure.usr.id"] == "test"
                assert meta["manual.keep"] == "true"

    def setup_login_sdk_success(self):
        self.r_sdk_success = [
            weblog.post(
                "/login?auth=local&sdk_event=success&sdk_user=sdkUser",
                data={"username": self.USER, "password": self.PASSWORD},
            ),
            weblog.get(
                "/login?auth=basic&sdk_event=success&sdk_user=sdkUser",
                headers={"Authorization": self.BASIC_AUTH_USER_HEADER},
            ),
        ]

    def test_login_sdk_success(self):
        for r in self.r_sdk_success:
            assert r.status_code == 200
            for _, _, span in interfaces.library.get_spans(request=r):
                meta = span.get("meta", {})
                assert meta["_dd.appsec.events.users.login.success.auto.mode"] == "extended"
                assert meta["_dd.appsec.events.users.login.success.sdk"] == "true"
                assert meta["appsec.events.users.login.success.track"] == "true"
                assert meta["usr.id"] == "sdkUser"
                assert meta["manual.keep"] == "true"

    def setup_login_sdk_failure(self):
        self.r_sdk_failure = [
            weblog.post(
                "/login?auth=local&sdk_event=failure&sdk_user=sdkUser&sdk_user_exists=true",
                data={"username": "invalidUser", "password": self.PASSWORD},
            ),
            weblog.get(
                "/login?auth=basic&sdk_event=failure&sdk_user=sdkUser&sdk_user_exists=true",
                headers={"Authorization": "Basic aW52YWxpZFVzZXI6MTIzNA=="},
            ),
        ]

    def test_login_sdk_failure(self):
        for r in self.r_sdk_failure:
            assert r.status_code == 401
            for _, _, span in interfaces.library.get_spans(request=r):
                meta = span.get("meta", {})
                assert meta["_dd.appsec.events.users.login.failure.auto.mode"] == "extended"
                assert meta["_dd.appsec.events.users.login.failure.sdk"] == "true"
                assert meta["appsec.events.users.login.failure.track"] == "true"
                assert meta["appsec.events.users.login.failure.usr.id"] == "sdkUser"
                assert meta["appsec.events.users.login.failure.usr.exists"] == "true"
                assert meta["manual.keep"] == "true"
