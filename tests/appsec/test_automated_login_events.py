# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

from utils import weblog, interfaces, context, missing_feature, released, scenarios

@released(cpp="?", golang="?", java="?", nodejs="?", dotnet="5.0.0-pre" php="?", ruby="?")
class Login_Events:
    "Test login success/failure use cases"
    VALID_USER = "test"
    VALID_USER_UUID = "591dc126-8431-4d0f-9509-b23318d3dce4"

    def setup_login_pii_sucess(self):
        self.requests = [
            weblog.post("/login", params={"auth": "local"}, data={"username": "test", "password": "1234"}),
            weblog.get("/login", params={"auth": "basic"}, headers={"Authorization": "Basic dGVzdDoxMjM0"})
        ]

    def test_login_pii_success(self):
        for r in self.requests:
            assert r.status_code == 200
            for _, _, span in interfaces.library.get_spans(request=r):
                meta = span.get("meta", {})
                assert meta["appsec.events.event.track"] == "true"
                assert meta["_dd.appsec.events.event.auto.mode"] == "safe"
                assert meta["appsec.events.users.login.success.track"] == "true"
                assert meta["appsec.events.users.login.success.usr.id"] == ""
                assert meta["manual.keep"] == "true"


    def setup_login_sucess(self):
        self.requests = [
            weblog.post("/login", params={"auth": "local"},
                        data={"username": "591dc126-8431-4d0f-9509-b23318d3dce4", "password": "1234"}),
            weblog.get("/login", params={"auth": "basic"}, headers={"Authorization": "Basic dGVzdDoxMjM0"})
        ]

    def test_login_success(self):
        for r in self.requests:
            assert r.status_code == 200
            for _, _, span in interfaces.library.get_spans(request=r):
                meta = span.get("meta", {})
                assert meta["appsec.events.event.track"] == "true"
                assert meta["_dd.appsec.events.event.auto.mode"] == "safe"
                assert meta["appsec.events.users.login.success.track"] == "true"
                assert meta["appsec.events.users.login.success.usr.id"] == ""
                assert meta["manual.keep"] == "true"


    def setup_login_wrong_user_failure(self):
        self.requests = [
            weblog.post("/login", params={"auth": "local"}, data={"username": "invalidUser", "password": "1234"}),
            weblog.get("/login", params={"auth": "basic"}, headers={"Authorization": "Basic dGVzdDoxMjM1"})
        ]

    def test_login_wrong_user_failure(self):
        for r in self.requests:
            assert r.status_code == 200
            for _, _, span in interfaces.library.get_spans(request=r):
                meta = span.get("meta", {})
                assert meta["appsec.events.event.track"] == "true"
                assert meta["_dd.appsec.events.event.auto.mode"] == "safe"
                assert meta["appsec.events.users.login.failure.track"] == "true"
                assert meta["appsec.events.users.login.failure.usr.id"] == ""
                assert meta["manual.keep"] == "true"
