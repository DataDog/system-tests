from pathlib import Path

from utils import interfaces, bug, scenarios, weblog, rfc, missing_feature, flaky, features
from utils._context.core import context
from .test_blocking_security_response_id import (
    is_valid_uuid4,
    extract_security_response_id_from_json,
    extract_security_response_id_from_html,
)


BLOCK_TEMPLATE_JSON_MIN_V1 = "blocked.v1.min.json"
BLOCK_TEMPLATE_HTML_MIN_V2 = "blocked.v2.min.html"
BLOCK_TEMPLATE_JSON_MIN_V3 = "blocked.v3.min.json"
BLOCK_TEMPLATE_HTML_MIN_V3 = "blocked.v3.min.html"


def _read_file(file_path: str) -> str:
    with Path(__file__).resolve().parent.joinpath(file_path).open() as file:
        return file.read()


def _is_valid_json_v3_template(body: str) -> bool:
    """Check if body matches v3 JSON template with valid dynamic security_response_id

    RFC-1070: Uses the actual security_response_id from the response for validation
    """
    # Extract and validate security_response_id from actual response
    security_response_id = extract_security_response_id_from_json(body)
    if security_response_id is None or not is_valid_uuid4(security_response_id):
        return False

    # Build expected response by injecting the actual security_response_id into the template
    v3_template = _read_file(BLOCK_TEMPLATE_JSON_MIN_V3).rstrip()
    expected_response = v3_template.replace("00000000-0000-4000-8000-000000000000", security_response_id)

    return body.rstrip() == expected_response


def _is_valid_html_v3_template(body: str) -> bool:
    """Check if body matches v3 HTML template with valid dynamic security_response_id

    RFC-1070: Uses the actual security_response_id from the response for validation
    """
    # Extract and validate security_response_id from actual response
    security_response_id = extract_security_response_id_from_html(body)
    if security_response_id is None or not is_valid_uuid4(security_response_id):
        return False

    # Build expected response by injecting the actual security_response_id into the template
    v3_template = _read_file(BLOCK_TEMPLATE_HTML_MIN_V3).rstrip()
    expected_response = v3_template.replace("00000000-0000-4000-8000-000000000000", security_response_id)

    return body.rstrip() == expected_response


def assert_valid_html_blocked_template(body: str) -> None:
    """Returns true if body is a valid HTML response on a blocked requests"""

    valid_templates = {
        _read_file("blocked.v0.java.html"),
        _read_file("blocked.v0.python.html"),
        _read_file("blocked.v1.html"),
        _read_file("blocked.v1.min.html"),
        _read_file(BLOCK_TEMPLATE_HTML_MIN_V2),
    }

    # Check for v3 template with dynamic security_response_id
    assert body in valid_templates or _is_valid_html_v3_template(body)


def assert_valid_json_blocked_template(body: str) -> None:
    """Returns true if body is a valid JSON response on a blocked requests"""

    valid_templates = {
        _read_file("blocked.v0.go.json"),
        _read_file("blocked.v0.python.json"),
        _read_file("blocked.v1.json"),
        _read_file("blocked.v1.json").rstrip(),  # No trailing new line in dotnet
        _read_file(BLOCK_TEMPLATE_JSON_MIN_V1),
        _read_file(BLOCK_TEMPLATE_JSON_MIN_V1).rstrip(),
    }

    # Check for v3 template with dynamic security_response_id
    assert body in valid_templates or _is_valid_json_v3_template(body)


HTML_CONTENT_TYPES = {"text/html", "text/html; charset=utf-8", "text/html;charset=utf-8"}
JSON_CONTENT_TYPES = {
    "application/json",
    "application/json; charset=utf-8",
    "application/json;charset=utf-8",
    # Python frameworks use text/json
    "text/json",
}


