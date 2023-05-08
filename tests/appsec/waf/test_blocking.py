import os.path
import re

import pytest

from utils import released, coverage, interfaces, bug, scenarios, weblog, rfc, missing_feature
from utils._context.core import context

if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


_CUR_DIR = os.path.dirname(os.path.abspath(__file__))

# Initial template version as found in dd-trace-java, with different indentation to v1.
BLOCK_TEMPLATE_HTML_V0 = open(os.path.join(_CUR_DIR, "blocked.v0.html"), "r").read()
BLOCK_TEMPLATE_HTML_V1 = open(os.path.join(_CUR_DIR, "blocked.v1.html"), "r").read()
BLOCK_TEMPLATE_HTML_MIN_V1 = open(os.path.join(_CUR_DIR, "blocked.v1.min.html"), "r").read()
BLOCK_TEMPLATE_HTML_MIN_V2 = open(os.path.join(_CUR_DIR, "blocked.v2.min.html"), "r").read()
# Prettified as found in dd-trace-go
BLOCK_TEMPLATE_JSON_V0 = open(os.path.join(_CUR_DIR, "blocked.v0.json"), "r").read()
BLOCK_TEMPLATE_JSON_V1 = open(os.path.join(_CUR_DIR, "blocked.v1.json"), "r").read()
BLOCK_TEMPLATE_JSON_MIN_V1 = open(os.path.join(_CUR_DIR, "blocked.v1.min.json"), "r").read()

BLOCK_TEMPLATE_HTML_ANY = {
    BLOCK_TEMPLATE_HTML_V0,
    BLOCK_TEMPLATE_HTML_V1,
    BLOCK_TEMPLATE_HTML_MIN_V1,
    BLOCK_TEMPLATE_HTML_MIN_V2,
}
BLOCK_TEMPLATE_JSON_ANY = {
    BLOCK_TEMPLATE_JSON_V0,
    BLOCK_TEMPLATE_JSON_V1,
    BLOCK_TEMPLATE_JSON_V1.rstrip(),
    BLOCK_TEMPLATE_JSON_MIN_V1,
}

HTML_CONTENT_TYPES = {"text/html", "text/html; charset=utf-8", "text/html;charset=utf-8"}
JSON_CONTENT_TYPES = {
    "application/json",
    "application/json; charset=utf-8",
    "application/json;charset=utf-8",
    # Python frameworks use text/json
    "text/json",
}


