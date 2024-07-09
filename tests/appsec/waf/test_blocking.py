import os.path

from utils import interfaces, bug, scenarios, weblog, rfc, missing_feature, flaky, features
from utils._context.core import context


_CUR_DIR = os.path.dirname(os.path.abspath(__file__))

BLOCK_TEMPLATE_HTML_V0_JAVA = open(os.path.join(_CUR_DIR, "blocked.v0.java.html"), "r").read()
BLOCK_TEMPLATE_HTML_V0_PYTHON = open(os.path.join(_CUR_DIR, "blocked.v0.python.html"), "r").read()
BLOCK_TEMPLATE_HTML_V1 = open(os.path.join(_CUR_DIR, "blocked.v1.html"), "r").read()
BLOCK_TEMPLATE_HTML_MIN_V1 = open(os.path.join(_CUR_DIR, "blocked.v1.min.html"), "r").read()
BLOCK_TEMPLATE_HTML_MIN_V2 = open(os.path.join(_CUR_DIR, "blocked.v2.min.html"), "r").read()

BLOCK_TEMPLATE_JSON_V0_GO = open(os.path.join(_CUR_DIR, "blocked.v0.go.json"), "r").read()
BLOCK_TEMPLATE_JSON_V0_PYTHON = open(os.path.join(_CUR_DIR, "blocked.v0.python.json"), "r").read()
BLOCK_TEMPLATE_JSON_V1 = open(os.path.join(_CUR_DIR, "blocked.v1.json"), "r").read()
BLOCK_TEMPLATE_JSON_MIN_V1 = open(os.path.join(_CUR_DIR, "blocked.v1.min.json"), "r").read()

BLOCK_TEMPLATE_HTML_ANY = {
    BLOCK_TEMPLATE_HTML_V0_JAVA,
    BLOCK_TEMPLATE_HTML_V0_PYTHON,
    BLOCK_TEMPLATE_HTML_V1,
    BLOCK_TEMPLATE_HTML_MIN_V1,
    BLOCK_TEMPLATE_HTML_MIN_V2,
}
BLOCK_TEMPLATE_JSON_ANY = {
    BLOCK_TEMPLATE_JSON_V0_GO,
    BLOCK_TEMPLATE_JSON_V0_PYTHON,
    BLOCK_TEMPLATE_JSON_V1,
    # No trailing new line in dotnet
    BLOCK_TEMPLATE_JSON_V1.rstrip(),
    BLOCK_TEMPLATE_JSON_MIN_V1,
    BLOCK_TEMPLATE_JSON_MIN_V1.rstrip(),
}

HTML_CONTENT_TYPES = {"text/html", "text/html; charset=utf-8", "text/html;charset=utf-8"}
JSON_CONTENT_TYPES = {
    "application/json",
    "application/json; charset=utf-8",
    "application/json;charset=utf-8",
    # Python frameworks use text/json
    "text/json",
}