@scenarios.appsec_blocking
@scenarios.appsec_lambda_blocking
@features.appsec_blocking_action
class Test_Blocking:
    """Blocking response is obtained when triggering a blocking rule, test the default blocking response"""

    def setup_no_accept(self):
        self.r_na = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    @bug(context.library < "java@0.115.0" and context.weblog_variant == "spring-boot-undertow", reason="APMRP-360")
    @bug(context.library < "java@0.115.0" and context.weblog_variant == "spring-boot-wildfly", reason="APMRP-360")
    @bug(context.library < "python@1.16.1", reason="APMRP-360")
    @bug(context.library < "ruby@1.12.1", reason="APMRP-360")
    def test_no_accept(self):
        """Blocking without an accept header"""
        assert self.r_na.status_code == 403
        assert self.r_na.headers.get("content-type", "") in JSON_CONTENT_TYPES
        assert_valid_json_blocked_template(self.r_na.text)

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
            if span.get("type") not in ("web", "serverless"):
                return None

            if span.get("parent_id") not in (0, None):  # do nothing if not root span
                return None

            if "appsec.blocked" not in span["meta"]:
                raise ValueError("Can't find appsec.blocked in span's tags")

            return True

        interfaces.library.validate_one_span(self.r_abt, validator=validate_appsec_blocked)

    def setup_accept_all(self):
        self.r_aa = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1", "Accept": "*/*"})

    @bug(context.library < "ruby@1.12.1", reason="APMRP-360")
    def test_accept_all(self):
        """Blocking with Accept: */*"""
        assert self.r_aa.status_code == 403
        assert self.r_aa.headers.get("content-type", "") in JSON_CONTENT_TYPES
        assert_valid_json_blocked_template(self.r_aa.text)

    def setup_accept_partial_json(self):
        # */* should be ignored because there are more specific matches for text/html and application/json
        self.r_apj = weblog.get(
            "/waf/", headers={"User-Agent": "Arachni/v1", "Accept": "text/*;q=0.7, application/*;q=0.8, */*;q=0.9"}
        )

    @bug(context.library < "ruby@1.12.1", reason="APMRP-360")
    def test_accept_partial_json(self):
        """Blocking with Accept: application/*"""
        assert self.r_apj.status_code == 403
        assert self.r_apj.headers.get("content-type", "") in JSON_CONTENT_TYPES
        assert_valid_json_blocked_template(self.r_apj.text)

    def setup_accept_partial_html(self):
        self.r_aph = weblog.get(
            "/waf/", headers={"User-Agent": "Arachni/v1", "Accept": "text/*;q=0.8, application/*;q=0.7, */*;q=0.9"}
        )

    @missing_feature(context.library == "php", reason="Support for partial html not implemented")
    @missing_feature(context.library == "dotnet", reason="Support for partial html not implemented")
    @missing_feature(context.library == "golang", reason="Support for partial html not implemented")
    @missing_feature(context.library == "nodejs", reason="Support for partial html not implemented")
    @missing_feature(context.library < "python@2.11.0.dev")
    @missing_feature(context.library == "ruby", reason="Support for partial html not implemented")
    def test_accept_partial_html(self):
        """Blocking with Accept: text/*"""
        assert self.r_aph.status_code == 403
        assert self.r_aph.headers.get("content-type", "").lower() in HTML_CONTENT_TYPES
        assert_valid_html_blocked_template(self.r_aph.text)

    def setup_accept_full_json(self):
        self.r_afj = weblog.get(
            "/waf/",
            headers={
                "User-Agent": "Arachni/v1",
                "Accept": "text/*;q=0.8, application/*;q=0.7, application/json;q=0.85, */*;q=0.9",
            },
        )

    @bug(context.library < "ruby@1.12.1", reason="APMRP-360")
    def test_accept_full_json(self):
        """Blocking with Accept: application/json"""
        assert self.r_afj.status_code == 403
        assert self.r_afj.headers.get("content-type", "").lower() in JSON_CONTENT_TYPES
        assert_valid_json_blocked_template(self.r_afj.text)

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
        assert_valid_html_blocked_template(self.r_afh.text)

    def setup_json_template_v1(self):
        self.r_json_v1 = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1", "Accept": "application/json"})

    @missing_feature(context.library < "java@1.14.0")
    @missing_feature(context.library < "nodejs@4.1.0")
    @missing_feature(context.library < "golang@1.52.0")
    @missing_feature(library="dotnet")
    @missing_feature(library="php")
    @missing_feature(context.library < "python@2.11.0.dev")
    @missing_feature(library="ruby")
    def test_json_template_v1(self):
        """JSON block template is v1 minified (or v3 with security_response_id)"""
        assert self.r_json_v1.status_code == 403
        assert self.r_json_v1.headers.get("content-type", "").lower() in JSON_CONTENT_TYPES

        # Accept v1 template without security_response_id or v3 template with security_response_id
        response_text = self.r_json_v1.text.rstrip()
        v1_template = _read_file(BLOCK_TEMPLATE_JSON_MIN_V1).rstrip()

        # Check if it's v1 template
        if response_text == v1_template:
            return

        # Check if it's v3 template with valid security_response_id
        assert _is_valid_json_v3_template(self.r_json_v1.text), "Response doesn't match v1 or v3 template"

    def setup_html_template_v2(self):
        self.r_html_v2 = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1", "Accept": "text/html"})

    @missing_feature(context.library < "java@1.14.0")
    @missing_feature(context.library < "nodejs@4.1.0")
    @missing_feature(context.library < "golang@1.52.0")
    @missing_feature(library="dotnet")
    @missing_feature(context.library < "python@2.11.0.dev")
    @missing_feature(library="ruby")
    def test_html_template_v2(self):
        """HTML block template is v2 minified (or v3 with security_response_id)"""
        assert self.r_html_v2.status_code == 403
        assert self.r_html_v2.headers.get("content-type", "").lower() in HTML_CONTENT_TYPES

        # Accept v2 template without security_response_id or v3 template with security_response_id
        response_text = self.r_html_v2.text
        v2_template = _read_file(BLOCK_TEMPLATE_HTML_MIN_V2)

        # Check if it's v2 template
        if response_text == v2_template:
            return

        # Check if it's v3 template with valid security_response_id
        assert _is_valid_html_v3_template(self.r_html_v2.text), "Response doesn't match v2 or v3 template"


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2705464728/Blocking#Stripping-response-headers")
@scenarios.appsec_blocking
@scenarios.appsec_lambda_blocking
@features.appsec_blocking_action
class Test_Blocking_strip_response_headers:
    def setup_strip_response_headers(self):
        self.r_srh = weblog.get("/tag_value/anything/200?x-secret-header=123&content-language=krypton")

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
@scenarios.appsec_lambda_blocking
@features.appsec_blocking_action
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

    def test_custom_redirect_wrong_status_code(self):
        """Block with an HTTP redirection but default to 303 status code, because the configured status code is not a valid redirect status code"""
        assert self.r_cr.status_code == 303
        assert self.r_cr.headers.get("location", "") == "/you-have-been-blocked"

    def setup_custom_redirect_missing_location(self):
        self.r_cr = weblog.get("/waf/", headers={"User-Agent": "Canary/v4"}, allow_redirects=False)

    def test_custom_redirect_missing_location(self):
        """Block with an default page because location parameter is missing from redirect request configuration"""
        assert self.r_cr.status_code == 403
        assert_valid_json_blocked_template(self.r_cr.text)
