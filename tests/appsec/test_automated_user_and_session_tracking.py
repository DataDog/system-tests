# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2024 Datadog, Inc.

from utils import context
from utils import features
from utils import interfaces
from utils import remote_config as rc
from utils import rfc
from utils import scenarios
from utils import weblog

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


def login_data(context, user, password):
    """In Rails the parameters are group by scope. In the case of the test the scope is user.
   The syntax to group parameters in a POST request is scope[parameter]
   """
    username_key = "user[username]" if "rails" in context.weblog_variant else "username"
    password_key = "user[password]" if "rails" in context.weblog_variant else "password"
    return {username_key: user, password_key: password}


@rfc("https://docs.google.com/document/d/1RT38U6dTTcB-8muiYV4-aVDCsT_XrliyakjtAPyjUpw")
@features.user_monitoring
class Test_Automated_User_Tracking:
    def setup_user_tracking_auto(self):
        self.r_login = weblog.post("/login?auth=local", data=login_data(context, USER, PASSWORD))
        self.r_home = weblog.get("/", cookies=self.r_login.cookies,)

    def test_user_tracking_auto(self):
        assert self.r_login.status_code == 200

        assert self.r_home.status_code == 200
        for _, _, span in interfaces.library.get_spans(request=self.r_home):
            meta = span.get("meta", {})
            assert meta["usr.id"] == "social-security-id"
            assert meta["_dd.appsec.usr.id"] == "social-security-id"
            assert meta["_dd.appsec.user.collection_mode"] == "identification"

    def setup_user_tracking_sdk_overwrite(self):
        self.r_login = weblog.post(
            "/login?auth=local&sdk_event=success&sdk_user=sdkUser", data=login_data(context, USER, PASSWORD)
        )

    def test_user_tracking_sdk_overwrite(self):
        assert self.r_login.status_code == 200
        for _, _, span in interfaces.library.get_spans(request=self.r_login):
            meta = span.get("meta", {})
            assert meta["usr.id"] == "sdkUser"
            assert meta["_dd.appsec.usr.id"] == "social-security-id"
            assert meta["_dd.appsec.user.collection_mode"] == "sdk"


CONFIG_ENABLED = (
    "datadog/2/ASM_FEATURES/asm_features_activation/config",
    {"asm": {"enabled": True}},
)

BLOCK_USER = (
    "datadog/2/ASM_DD/rules/config",
    {
        "version": "2.1",
        "metadata": {"rules_version": "1.2.6"},
        "rules": [
            {
                "id": "block-users",
                "name": "Block User Addresses",
                "tags": {"type": "block_user", "category": "security_response"},
                "conditions": [
                    {
                        "parameters": {"inputs": [{"address": "usr.id"}], "data": "blocked_users"},
                        "operator": "exact_match",
                    }
                ],
                "transformers": [],
                "on_match": ["block"],
            }
        ],
        "rules_data": [
            {
                "id": "blocked_users",
                "type": "data_with_expiration",
                "data": [{"value": "social-security-id", "expiration": 0}, {"value": "sdkUser", "expiration": 0}],
            },
        ],
    },
)


@rfc("https://docs.google.com/document/d/1RT38U6dTTcB-8muiYV4-aVDCsT_XrliyakjtAPyjUpw")
@features.user_monitoring
@scenarios.appsec_runtime_activation
class Test_Automated_User_Blocking:
    def setup_user_blocking_auto(self):
        rc.rc_state.reset().apply()

        self.config_state_1 = rc.rc_state.set_config(*CONFIG_ENABLED).apply()
        self.r_login = weblog.post("/login?auth=local", data=login_data(context, USER, PASSWORD))

        self.config_state_2 = rc.rc_state.set_config(*BLOCK_USER).apply()
        self.r_home_blocked = weblog.get("/", cookies=self.r_login.cookies,)

    def test_user_blocking_auto(self):
        assert self.config_state_1[rc.RC_STATE] == rc.ApplyState.ACKNOWLEDGED
        assert self.r_login.status_code == 200

        assert self.config_state_2[rc.RC_STATE] == rc.ApplyState.ACKNOWLEDGED
        interfaces.library.assert_waf_attack(self.r_home_blocked, rule="block-users")
        assert self.r_home_blocked.status_code == 403

    def setup_user_blocking_sdk(self):
        rc.rc_state.reset().apply()

        self.config_state_1 = rc.rc_state.set_config(*CONFIG_ENABLED).apply()
        self.config_state_2 = rc.rc_state.set_config(*BLOCK_USER).apply()
        self.r_login = weblog.post("/login?auth=local", data=login_data(context, UUID_USER, PASSWORD))
        self.r_login_blocked = weblog.post(
            "/login?auth=local&sdk_event=success&sdk_user=sdkUser", data=login_data(context, UUID_USER, PASSWORD)
        )

    def test_user_blocking_sdk(self):
        assert self.config_state_1[rc.RC_STATE] == rc.ApplyState.ACKNOWLEDGED
        assert self.config_state_2[rc.RC_STATE] == rc.ApplyState.ACKNOWLEDGED

        assert self.r_login.status_code == 200

        interfaces.library.assert_waf_attack(self.r_login_blocked, rule="block-users")
        assert self.r_login_blocked.status_code == 403


BLOCK_SESSION = (
    "datadog/2/ASM_DD/rules/config",
    {
        "version": "2.1",
        "metadata": {"rules_version": "1.2.6"},
        "rules": [
            {
                "id": "block-sessions",
                "name": "Block Session Addresses",
                "tags": {"type": "block_user", "category": "security_response"},
                "conditions": [
                    {
                        "parameters": {"inputs": [{"address": "usr.session_id"}], "data": "blocked_sessions"},
                        "operator": "exact_match",
                    }
                ],
                "transformers": [],
                "on_match": ["block"],
            }
        ],
        "rules_data": [{"id": "blocked_sessions", "type": "data_with_expiration", "data": []},],
    },
)


@rfc("https://docs.google.com/document/d/1RT38U6dTTcB-8muiYV4-aVDCsT_XrliyakjtAPyjUpw")
@features.user_monitoring
@scenarios.appsec_runtime_activation
class Test_Automated_Session_Blocking:
    def setup_session_blocking(self):
        rc.rc_state.reset().apply()

        self.config_state_1 = rc.rc_state.set_config(*CONFIG_ENABLED).apply()
        self.r_create_session = weblog.get("/session/new")
        self.session_id = self.r_create_session.text

        BLOCK_SESSION[1]["rules_data"][0]["data"].append({"value": self.session_id, "expiration": 0})
        self.config_state_2 = rc.rc_state.set_config(*BLOCK_SESSION).apply()
        self.r_home_blocked = weblog.get("/", cookies=self.r_create_session.cookies,)

    def test_session_blocking(self):
        assert self.config_state_1[rc.RC_STATE] == rc.ApplyState.ACKNOWLEDGED
        assert self.r_create_session.status_code == 200

        assert self.config_state_2[rc.RC_STATE] == rc.ApplyState.ACKNOWLEDGED
        interfaces.library.assert_waf_attack(self.r_home_blocked, pattern=self.session_id, rule="block-sessions")
        assert self.r_home_blocked.status_code == 403
