from utils import weblog, interfaces, features, scenarios, logger, rfc
from utils._weblog import CaseInsensitiveDict
from utils.dd_types import DataDogSpan


def validate_builder(headers: CaseInsensitiveDict, *, mandatory: bool = True):
    content_type = headers.get("Content-Type")
    content_length = headers.get("Content-Length")
    content_encoding = headers.get("Content-Encoding")
    content_language = headers.get("Content-Language")

    def validator(span: DataDogSpan):
        assert (enabled := span["metrics"].get("_dd.appsec.enabled")) == 1.0, (
            f"Expected _dd.appsec.enabled to be '1.0', got {enabled}"
        )

        assert (content_type_tag := span["meta"].get("http.response.headers.content-type")), (
            f"Expected content-type, got {content_type_tag}"
        )

        assert isinstance(content_type_tag, str), f"Expected content-type to be a string, got {type(content_type_tag)}"
        assert content_type_tag.startswith(("text/", "application/json")), (
            f"Expected content-type to be 'text/html', 'text/plain' or 'application/json', got {content_type_tag}"
        )
        assert content_type == content_type_tag, (
            f"Expected content-type header to be {content_type}, got {content_type_tag}"
        )

        if mandatory:
            assert content_length is not None, "Expected content-length header to be present"
        else:
            logger.info(
                f"Content-length is optional for this test, skipping assertion. Got content-length: {content_length}"
            )

        if content_length is not None:
            assert (content_length_tag := span["meta"].get("http.response.headers.content-length")) == content_length, (
                f"Expected content-length to be {content_length}, got {content_length_tag}"
            )

        if content_encoding is not None:
            assert (
                content_encoding_tag := span["meta"].get("http.response.headers.content-encoding")
            ) == content_encoding, f"Expected content-encoding to be {content_encoding}, got {content_encoding_tag}"
        logger.info(f"Content-encoding is optional for this test. Got content-encoding: {content_encoding}")

        if content_language is not None:
            assert (
                content_language_tag := span["meta"].get("http.response.headers.content-language")
            ) == content_language, f"Expected content-language to be {content_language}, got {content_language_tag}"
        logger.info(f"Content-language is optional for this test. Got content-language: {content_language}")

        return True

    return validator


@rfc("https://datadoghq.atlassian.net/wiki/spaces/SAAL/pages/2186870984/HTTP+header+collection")
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
        interfaces.library.validate_one_span(self.r, validator=validate_builder(self.r.headers))


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
        interfaces.library.validate_one_span(self.r, validator=validate_builder(self.r.headers))


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
        interfaces.library.validate_one_span(self.r, validator=validate_builder(self.r.headers, mandatory=False))
