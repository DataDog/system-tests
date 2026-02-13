from utils import weblog, interfaces, features, scenarios


def validate_headers_tags(span: dict):
    assert (enabled := span["metrics"].get("_dd.appsec.enabled")) == 1.0, (
        f"Expected _dd.appsec.enabled to be '1.0', got {enabled}"
    )

    assert (content_type := span["meta"].get("http.response.headers.content-type")), (
        f"Expected content-type, got {content_type}"
    )

    assert isinstance(content_type, str), f"Expected content-type to be a string, got {type(content_type)}"
    assert content_type.startswith(("text/", "application/json")), (
        f"Expected content-type to be 'text/html', 'text/plain' or 'application/json', got {content_type}"
    )

    return True


@features.appsec_request_blocking
@scenarios.appsec_blocking
class Test_Headers_No_Event:
    """Check for headers in the absence of security event"""

    def setup_content_type_no_event(self):
        self.r = weblog.get("/", headers={"User-Agent": "Mozilla/5.0"})

    def test_content_type_no_event(self):
        # Send a random attack on the identify endpoint - should not affect the usr.id tag

        assert self.r.status_code == 200

        interfaces.library.validate_one_span(self.r, validator=validate_headers_tags)


@features.appsec_request_blocking
@scenarios.appsec_blocking
class Test_Headers_Event_No_Blocking:
    """Check for headers in the absence of security event"""

    def setup_content_type_event(self):
        self.r = weblog.get("/", headers={"User-Agent": "TraceTagging/v3"})

    def test_content_type_event(self):
        # Send a random attack on the identify endpoint - should not affect the usr.id tag

        assert self.r.status_code == 200

        interfaces.library.validate_one_span(self.r, validator=validate_headers_tags)


@features.appsec_request_blocking
@scenarios.appsec_blocking
class Test_Headers_Event_Blocking:
    """Check for headers in the absence of security event"""

    def setup_content_type_event_blocking(self):
        self.r = weblog.get("/", headers={"User-Agent": "Arachni/v1"})

    def test_content_type_event_blocking(self):
        # Send a random attack on the identify endpoint - should not affect the usr.id tag

        assert self.r.status_code == 403

        def validate_headers_tags(span: dict):
            assert (enabled := span["metrics"].get("_dd.appsec.enabled")) == 1.0, (
                f"Expected _dd.appsec.enabled to be '1', got {enabled}"
            )

            assert (content_type := span["meta"].get("http.response.headers.content-type")), (
                f"Expected content-type, got {content_type}"
            )
            assert content_type.startswith(("text/", "application/json")), (
                f"Expected content-type to be 'text/html', 'text/plain' or 'application/json', got {content_type}"
            )

            return True

        interfaces.library.validate_one_span(self.r, validator=validate_headers_tags)
