from utils import interfaces, rfc, scenarios, weblog, features

from utils.telemetry import validate_app_endpoints_schema


@rfc("https://docs.google.com/document/d/1txwuurIiSUWjYX7Xa0let7e49XKW2uhm1djgqjl_gL0/edit?tab=t.0")
@scenarios.appsec_api_security
@features.api_security_endpoint_discovery
class Test_Endpoint_Discovery:
    def setup_endpoint_discovery(self):
        """Setup for endpoint discovery tests."""
        self.request = weblog.get("/")

    def test_endpoint_discovery(self):
        """Test for endpoint discovery in API security."""
        validate_app_endpoints_schema()

        for data in interfaces.library.get_telemetry_data():
            content = data["request"]["content"]
            if content.get("request_type") != "app-endpoints":
                continue
            discovered = content["payload"]

        assert discovered is not None, "No endpoint discovery data found"
        assert discovered["is_first"] is True, "Endpoint discovery should be the first request"
        assert discovered["endpoints"], "No endpoints discovered"
