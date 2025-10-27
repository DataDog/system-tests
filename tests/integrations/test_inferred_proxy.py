import json
import time

from utils import weblog, scenarios, features, interfaces, logger


DISTRIBUTED_TRACE_ID = 1
DISTRIBUTED_PARENT_ID = 2
DISTRIBUTED_SAMPLING_PRIORITY = 2


class _BaseTestCase:
    start_time: int
    start_time_ns: int


@features.aws_api_gateway_inferred_span_creation
@scenarios.integrations
class Test_AWS_API_Gateway_Inferred_Span_Creation(_BaseTestCase):
    """Verify AWS API Gateway inferred spans are created when a web server receives specific headers."""

    start_time = round(time.time() * 1000)
    start_time_ns = start_time * 1000000

    def setup_api_gateway_inferred_span_creation(self):
        headers = {
            "x-dd-proxy-request-time-ms": str(self.start_time),  # in ms
            "x-dd-proxy-path": "/api/data",
            "x-dd-proxy-httpmethod": "GET",
            "x-dd-proxy-domain-name": "system-tests-api-gateway.com",
            "x-dd-proxy-stage": "staging",
            "x-dd-proxy": "aws-apigateway",
        }

        self.r = weblog.get("/inferred-proxy/span-creation?status_code=200", headers=headers, timeout=60)

    def test_api_gateway_inferred_span_creation(self):
        assert self.r.text == "ok"

        span = get_span(interfaces.library, "GET /api/data")

        assert span is not None, "API Gateway inferred span should have been created but was not found!"

        assert_api_gateway_span(self, span, path="/api/data", status_code="200")


@features.aws_api_gateway_inferred_span_creation
@scenarios.integrations
class Test_AWS_API_Gateway_Inferred_Span_Creation_With_Distributed_Context(_BaseTestCase):
    """Verify AWS API Gateway inferred spans are created when a web server receives specific headers and
    distributed context.
    """

    start_time = round(time.time() * 1000)
    start_time_ns = start_time * 1000000

    def setup_api_gateway_inferred_span_creation_with_distributed_context(self):
        headers = {
            "x-dd-proxy-request-time-ms": str(self.start_time),  # in ms
            "x-dd-proxy-path": "/api/data/distributed",
            "x-dd-proxy-httpmethod": "GET",
            "x-dd-proxy-domain-name": "system-tests-api-gateway.com",
            "x-dd-proxy-stage": "staging",
            "x-dd-proxy": "aws-apigateway",
            "x-datadog-trace-id": str(DISTRIBUTED_TRACE_ID),
            "x-datadog-parent-id": str(DISTRIBUTED_PARENT_ID),
            "x-datadog-origin": "rum",
            "x-datadog-sampling-priority": str(DISTRIBUTED_SAMPLING_PRIORITY),
        }

        self.r = weblog.get("/inferred-proxy/span-creation?status_code=200", headers=headers, timeout=60)

    def test_api_gateway_inferred_span_creation_with_distributed_context(self):
        assert self.r.text == "ok"

        span = get_span(interfaces.library, "GET /api/data/distributed")

        assert span is not None, "API Gateway inferred span should have been created but was not found!"

        assert_api_gateway_span(self, span, path="/api/data/distributed", status_code="200", is_distributed=True)


@features.aws_api_gateway_inferred_span_creation
@scenarios.integrations
class Test_AWS_API_Gateway_Inferred_Span_Creation_With_Error(_BaseTestCase):
    """Verify AWS API Gateway inferred spans are created when a web server receives specific headers and
    an error.
    """

    start_time = round(time.time() * 1000)
    start_time_ns = start_time * 1000000

    def setup_api_gateway_inferred_span_creation_error(self):
        headers = {
            "x-dd-proxy-request-time-ms": str(self.start_time),  # in ms
            "x-dd-proxy-path": "/api/data/error",
            "x-dd-proxy-httpmethod": "GET",
            "x-dd-proxy-domain-name": "system-tests-api-gateway.com",
            "x-dd-proxy-stage": "staging",
            "x-dd-proxy": "aws-apigateway",
        }

        self.r = weblog.get("/inferred-proxy/span-creation?status_code=500", headers=headers, timeout=60)

    def test_api_gateway_inferred_span_creation_error(self):
        assert self.r.text == "ok"

        span = get_span(interfaces.library, "GET /api/data/error")

        assert span is not None, "API Gateway inferred span should have been created but was not found!"

        assert_api_gateway_span(
            self, span, path="/api/data/error", status_code="500", is_distributed=False, is_error=True
        )


