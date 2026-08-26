from utils import interfaces, rfc, scenarios, weblog, features

from utils.telemetry import validate_app_endpoints_schema


@rfc("https://docs.google.com/document/d/1txwuurIiSUWjYX7Xa0let7e49XKW2uhm1djgqjl_gL0/edit?tab=t.0")
@scenarios.appsec_api_security
@scenarios.appsec_otel_collector_api_security
@features.api_security_endpoint_discovery
class Test_Endpoint_Discovery:
    _main_setup_done: bool = False

    def main_setup(self):
        """Setup (once) for endpoint discovery tests."""
        if Test_Endpoint_Discovery._main_setup_done:
            return
        weblog.get("/")
        Test_Endpoint_Discovery._main_setup_done = True

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

    def setup_endpoint_discovery(self):
        """Setup for endpoint discovery test."""
        self.main_setup()

    def test_endpoint_discovery(self):
        """Test for endpoint discovery in API security.

        Mandatory for the feature.
        """
        self._get_endpoints()

    def setup_is_first(self):
        """Setup for is_first test."""
        self.main_setup()

    def test_single_is_first(self):
        """Verify that the is_first flag appears exactly once in telemetry.

        Mandatory for the feature.
        """

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

    def setup_optional_type(self):
        """Setup for optional type test."""
        self.main_setup()

    def test_optional_type(self):
        endpoints = self._get_endpoints()
        found = False
        for endpoint in endpoints:
            endpoint_type = endpoint.get("type")
            if endpoint_type is not None:
                found = True
                assert isinstance(endpoint_type, str)
        assert found, "No endpoint contained the optional 'type' attribute"

    def setup_optional_method(self):
        """Setup for optional method test."""
        self.main_setup()

    def test_optional_method(self):
        endpoints = self._get_endpoints()
        allowed = {
            "GET",
            "POST",
            "PUT",
            "DELETE",
            "PATCH",
            "HEAD",
            "OPTIONS",
            "TRACE",
            "CONNECT",
            "*",
            "PROPFIND",
            "REPORT",
        }
        found = False
        for endpoint in endpoints:
            endpoint_method = endpoint.get("method")
            if endpoint_method is not None:
                found = True
                assert endpoint_method in allowed
        assert found, "No endpoint contained the optional 'method' attribute"

    def setup_optional_path(self):
        """Setup for optional path test."""
        self.main_setup()

    def test_optional_path(self):
        endpoints = self._get_endpoints()
        found = False
        for endpoint in endpoints:
            endpoint_path = endpoint.get("path")
            if endpoint_path is not None:
                found = True
                assert isinstance(endpoint_path, str)
        assert found, "No endpoint contained the optional 'path' attribute"

    def setup_optional_request_body_type(self):
        """Setup for optional request body type test."""
        self.main_setup()

    def test_optional_request_body_type(self):
        endpoints = self._get_endpoints()
        found = False
        for endpoint in endpoints:
            endpoint_body_type = endpoint.get("request_body_type")
            if endpoint_body_type is not None:
                found = True
                assert isinstance(endpoint_body_type, list)
                assert all(isinstance(t, str) for t in endpoint_body_type)
        assert found, "No endpoint contained the optional 'request_body_type' attribute"

    def setup_optional_response_body_type(self):
        """Setup for optional response body type test."""
        self.main_setup()

    def test_optional_response_body_type(self):
        endpoints = self._get_endpoints()
        found = False
        for endpoint in endpoints:
            endpoint_body_type = endpoint.get("response_body_type")
            if endpoint_body_type is not None:
                found = True
                assert isinstance(endpoint_body_type, list)
                assert all(isinstance(t, str) for t in endpoint_body_type)
        assert found, "No endpoint contained the optional 'response_body_type' attribute"

    def setup_optional_response_code(self):
        """Setup for optional response code test."""
        self.main_setup()

    def test_optional_response_code(self):
        endpoints = self._get_endpoints()
        found = False
        for endpoint in endpoints:
            endpoint_code = endpoint.get("response_code")
            if endpoint_code is not None:
                found = True
                assert isinstance(endpoint_code, list)
                assert len(endpoint_code) >= 1
                assert all(isinstance(code, int) for code in endpoint_code)
        assert found, "No endpoint contained the optional 'response_code' attribute"

    def setup_optional_authentication(self):
        """Setup for optional authentication test."""
        self.main_setup()

    def test_optional_authentication(self):
        endpoints = self._get_endpoints()
        allowed = {"JWT", "basic", "oauth", "OIDC", "api_key", "session", "mTLS", "SAML", "LDAP", "Form", "other"}
        found = False
        for endpoint in endpoints:
            endpoint_authentication = endpoint.get("authentication")
            if endpoint_authentication is not None:
                found = True
                assert isinstance(endpoint_authentication, list)
                assert all(auth in allowed for auth in endpoint_authentication)
        assert found, "No endpoint contained the optional 'authentication' attribute"

    def setup_optional_metadata(self):
        """Setup for optional metadata test."""
        self.main_setup()

    def test_optional_metadata(self):
        endpoints = self._get_endpoints()
        found = False
        for endpoint in endpoints:
            endpoint_metadata = endpoint.get("metadata")
            if endpoint_metadata is not None:
                found = True
                assert isinstance(endpoint_metadata, dict)
        assert found, "No endpoint contained the optional 'metadata' attribute"
