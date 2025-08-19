from utils import context, interfaces, weblog, bug, features

from .utils import BaseFullDenyListTest
from utils._context._scenarios.dynamic import dynamic_scenario


@features.appsec_user_blocking
@dynamic_scenario(mandatory={"DD_APPSEC_RULES": "None"})
class Test_UserBlocking_FullDenylist(BaseFullDenyListTest):
    NOT_BLOCKED_USER = "regularUser"
    NUM_OF_BLOCKED_USERS = 2500

    def setup_nonblocking_test(self):
        self.setup_scenario()

        self.r_nonblock = weblog.get("/users", params={"user": self.NOT_BLOCKED_USER})

    def test_nonblocking_test(self):
        def validate_nonblock_user(span):
            assert span["meta"]["usr.id"] == self.NOT_BLOCKED_USER
            return True

        assert self.r_nonblock.status_code == 200
        interfaces.library.validate_spans(self.r_nonblock, validator=validate_nonblock_user)
        interfaces.library.assert_no_appsec_event(self.r_nonblock)

    def setup_blocking_test(self):
        self.setup_scenario()

        self.r_blocked_requests = [
            weblog.get("/users", params={"user": 0}),
            weblog.get("/users", params={"user": self.NUM_OF_BLOCKED_USERS - 1}),
        ]

    @bug(context.library < "ruby@1.12.1", reason="APMRP-360")
    @bug(context.library >= "java@1.22.0" and context.library < "java@1.35.0", reason="APMRP-360")
    @bug(library="java", weblog_variant="spring-boot-payara", reason="APPSEC-56006")
    @bug(context.library < "ruby@2.11.0-dev", reason="APMRP-56691")
    def test_blocking_test(self):
        """Test with a denylisted user"""

        self.assert_protocol_is_respected()

        for r in self.r_blocked_requests:
            assert r.status_code == 403
            interfaces.library.assert_waf_attack(r, rule="blk-001-002", address="usr.id")
            span = interfaces.library.get_root_span(r)
            assert span["meta"]["appsec.event"] == "true"
            assert span["meta"]["appsec.blocked"] == "true"
            assert span["meta"]["http.status_code"] == "403"