@released(
    dotnet="2.27.0",
    nodejs="?",
    php_appsec="0.7.0",
    python={"django-poc": "1.10", "flask-poc": "1.10", "*": "?"},
    ruby="?",
)
@released(
    java={
        "spring-boot": "0.112.0",
        "uds-spring-boot": "0.112.0",
        "sprint-boot-jetty": "0.112.0",
        "spring-boot-undertow": "0.112.0",
        "spring-boot-wildfly": "0.112.0",
        "spring-boot-openliberty": "1.3.0",
        "ratpack": "1.7.0",
        "jersey-grizzly2": "1.7.0",
        "resteasy-netty3": "1.7.0",
        "vertx3": "1.7.0",
        "*": "?",
    }
)
@released(golang="1.50.0-rc.1")
@missing_feature(context.weblog_variant == "spring-boot-native", reason="GraalVM. Tracing support only")
@missing_feature(context.weblog_variant == "spring-boot-3-native", reason="GraalVM. Tracing support only")
@coverage.basic
@scenarios.appsec_blocking
class Test_Blocking:
    """Blocking response is obtained when triggering a blocking rule, test the default blocking response"""

    def setup_no_accept(self):
        self.r_na = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    @bug(context.library < "java@0.115.0" and context.weblog_variant == "spring-boot-undertow", reason="npe")
    @bug(context.library < "java@0.115.0" and context.weblog_variant == "spring-boot-wildfly", reason="npe")
    @bug(context.weblog_variant == "gin", reason="Block message is prepended")
    @bug(context.library == "python", reason="Bug, minify and remove new line characters")
    def test_no_accept(self):
        """Blocking without an accept header"""
        assert self.r_na.status_code == 403
        assert self.r_na.headers.get("content-type", "") in JSON_CONTENT_TYPES
        assert self.r_na.text in BLOCK_TEMPLATE_JSON_ANY

    def setup_blocking_appsec_blocked_tag(self):
        self.r_abt = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1", "Accept": "*/*"})

    def test_blocking_appsec_blocked_tag(self):
        """Tag ddappsec.blocked is set when blocking"""
        assert self.r_abt.status_code == 403

        interfaces.library.assert_waf_attack(
            self.r_abt, pattern="Arachni/v", address="server.request.headers.no_cookies"
        )

        def validate_appsec_blocked(span):
            if span.get("type") != "web":
                return

            if span.get("parent_id") not in (0, None):  # do nothing if not root span
                return

            if "appsec.blocked" not in span["meta"]:
                raise Exception("Can't find appsec.blocked in span's tags")

            return True

        interfaces.library.validate_spans(self.r_abt, validator=validate_appsec_blocked)

    def setup_accept_all(self):
        self.r_aa = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1", "Accept": "*/*"})

    def test_accept_all(self):
        """Blocking with Accept: */*"""
        assert self.r_aa.status_code == 403
        assert self.r_aa.headers.get("content-type", "") in JSON_CONTENT_TYPES
        assert self.r_aa.text in BLOCK_TEMPLATE_JSON_ANY

    def setup_accept_partial_json(self):
        # */* should be ignored because there are more specific matches for text/html and application/json
        self.r_apj = weblog.get(
            "/waf/", headers={"User-Agent": "Arachni/v1", "Accept": "text/*;q=0.7, application/*;q=0.8, */*;q=0.9"}
        )

    @bug(context.weblog_variant == "gin", reason="Block message is prepended")
    def test_accept_partial_json(self):
        """Blocking with Accept: application/*"""
        assert self.r_apj.status_code == 403
        assert self.r_apj.headers.get("content-type", "") in JSON_CONTENT_TYPES
        assert self.r_apj.text in BLOCK_TEMPLATE_JSON_ANY

    def setup_accept_partial_html(self):
        self.r_aph = weblog.get(
            "/waf/", headers={"User-Agent": "Arachni/v1", "Accept": "text/*;q=0.8, application/*;q=0.7, */*;q=0.9"}
        )

    @missing_feature(context.library == "php", reason="Support for partial html not implemented")
    @missing_feature(context.library == "dotnet", reason="Support for partial html not implemented")
    @missing_feature(context.library == "golang", reason="Support for partial html not implemented")
    @missing_feature(context.library == "python", reason="Support for partial html not implemented")
    def test_accept_partial_html(self):
        """Blocking with Accept: text/*"""
        assert self.r_aph.status_code == 403
        assert self.r_aph.headers.get("content-type", "") in HTML_CONTENT_TYPES
        assert self.r_aph.text in BLOCK_TEMPLATE_HTML_ANY

    def setup_accept_full_json(self):
        self.r_afj = weblog.get(
            "/waf/",
            headers={
                "User-Agent": "Arachni/v1",
                "Accept": "text/*;q=0.8, application/*;q=0.7, application/json;q=0.85, */*;q=0.9",
            },
        )

    @bug(context.weblog_variant == "gin", reason="Block message is prepended")
    def test_accept_full_json(self):
        """Blocking with Accept: application/json"""
        assert self.r_afj.status_code == 403
        assert self.r_afj.headers.get("content-type", "") in JSON_CONTENT_TYPES
        assert self.r_afj.text in BLOCK_TEMPLATE_JSON_ANY

    def setup_accept_full_html(self):
        self.r_afh = weblog.get(
            "/waf/",
            headers={
                "User-Agent": "Arachni/v1",
                "Accept": "text/html;q=0.9, text/*;q=0.8, application/json;q=0.85, */*;q=0.9",
            },
        )

    @missing_feature(context.library == "php", reason="Support for quality not implemented")
    @missing_feature(context.library == "dotnet", reason="Support for quality not implemented")
    @bug(context.weblog_variant == "gin", reason="Block message is prepended")
    def test_accept_full_html(self):
        """Blocking with Accept: text/html"""
        assert self.r_afh.status_code == 403
        assert self.r_afh.headers.get("content-type", "") in HTML_CONTENT_TYPES
        assert self.r_afh.text in BLOCK_TEMPLATE_HTML_ANY

    def setup_json_template_v1(self):
        self.r_json_v1 = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1", "Accept": "application/json",},)

    @released(java="?", dotnet="?", golang="?", nodejs="?", php_appsec="?", python="?", ruby="?")
    def test_json_template_v1(self):
        """HTML block template is v1 minified"""
        assert self.r_json_v1.status_code == 403
        assert self.r_json_v1.headers.get("content-type", "") in HTML_CONTENT_TYPES
        assert self.r_json_v1.text == BLOCK_TEMPLATE_JSON_MIN_V1

    def setup_html_template_v2(self):
        self.r_html_v2 = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1", "Accept": "text/html",},)

    @released(java="?", dotnet="?", golang="?", nodejs="?", php_appsec="?", python="?", ruby="?")
    def test_html_template_v2(self):
        """HTML block template is v1 minified"""
        assert self.r_html_v2.status_code == 403
        assert self.r_html_v2.headers.get("content-type", "") in HTML_CONTENT_TYPES
        assert self.r_html_v2.text == BLOCK_TEMPLATE_HTML_MIN_V2


@rfc(
    "https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2705464728/Blocking#Custom-Blocking-Response-via-Remote-Config"
)
@released(java="1.11.0", dotnet="?", golang="?", nodejs="?", php_appsec="0.7.0", python="?", ruby="?")
@missing_feature(context.weblog_variant == "spring-boot-native", reason="GraalVM. Tracing support only")
@missing_feature(context.weblog_variant == "spring-boot-3-native", reason="GraalVM. Tracing support only")
@coverage.basic
@scenarios.appsec_blocking
class Test_CustomBlockingResponse:
    """Custom Blocking response"""

    def setup_custom_status_code(self):
        self.r_cst = weblog.get("/waf/", headers={"User-Agent": "Canary/v1"})

    def test_custom_status_code(self):
        """Block with a custom HTTP status code"""
        assert self.r_cst.status_code == 401

    def setup_custom_redirect(self):
        self.r_cr = weblog.get("/waf/", headers={"User-Agent": "Canary/v2"}, allow_redirects=False)

    def test_custom_redirect(self):
        """Block with an HTTP redirection"""
        assert self.r_cr.status_code == 301
        assert self.r_cr.headers.get("location", "") == "/you-have-been-blocked"