@scenarios.appsec_blocking
@features.appsec_blocking_action
class Test_Blocking:
    """Blocking response is obtained when triggering a blocking rule, test the default blocking response"""

    def setup_no_accept(self):
        self.r_na = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    @bug(context.library < "java@0.115.0" and context.weblog_variant == "spring-boot-undertow", reason="npe")
    @bug(context.library < "java@0.115.0" and context.weblog_variant == "spring-boot-wildfly", reason="npe")
    @bug(context.library < "python@1.16.1", reason="Bug, minify and remove new line characters")
    @bug(context.library < "ruby@1.12.1", reason="wrong default content-type")
    def test_no_accept(self):
        """Blocking without an accept header"""
        assert self.r_na.status_code == 403
        assert self.r_na.headers.get("content-type", "") in JSON_CONTENT_TYPES
        assert self.r_na.text in BLOCK_TEMPLATE_JSON_ANY

    def setup_blocking_appsec_blocked_tag(self):
        self.r_abt = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1", "Accept": "*/*"})

    @flaky(context.library >= "java@1.19.0", reason="APPSEC-10798")
    def test_blocking_appsec_blocked_tag(self):
        """Tag appsec.blocked is set when blocking"""
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
                raise ValueError("Can't find appsec.blocked in span's tags")

            return True

        interfaces.library.validate_spans(self.r_abt, validator=validate_appsec_blocked)

    def setup_accept_all(self):
        self.r_aa = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1", "Accept": "*/*"})

    @bug(context.library < "ruby@1.12.1", reason="wrong default content-type")
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

    @bug(context.library < "ruby@1.12.1", reason="wrong default content-type")
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
    @missing_feature(context.library == "nodejs", reason="Support for partial html not implemented")
    @missing_feature(context.library == "python", reason="Support for partial html not implemented")
    @missing_feature(context.library == "ruby", reason="Support for partial html not implemented")
    def test_accept_partial_html(self):
        """Blocking with Accept: text/*"""
        assert self.r_aph.status_code == 403
        assert self.r_aph.headers.get("content-type", "").lower() in HTML_CONTENT_TYPES
        assert self.r_aph.text in BLOCK_TEMPLATE_HTML_ANY

    def setup_accept_full_json(self):
        self.r_afj = weblog.get(
            "/waf/",
            headers={
                "User-Agent": "Arachni/v1",
                "Accept": "text/*;q=0.8, application/*;q=0.7, application/json;q=0.85, */*;q=0.9",
            },
        )

    @bug(context.library < "ruby@1.12.1", reason="wrong default content-type")
    def test_accept_full_json(self):
        """Blocking with Accept: application/json"""
        assert self.r_afj.status_code == 403
        assert self.r_afj.headers.get("content-type", "").lower() in JSON_CONTENT_TYPES
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
    @missing_feature(context.library == "nodejs", reason="Support for quality not implemented")
    @missing_feature(context.library == "ruby", reason="Support for quality not implemented")
    def test_accept_full_html(self):
        """Blocking with Accept: text/html"""
        assert self.r_afh.status_code == 403
        assert self.r_afh.headers.get("content-type", "").lower() in HTML_CONTENT_TYPES
        assert self.r_afh.text in BLOCK_TEMPLATE_HTML_ANY

    def setup_json_template_v1(self):
        self.r_json_v1 = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1", "Accept": "application/json",},)

    @missing_feature(context.library < "java@1.14.0")
    @missing_feature(context.library < "nodejs@4.1.0")
    @missing_feature(context.library < "golang@1.52.0")
    @missing_feature(library="dotnet")
    @missing_feature(library="php")
    @missing_feature(library="ruby")
    def test_json_template_v1(self):
        """HTML block template is v1 minified"""
        assert self.r_json_v1.status_code == 403
        assert self.r_json_v1.headers.get("content-type", "").lower() in JSON_CONTENT_TYPES
        assert self.r_json_v1.text.rstrip() == BLOCK_TEMPLATE_JSON_MIN_V1.rstrip()

    def setup_html_template_v2(self):
        self.r_html_v2 = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1", "Accept": "text/html",},)

    @missing_feature(context.library < "java@1.14.0")
    @missing_feature(context.library < "nodejs@4.1.0")
    @missing_feature(context.library < "golang@1.52.0")
    @missing_feature(library="dotnet")
    @missing_feature(library="php")
    @missing_feature(library="ruby")
    def test_html_template_v2(self):
        """HTML block template is v2 minified"""
        assert self.r_html_v2.status_code == 403
        assert self.r_html_v2.headers.get("content-type", "").lower() in HTML_CONTENT_TYPES
        assert self.r_html_v2.text == BLOCK_TEMPLATE_HTML_MIN_V2


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2705464728/Blocking#Stripping-response-headers")
@scenarios.appsec_blocking
@features.appsec_blocking_action
class Test_Blocking_strip_response_headers:
    def setup_strip_response_headers(self):
        self.r_srh = weblog.get(f"/tag_value/anything/200?x-secret-header=123&content-language=krypton")

    def test_strip_response_headers(self):
        """Test if headers are stripped from the blocking response"""
        assert self.r_srh.status_code == 403
        interfaces.library.assert_waf_attack(self.r_srh, rule="tst-037-009")
        # x-secret-header is set by the app so is should be not be present in the response
        assert "x-secret-header" not in self.r_srh.headers
        # content-length is set by the blocking response so it should be present
        assert "content-length" in self.r_srh.headers


@rfc("https://docs.google.com/document/d/1a_-isT9v_LiiGshzQZtzPzCK_CxMtMIil_2fOq9Z1RE/edit")
@scenarios.appsec_blocking
@features.appsec_blocking_action
@bug(context.library >= "java@1.20.0" and context.weblog_variant == "spring-boot-openliberty")
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

    def setup_custom_redirect_wrong_status_code(self):
        self.r_cr = weblog.get("/waf/", headers={"User-Agent": "Canary/v3"}, allow_redirects=False)

    @bug(
        context.library == "java" and context.weblog_variant not in ("akka-http", "play"),
        reason="Do not check the configured redirect status code",
    )
    def test_custom_redirect_wrong_status_code(self):
        """Block with an HTTP redirection but default to 303 status code, because the configured status code is not a valid redirect status code"""
        assert self.r_cr.status_code == 303
        assert self.r_cr.headers.get("location", "") == "/you-have-been-blocked"

    def setup_custom_redirect_missing_location(self):
        self.r_cr = weblog.get("/waf/", headers={"User-Agent": "Canary/v4"}, allow_redirects=False)

    @bug(context.library == "java", reason="Do not check the configured redirect location value")
    def test_custom_redirect_missing_location(self):
        """Block with an default page because location parameter is missing from redirect request configuration"""
        assert self.r_cr.status_code == 403
        assert self.r_cr.text in BLOCK_TEMPLATE_JSON_ANY
