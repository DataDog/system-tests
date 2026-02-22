import json
import time

from utils import weblog, interfaces, scenarios, features
from utils.dd_types import DataDogSpan

INFERRED_SPAN_NAMES = {"aws.apigateway", "aws.httpapi"}


@scenarios.appsec_lambda_inferred_spans
@features.appsec_api_gateway_inferred_span_discovery
class Test_Lambda_Inferred_Span_Tags:
    """Tests for endpoint discovery & correlation from lambda inferred spans"""

    def setup_lambda_inferred_span(self) -> None:
        self.r = weblog.get("/waf/?message=<script>alert()</script>")

    def test_lambda_inferred_span(self) -> None:
        for _, _, span, appsec_data in interfaces.library.get_appsec_events(self.r):
            if span.get("name") == "aws.lambda":
                lambda_span_appsec_data = appsec_data

        assert lambda_span_appsec_data, "Expected non empty appsec data on aws.lambda span"

        def validate_inferred_span(span: DataDogSpan) -> bool:
            if span.get("name") not in INFERRED_SPAN_NAMES:
                return False

            assert span.get("type") == "web", "Lambda inferred spans must be of type web"
            assert "operation_name" not in span.get("meta", {}), "operation_name should be removed"

            metrics = span.get("metrics", {})
            appsec_enabled = metrics.get("_dd.appsec.enabled")
            assert appsec_enabled is not None, "Lambda inferred spans must report _dd.appsec.enabled"
            assert float(appsec_enabled) == 1.0

            inferred_span_payload = span.get("meta", {}).get("_dd.appsec.json", {}) or span.get("meta_struct", {}).get(
                "appsec", {}
            )
            assert inferred_span_payload, "Lambda inferred spans must include the appsec payload"
            inferred_payload = (
                json.loads(inferred_span_payload) if isinstance(inferred_span_payload, str) else inferred_span_payload
            )
            assert inferred_payload == lambda_span_appsec_data, "AppSec Data must match the service-entry span"

            return True

        interfaces.library.validate_one_span(self.r, validator=validate_inferred_span, full_trace=True)


@scenarios.integrations
@features.appsec_api_gateway_inferred_span_discovery
class Test_Proxy_Inferred_Span_Tags:
    """Tests for endpoint discovery & correlation from proxy inferred spans"""

    start_time = round(time.time() * 1000)
    start_time_ns = start_time * 1000000

    def setup_proxy_inferred_span(self) -> None:
        headers = {
            "x-dd-proxy": "aws-apigateway",
            "x-dd-proxy-request-time-ms": str(self.start_time),  # in ms
            "x-dd-proxy-path": "/api/data/appsec",
            "x-dd-proxy-resource-path": "/api/{Proxy}",
            "x-dd-proxy-httpmethod": "GET",
            "x-dd-proxy-domain-name": "system-tests-api-gateway.com",
            "x-dd-proxy-stage": "staging",
            "x-dd-proxy-account-id": "123456789123",
            "x-dd-proxy-api-id": "a1b2c3d4e5f",
            "x-dd-proxy-region": "eu-west-3",
            "x-dd-proxy-user": "aws-user",
        }

        self.r = weblog.get("/waf/?message=<script>alert()</script>", headers=headers)

    def test_proxy_inferred_span(self) -> None:
        service_entry_span_appsec_data = None
        for _, _, span, appsec_data in interfaces.library.get_appsec_events(self.r):
            if span.get("service") == "weblog":
                service_entry_span_appsec_data = appsec_data

        assert service_entry_span_appsec_data, "Expected non empty appsec data on the weblog entry span"

        def validate_inferred_span(span: DataDogSpan) -> bool:
            if span.get("name") != "aws.apigateway":
                return False

            metrics = span.get("metrics", {})
            appsec_enabled = metrics.get("_dd.appsec.enabled")
            assert appsec_enabled is not None, "Proxy inferred spans must report _dd.appsec.enabled"
            assert float(appsec_enabled) == 1.0

            inferred_span_payload = span.get("meta", {}).get("_dd.appsec.json", {}) or span.get("meta_struct", {}).get(
                "appsec", {}
            )
            assert inferred_span_payload, "Proxy inferred spans must include the appsec payload"
            inferred_payload = (
                json.loads(inferred_span_payload) if isinstance(inferred_span_payload, str) else inferred_span_payload
            )
            assert inferred_payload == service_entry_span_appsec_data, "AppSec Data must match the service-entry span"

            return True

        interfaces.library.validate_one_span(self.r, validator=validate_inferred_span, full_trace=True)
