from utils import context, released, coverage, interfaces, scenarios, weblog, bug, irrelevant, missing_feature


@released(
    cpp="?",
    dotnet="2.30.0",
    golang="1.48.0",
    java={
        "spring-boot": "0.110.0",
        "sprint-boot-jetty": "0.111.0",
        "spring-boot-undertow": "0.111.0",
        "spring-boot-openliberty": "0.115.0",
        "ratpack": "1.7.0",
        "jersey-grizzly2": "1.7.0",
        "resteasy-netty3": "1.7.0",
        "vertx3": "1.7.0",
        "*": "?",
    },
    nodejs="3.15.0",
    php="0.86.3",
    php_appsec="0.7.2",
    python={"django-poc": "1.10", "flask-poc": "1.10", "*": "?"},
    ruby="?",
)
@missing_feature(library="java", reason="/users endpoint is not implemented on java weblog")
@coverage.basic
@scenarios.appsec_blocking_full_denylist
class Test_UserBlocking_FullDenylist:
    NOT_BLOCKED_USER = "regularUser"
    remote_config_is_sent = False
    NUM_OF_BLOCKED_USERS = 2500

    def _remote_config_asm_payload(self, data):
        if data["path"] == "/v0.7/config":
            if "client_configs" in data.get("response", {}).get("content", {}):
                self.remote_config_is_sent = True
                return True

        return False

    def _remote_config_is_applied(self, data):
        if data["path"] == "/v0.7/config" and self.remote_config_is_sent:
            if "config_states" in data.get("request", {}).get("content", {}).get("client", {}).get("state", {}):
                config_states = data["request"]["content"]["client"]["state"]["config_states"]

                for state in config_states:
                    if state["id"] == "ASM_DATA-third":
                        return True

        return False

    def setup_nonblocking_test(self):
        interfaces.library.wait_for(self._remote_config_asm_payload, timeout=30)
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
        interfaces.library.wait_for(self._remote_config_asm_payload, timeout=30)
        interfaces.library.wait_for(self._remote_config_is_applied, timeout=30)

        self.r_blocked_requests = [weblog.get("/users", params={"user": i}) for i in range(self.NUM_OF_BLOCKED_USERS)]

    def test_blocking_test(self):
        """Test with a denylisted user"""

        def validate_blocking_test(span):
            """Check all fields are present in meta"""
            assert span["meta"]["appsec.event"] == "true"
            assert span["meta"]["appsec.blocked"] == "true"
            assert span["meta"]["http.status_code"] == "403"
            return True

        for r in self.r_blocked_requests:
            assert r.status_code == 403
            interfaces.library.assert_waf_attack(r, rule="blk-001-002", address="usr.id")
            interfaces.library.validate_spans(r, validator=validate_blocking_test)
