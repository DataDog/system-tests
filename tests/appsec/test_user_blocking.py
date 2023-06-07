import re

import pytest

from utils import released, coverage, interfaces, scenarios, weblog, irrelevant
from utils._context.core import context

if context.weblog_variant == "akka-http":
    pytestmark = pytest.mark.skip("missing feature: No AppSec support")

_is_spring_native_weblog = re.fullmatch(r"spring-.+native", context.weblog_variant) is not None


@released(
    cpp="?",
    dotnet="2.30.0",
    golang="1.48.0",
    java="1.11.0",
    nodejs="3.15.0",
    php="0.85.0",
    php_appsec="0.7.0",
    python={"django-poc": "1.10", "flask-poc": "1.10", "*": "?"},
    ruby="?",
)
@irrelevant(_is_spring_native_weblog, reason="GraalVM. Tracing support only")
@coverage.basic
@scenarios.appsec_blocking
class Test_UserBlocking:
    def setup_nonblocking_test(self):
        self.r_nonblock = weblog.get("/users", params={"user": "regularUser"})

    def setup_blocking_test(self):
        self.r_block = weblog.get("/users", params={"user": "blockedUser"})

    def test_nonblocking_test(self):
        def validate_nonblock_user(span):
            if "usr.id" not in span["meta"]:
                return

            assert span["meta"]["usr.id"] == "regularUser"
            return True

        assert self.r_nonblock.status_code == 200
        interfaces.library.validate_spans(self.r_nonblock, validator=validate_nonblock_user)
        interfaces.library.assert_no_appsec_event(self.r_nonblock)

    def test_blocking_test(self):
        """Test with a denylisted user"""

        def validate_blocking_test(span):
            """Check all fields are present in meta"""
            if "usr.id" not in span["meta"]:
                return

            assert span["meta"]["usr.id"] == "blockedUser"
            assert span["meta"]["appsec.event"] == "true"
            assert span["meta"]["appsec.blocked"] == "true"
            assert span["meta"]["http.status_code"] == "403"
            return True

        assert self.r_block.status_code == 403
        interfaces.library.assert_waf_attack(self.r_block, rule="block-users", address="usr.id")
        interfaces.library.validate_spans(self.r_block, validator=validate_blocking_test)

        if context.library == "java":
            # we should also see a span with the blocking exception
            # this may or may not be the root span
            def validate_error_span(span):
                if "error.message" not in span["meta"]:
                    return

                assert "Blocking user with id 'blockedUser'" in span["meta"]["error.message"]

                return True

            interfaces.library.validate_spans(self.r_block, validator=validate_error_span)
