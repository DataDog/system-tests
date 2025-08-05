from utils import interfaces, rfc, scenarios, weblog, features, irrelevant, missing_feature, context

from utils.telemetry import validate_app_endpoints_schema


@rfc("https://docs.google.com/document/d/1txwuurIiSUWjYX7Xa0let7e49XKW2uhm1djgqjl_gL0/edit?tab=t.0")
@scenarios.appsec_api_security
@features.api_security_endpoint_discovery
class Test_Endpoint_Discovery:
    def setup_endpoint_discovery(self):
        """Setup for endpoint discovery tests."""
        for _ in range(10):
            weblog.get("/")

    def _get_discovered(self):
        """Return all payloads sent through app-endpoints telemetry events."""
        validate_app_endpoints_schema()

        discovered: list[dict] = []
        for data in interfaces.library.get_telemetry_data():
            content = data["request"]["content"]
            if content.get("request_type") != "app-endpoints":
                continue
            discovered.append(content["payload"])

        assert discovered, "No endpoint discovery data found"
        return discovered

    def _get_endpoints(self):
        discovered_list = self._get_discovered()
        assert any(d.get("is_first") for d in discovered_list), "Endpoint discovery should be the first request"

        endpoints: list[dict] = []
        for payload in discovered_list:
            endpoints.extend(payload.get("endpoints", []))

        assert endpoints, "No endpoints discovered"
        return endpoints

    def test_endpoint_discovery(self):
        """Test for endpoint discovery in API security."""
        self._get_endpoints()

    def test_optional_type(self):
        endpoints = self._get_endpoints()
        found = False
        for endpoint in endpoints:
            if "type" in endpoint:
                found = True
                assert isinstance(endpoint["type"], str)
        assert found, "No endpoint contained the optional 'type' attribute"

    def test_optional_method(self):
        endpoints = self._get_endpoints()
        allowed = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS", "TRACE", "CONNECT", "*"}
        found = False
        for endpoint in endpoints:
            if "method" in endpoint:
                found = True
                assert endpoint["method"] in allowed
        assert found, "No endpoint contained the optional 'method' attribute"

    def test_optional_path(self):
        endpoints = self._get_endpoints()
        found = False
        for endpoint in endpoints:
            if "path" in endpoint:
                found = True
                assert isinstance(endpoint["path"], str)
        assert found, "No endpoint contained the optional 'path' attribute"

    @missing_feature(
        context.library == "java" and context.weblog_variant in ["spring-boot"],
        reason="Missing endpoint discovery feature in weblog variant",
    )
    def test_optional_request_body_type(self):
        endpoints = self._get_endpoints()
        found = False
        for endpoint in endpoints:
            if "request_body_type" in endpoint:
                found = True
                assert isinstance(endpoint["request_body_type"], list)
                assert all(isinstance(t, str) for t in endpoint["request_body_type"])
        assert found, "No endpoint contained the optional 'request_body_type' attribute"

    def test_optional_response_body_type(self):
        endpoints = self._get_endpoints()
        found = False
        for endpoint in endpoints:
            if "response_body_type" in endpoint:
                found = True
                assert isinstance(endpoint["response_body_type"], list)
                assert all(isinstance(t, str) for t in endpoint["response_body_type"])
        assert found, "No endpoint contained the optional 'response_body_type' attribute"

    @irrelevant(
        context.library == "java" and context.weblog_variant in ["spring-boot"],
        reason="Not applicable to weblog variant",
    )
    def test_optional_response_code(self):
        endpoints = self._get_endpoints()
        found = False
        for endpoint in endpoints:
            if "response_code" in endpoint:
                found = True
                assert isinstance(endpoint["response_code"], list)
                assert len(endpoint["response_code"]) >= 1
                assert all(isinstance(code, int) for code in endpoint["response_code"])
        assert found, "No endpoint contained the optional 'response_code' attribute"

    @irrelevant(
        context.library == "java" and context.weblog_variant in ["spring-boot"],
        reason="Not applicable to weblog variant",
    )
    def test_optional_authentication(self):
        endpoints = self._get_endpoints()
        allowed = {"JWT", "basic", "oauth", "OIDC", "api_key", "session", "mTLS", "SAML", "LDAP", "Form", "other"}
        found = False
        for endpoint in endpoints:
            if "authentication" in endpoint:
                found = True
                assert isinstance(endpoint["authentication"], list)
                assert all(auth in allowed for auth in endpoint["authentication"])
        assert found, "No endpoint contained the optional 'authentication' attribute"

    def test_optional_metadata(self):
        endpoints = self._get_endpoints()
        found = False
        for endpoint in endpoints:
            if "metadata" in endpoint:
                found = True
                assert isinstance(endpoint["metadata"], dict)
        assert found, "No endpoint contained the optional 'metadata' attribute"

    def test_single_is_first(self):
        """Verify that the is_first flag appears exactly once in telemetry."""

        validate_app_endpoints_schema()

        is_first_count = 0
        for data in interfaces.library.get_telemetry_data():
            content = data["request"]["content"]
            if content.get("request_type") != "app-endpoints":
                continue
            payload = content.get("payload", {})
            if payload.get("is_first") is True:
                is_first_count += 1

        assert is_first_count == 1, f"Expected one is_first=true payload, found {is_first_count}"
