from utils import weblog, interfaces, features, scenarios


def validate_builder(*, check_for_content_length: bool = True):
    def validator(span: dict):
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

        if check_for_content_length:
            assert (content_length := span["meta"].get("http.response.headers.content-length")), (
                f"Expected content-length, got {content_length}"
            )

        return True

    return validator


@features.appsec_request_blocking
@scenarios.appsec_blocking
class Test_Headers_No_Event:
    """Check for headers in the absence of security event"""

    def setup_content_type_no_event(self):
        self.r = weblog.get("/", headers={"User-Agent": "Mozilla/5.0"})

    def test_content_type_no_event(self):
        # Send a non-malicious request with no triggered rules - should have the content-type and content-length tags
        assert self.r.status_code == 200
        interfaces.library.assert_no_appsec_event(self.r)
        # content-length is mandatory on this endpoint
        interfaces.library.validate_one_span(self.r, validator=validate_builder())


@features.appsec_request_blocking
@scenarios.appsec_blocking
class Test_Headers_Event_No_Blocking:
    """Check for headers in the absence of security event"""

    def setup_content_type_event(self):
        self.r = weblog.get("/", headers={"User-Agent": "TraceTagging/v3"})

    def test_content_type_event(self):
        # Send a request that triggers a security event but not blocking - should have the content-type and content-length tags
        assert self.r.status_code == 200
        interfaces.library.assert_waf_attack(self.r, rule="ttr-000-003")
        # content-length is mandatory on this endpoint
        interfaces.library.validate_one_span(self.r, validator=validate_builder())


@features.appsec_request_blocking
@scenarios.appsec_blocking
class Test_Headers_Event_Blocking:
    """Check for headers when a security event is triggered"""

    def setup_content_type_event_blocking(self):
        self.r = weblog.get("/", headers={"User-Agent": "Arachni/v1"})

    def test_content_type_event_blocking(self):
        # Send a request that triggers a blocking security event - should have the content-type and content-length tags
        assert self.r.status_code == 403
        interfaces.library.assert_waf_attack(self.r, rule="arachni_rule")
        # content-length is optional on blocking response
        is_cl = self.r.headers.get("Content-Length") is not None
        interfaces.library.validate_one_span(self.r, validator=validate_builder(check_for_content_length=is_cl))
