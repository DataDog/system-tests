import re

import pytest

from utils import released, coverage, interfaces, bug, scenario, weblog
from utils._context.core import context

if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")

HTML_DATA = """<!-- Sorry, you’ve been blocked -->
<!DOCTYPE html>
<html lang="en">

<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>You've been blocked</title>
  <style>
    a,
    body,
    div,
    html,
    span {
      margin: 0;
      padding: 0;
      border: 0;
      font-size: 100%;
      font: inherit;
      vertical-align: baseline
    }

    body {
      background: -webkit-radial-gradient(26% 19%, circle, #fff, #f4f7f9);
      background: radial-gradient(circle at 26% 19%, #fff, #f4f7f9);
      display: -webkit-box;
      display: -ms-flexbox;
      display: flex;
      -webkit-box-pack: center;
      -ms-flex-pack: center;
      justify-content: center;
      -webkit-box-align: center;
      -ms-flex-align: center;
      align-items: center;
      -ms-flex-line-pack: center;
      align-content: center;
      width: 100%;
      min-height: 100vh;
      line-height: 1;
      flex-direction: column
    }

    p {
      display: block
    }


    main {
      text-align: center;
      flex: 1;
      display: -webkit-box;
      display: -ms-flexbox;
      display: flex;
      -webkit-box-pack: center;
      -ms-flex-pack: center;
      justify-content: center;
      -webkit-box-align: center;
      -ms-flex-align: center;
      align-items: center;
      -ms-flex-line-pack: center;
      align-content: center;
      flex-direction: column
    }

    p {
      font-size: 18px;
      line-height: normal;
      color: #646464;
      font-family: sans-serif;
      font-weight: 400
    }

    a {
      color: #4842b7
    }

    footer {
      width: 100%;
      text-align: center
    }

    footer p {
      font-size: 16px
    }
  </style>
</head>

<body>
<main>
  <p>Sorry, you cannot access this page. Please contact the customer service team.</p>
</main>
<footer>
  <p>Security provided by <a
    href="https://www.datadoghq.com/product/security-platform/application-security-monitoring/"
    target="_blank">Datadog</a></p>
</footer>
</body>

</html>
"""


@released(dotnet="?", golang="?", nodejs="?", php_appsec="?", python="?", ruby="?")
@released(
    java={
        "spring-boot": "0.112.0",
        "sprint-boot-jetty": "0.112.0",
        "spring-boot-undertow": "0.112.0",
        "spring-boot-openliberty": "1.3.0",
        "*": "?",
    }
)
@coverage.basic
@scenario("APPSEC_BLOCKING")
class Test_Blocking:
    """Blocking response is obtained when triggering a blocking rule"""

    @bug(context.library < "java@0.115.0" and context.weblog_variant == "spring-boot-undertow", reason="npe")
    def test_no_accept(self):
        """Blocking without an accept header"""
        r = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})
        assert r.status_code == 403
        assert re.match("^application/json", r.headers.get("content-type", "")) is not None
        assert (
            r.text == '{"errors": [{"title": "You\'ve been blocked", "detail": "Sorry, you cannot access '
            'this page. Please contact the customer service team. Security provided by Datadog."}]}\n'
        )

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

    def test_accept_all(self):
        """Blocking with Accept: */*"""
        r = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1", "Accept": "*/*"})
        assert r.status_code == 403
        assert re.match("^application/json", r.headers.get("content-type", "")) is not None

    def test_accept_partial_json(self):
        """Blocking with Accept: application/*"""
        # */* should be ignored because there are more specific matches for text/html and application/json
        r = weblog.get(
            "/waf/", headers={"User-Agent": "Arachni/v1", "Accept": "text/*;q=0.7, application/*;q=0.8, */*;q=0.9"}
        )
        assert r.status_code == 403
        assert re.match("^application/json", r.headers.get("content-type", "")) is not None

    def test_accept_partial_html(self):
        """Blocking with Accept: text/*"""
        r = weblog.get(
            "/waf/", headers={"User-Agent": "Arachni/v1", "Accept": "text/*;q=0.8, application/*;q=0.7, */*;q=0.9"}
        )
        assert r.status_code == 403
        assert r.text == HTML_DATA

    def test_accept_full_json(self):
        """Blocking with Accept: application/json"""
        r = weblog.get(
            "/waf/",
            headers={
                "User-Agent": "Arachni/v1",
                "Accept": "text/*;q=0.8, application/*;q=0.7, application/json;q=0.85, */*;q=0.9",
            },
        )
        assert r.status_code == 403
        assert re.match("^application/json", r.headers.get("content-type", "")) is not None

    def test_accept_full_html(self):
        """Blocking with Accept: text/html"""
        r = weblog.get(
            "/waf/",
            headers={
                "User-Agent": "Arachni/v1",
                "Accept": "text/html;q=0.9, text/*;q=0.8, application/json;q=0.85, */*;q=0.9",
            },
        )
        assert r.status_code == 403
        assert re.match("^text/html", r.headers.get("content-type", "")) is not None
