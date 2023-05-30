from utils import released, coverage, interfaces, scenarios, weblog


@released(
    cpp="?",
    dotnet="2.30.0",
    golang="1.48.0",
    java="?",
    nodejs="3.15.0",
    php="0.85.0",
    php_appsec="0.7.0",
    python={"django-poc": "1.10", "flask-poc": "1.10", "*": "?"},
    ruby="?",
)
@coverage.basic
@scenarios.appsec_blocking
class Test_UserBlocking:
    def setup_nonblocking_test(self):
        self.r_nonblock = weblog.get("/users", params={"user": "regularUser"})

    def setup_blocking_test(self):
        self.r_block = weblog.get("/users", params={"user": "blockedUser"})

    def test_nonblocking_test(self):
        def validate_nonblock_user(span):
            assert span["meta"]["usr.id"] == "regularUser"
            return True

        assert self.r_nonblock.status_code == 200
        interfaces.library.validate_spans(self.r_nonblock, validator=validate_nonblock_user)
        interfaces.library.assert_no_appsec_event(self.r_nonblock)

    def test_blocking_test(self):
        """Test with a denylisted user"""

        def validate_blocking_test(span):
            """Check all fields are present in meta"""
            assert span["meta"]["usr.id"] == "blockedUser"
            assert span["meta"]["appsec.event"] == "true"
            assert span["meta"]["appsec.blocked"] == "true"
            assert span["meta"]["http.status_code"] == "403"
            return True

        assert self.r_block.status_code == 403
        interfaces.library.assert_waf_attack(self.r_block, rule="block-users", address="usr.id")
        interfaces.library.validate_spans(self.r_block, validator=validate_blocking_test)
