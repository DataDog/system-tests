from utils import context, interfaces, scenarios, weblog, bug, features, missing_feature


@features.appsec_user_blocking
@scenarios.appsec_blocking_full_denylist
class Test_UserBlocking_FullDenylist:
    NOT_BLOCKED_USER = "regularUser"
    NUM_OF_BLOCKED_USERS = 2500

    def _remote_config_is_applied(self, data):
        if data["path"] == "/v0.7/config":
            if "config_states" in data.get("request", {}).get("content", {}).get("client", {}).get("state", {}):
                config_states = data["request"]["content"]["client"]["state"]["config_states"]

                for state in config_states:
                    if state["id"] == "ASM_DATA-third":
                        return True

        return False

    def setup_nonblocking_test(self):
        interfaces.library.wait_for_remote_config_request()
        interfaces.library.wait_for(self._remote_config_is_applied, timeout=30)

        self.r_nonblock = weblog.get("/users", params={"user": self.NOT_BLOCKED_USER})

    def test_nonblocking_test(self):
        def validate_nonblock_user(span):
            assert span["meta"]["usr.id"] == self.NOT_BLOCKED_USER
            return True

        assert self.r_nonblock.status_code == 200
        interfaces.library.validate_spans(self.r_nonblock, validator=validate_nonblock_user)
        interfaces.library.assert_no_appsec_event(self.r_nonblock)

    def setup_blocking_test(self):
        interfaces.library.wait_for_remote_config_request()
        interfaces.library.wait_for(self._remote_config_is_applied, timeout=30)

        self.r_blocked_requests = [
            weblog.get("/users", params={"user": 0}),
            weblog.get("/users", params={"user": 2499}),
        ]

    @bug(context.library < "ruby@1.12.1", reason="not setting the tags on the service entry span")
    @bug(
        context.library >= "java@1.22.0" and context.library < "java@1.35.0",
        reason="Failed on large expiration values, which are used in this test",
    )
    @bug(library="java", reason="Request blocked but appsec.blocked tag not set")
    @missing_feature(library="python")
    def test_blocking_test(self):
        """Test with a denylisted user"""
        for r in self.r_blocked_requests:
            assert r.status_code == 403
            interfaces.library.assert_waf_attack(r, rule="blk-001-002", address="usr.id")
            spans = [s for _, s in interfaces.library.get_root_spans(r)]
            assert len(spans) == 1
            span = spans[0]
            assert span["meta"]["appsec.event"] == "true"
            assert span["meta"]["appsec.blocked"] == "true"
            assert span["meta"]["http.status_code"] == "403"
