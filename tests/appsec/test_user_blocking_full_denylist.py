from utils import context, interfaces, scenarios, weblog, bug, features, missing_feature

from .utils import BaseFullDenyListTest


@features.appsec_user_blocking
@scenarios.appsec_blocking_full_denylist
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

    @bug(context.library < "ruby@1.12.1", reason="not setting the tags on the service entry span")
    @bug(
        context.library >= "java@1.22.0" and context.library < "java@1.35.0",
        reason="Failed on large expiration values, which are used in this test",
    )
    @bug(library="java", reason="Request blocked but appsec.blocked tag not set")
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