def get_span(interface: interfaces.LibraryInterfaceValidator, resource: str) -> dict | None:
    logger.debug(f"Trying to find API Gateway span for interface: {interface}")

    for data, trace in interface.get_traces():
        for span in trace:
            if not span.get("meta"):
                continue

            if span["name"] != "aws.apigateway":
                continue

            if span["resource"] != resource:
                continue

            logger.debug(f"Span found in {data['log_filename']}:\n{json.dumps(span, indent=2)}")
            return span

    logger.debug("No span found")
    return None


def assert_api_gateway_span(
    test_case: _BaseTestCase,
    span: dict,
    path: str,
    status_code: str,
    *,
    is_distributed: bool = False,
    is_error: bool = False,
) -> None:
    assert span["name"] == "aws.apigateway", "Inferred AWS API Gateway span name should be 'aws.apigateway'"

    # Assertions to check if the span data contains the required keys and values.
    assert "meta" in span, "Inferred AWS API Gateway span should contain 'meta'"
    assert "component" in span["meta"], (
        "Inferred AWS API Gateway span meta should contain 'component' equal to 'aws-apigateway'"
    )
    assert span["meta"]["component"] == "aws-apigateway", "Expected component to be 'aws-apigateway'"

    if "language" in span["meta"] and span["meta"]["language"] == "javascript":
        assert "service" in span["meta"], "Inferred AWS API Gateway span meta should contain 'service'"
        assert span["meta"]["service"] == "system-tests-api-gateway.com", (
            "Inferred AWS API Gateway span expected service should equal 'system-tests-api-gateway.com'"
        )
    else:
        assert "service" in span, "Inferred AWS API Gateway span should contain 'service'"
        assert span["service"] == "system-tests-api-gateway.com", (
            "Inferred AWS API Gateway span expected service should equal 'system-tests-api-gateway.com'"
        )
    assert "stage" in span["meta"], "Inferred AWS API Gateway span meta should contain 'stage'"
    assert span["meta"]["stage"] == "staging", "Inferred AWS API Gateway span meta expected stage to be 'staging'"
    assert "start" in span, "Inferred AWS API Gateway span should have 'startTime'"
    assert span["metrics"]["_dd.inferred_span"] == 1, (
        "Inferred AWS API Gateway span meta expected _dd.inferred_span = 1"
    )

    # assert on HTTP tags
    assert "http.method" in span["meta"], "Inferred AWS API Gateway span meta should contain 'http.method'"
    assert span["meta"]["http.method"] == "GET", "Inferred AWS API Gateway span meta expected HTTP method to be 'GET'"
    assert "http.url" in span["meta"], "Inferred AWS API Gateway span eta should contain 'http.url'"
    assert span["meta"]["http.url"] == "system-tests-api-gateway.com" + path, (
        f"Inferred AWS API Gateway span meta expected HTTP URL to be 'system-tests-api-gateway.com{path}'"
    )
    assert "http.status_code" in span["meta"], "Inferred AWS API Gateway span eta should contain 'http.status_code'"
    assert span["meta"]["http.status_code"] == status_code, (
        f"Inferred AWS API Gateway span meta expected HTTP Status Code of '{status_code}'"
    )

    if not interfaces.library.replay:
        # round the start time since we get some inconsistent errors due to how the agent rounds start times.
        assert round(span["start"], -6) == test_case.start_time_ns, (
            f"Inferred AWS API Gateway span startTime should equal expected '{test_case.start_time_ns!s}''"
        )

    if is_distributed:
        assert span["trace_id"] == DISTRIBUTED_TRACE_ID
        assert span["parent_id"] == DISTRIBUTED_PARENT_ID
        assert span["metrics"]["_sampling_priority_v1"] == DISTRIBUTED_SAMPLING_PRIORITY

    if is_error:
        assert span["error"] == 1
        assert span["meta"]["http.status_code"] == "500"
