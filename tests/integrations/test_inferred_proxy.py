import json
import time

from utils import weblog, scenarios, features, interfaces
from utils.tools import logger


@features.aws_api_gateway_inferred_span_creation
@scenarios.integrations
class Test_AWS_API_Gateway_Inferred_Span_Creation:
    ...


class TOBEFIXED_Test_AWS_API_Gateway_Inferred_Span_Creation:
    """ Verify DSM context is extracted using "dd-pathway-ctx-base64" """

    start_time = round(time.time() * 1e3)
    start_time_ns = start_time * 1e6

    def setup_api_gateway_inferred_span_creation(self):
        headers = {
            "x-dd-proxy-request-time-ms": str(self.start_time),  # in ms
            "x-dd-proxy-path": "/api/data",
            "x-dd-proxy-httpmethod": "GET",
            "x-dd-proxy-domain-name": "system-tests-api-gateway.com",
            "x-dd-proxy-stage": "staging",
            "x-dd-proxy": "aws-apigateway",
        }

        self.r = weblog.get(f"/inferred-proxy/span-creation?status_code=200", headers=headers, timeout=60,)

    def test_api_gateway_inferred_span_creation(self):
        assert self.r.text == "ok"

        span = get_span(interfaces.library)

        assert span is not None, "API Gateway inferred span should have been created but was not found!"

        assert_api_gateway_span(self, span)


def get_span(interface):
    logger.debug(f"Trying to find API Gateway span for interface: {interface}")

    for data, trace in interface.get_traces():
        for span in trace:
            if not span.get("meta"):
                continue

            if span["name"] != "aws.apigateway":
                continue

            logger.debug(f"Span found in {data['log_filename']}:\n{json.dumps(span, indent=2)}")
            return span

    logger.debug("No span found")
    return None


def assert_api_gateway_span(testCase, span):
    assert span["name"] == "aws.apigateway", "Inferred AWS API Gateway span name should be 'aws.apigateway'"

    # Assertions to check if the span data contains the required keys and values.
    assert "meta" in span, "Inferred AWS API Gateway span should contain 'meta'"
    assert (
        "component" in span["meta"]
    ), "Inferred AWS API Gateway span meta should contain 'component' equal to 'aws-apigateway'"
    assert span["meta"]["component"] == "aws-apigateway", "Expected component to be 'aws-apigateway'"
    assert "service" in span["meta"], "Inferred AWS API Gateway span meta should contain 'service'"

    assert (
        span["meta"]["service"] == "system-tests-api-gateway.com"
    ), "Inferred AWS API Gateway span expected service should equal 'system-tests-api-gateway.com'"
    assert "span.kind" in span["meta"], "Inferred AWS API Gateway span meta should contain 'span.kind'"
    assert (
        span["meta"]["span.kind"] == "internal"
    ), "Inferred AWS API Gateway span meta span.kind should equal 'internal'"
    assert "http.method" in span["meta"], "Inferred AWS API Gateway span meta should contain 'http.method'"
    assert span["meta"]["http.method"] == "GET", "Inferred AWS API Gateway span meta expected HTTP method to be 'GET'"
    assert "http.url" in span["meta"], "Inferred AWS API Gateway span eta should contain 'http.url'"
    assert (
        span["meta"]["http.url"] == "system-tests-api-gateway.com/api/data"
    ), "Inferred AWS API Gateway span meta expected HTTP URL to be 'system-tests-api-gateway.com/api/data'"
    assert "http.route" in span["meta"], "Inferred AWS API Gateway span meta should contain 'http.route'"
    assert (
        span["meta"]["http.route"] == "/api/data"
    ), "Inferred AWS API Gateway span meta expected HTTP route to be '/api/data'"
    assert "stage" in span["meta"], "Inferred AWS API Gateway span meta should contain 'stage'"
    assert span["meta"]["stage"] == "staging", "Inferred AWS API Gateway span meta expected stage to be 'staging'"
    assert "start" in span, f"Inferred AWS API Gateway span should have 'startTime'"

    if not interfaces.library.replay:
        assert (
            span["start"] == testCase.start_time_ns
        ), f"Inferred AWS API Gateway span startTime should equal expected '{str(testCase.start_time_ns)}''"
