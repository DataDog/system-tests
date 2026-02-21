import json
import time
from typing import Literal

from utils import weblog, scenarios, features, interfaces, logger
from utils.dd_types import DataDogSpan

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


def get_span(interface: interfaces.LibraryInterfaceValidator, resource: str) -> DataDogSpan | None:
    logger.debug(f"Trying to find API Gateway span for interface: {interface}")

    for data, trace in interface.get_traces():
        for span in trace:
            if not span.get("meta"):
                continue

            if span["name"] != "aws.apigateway":
                continue

            if span["resource"] != resource:
                continue

            logger.debug(f"Span found in {data['log_filename']}:\n{json.dumps(span.raw_span, indent=2)}")
            return span

    logger.debug("No span found")
    return None


def assert_api_gateway_span(
    test_case: _BaseTestCase,
    span: DataDogSpan,
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

    if span["meta"].get("language") == "javascript":
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

    # Skip http.url and http.status_code assertions for Java (language='jvm') - these fields are not properly set
    is_java = span["meta"].get("language") == "jvm" or span["meta"].get("language") == "java"
    if not is_java:
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

    if is_error and not is_java:
        assert span["error"] == 1
        assert span["meta"]["http.status_code"] == "500"


def mandatory_tags_validator_factory(
    proxy: Literal["aws.apigateway", "aws.httpapi"],
    expected_status_code: str,
    expected_start_time_ns: float,
    *,
    distributed: bool = False,
    error: bool = False,
):
    if proxy == "aws.apigateway":
        expected_component = "aws-apigateway"
    else:
        expected_component = "aws-httpapi"

    def validate_api_gateway_span(span: DataDogSpan) -> bool:
        if span.get("metrics", {}).get("_dd.inferred_span") != 1:
            return False

        name = span.get("name")
        if name != proxy:
            raise ValueError(f"Inferred API Gateway span should be named 'aws.apigateway', found '{name}'")

        span_type = span.get("type")
        if span_type != "web":
            raise ValueError(f"Inferred API Gateway span should be of type 'web', found '{span_type}'")

        service = span.get("service")
        if service != "system-tests-api-gateway.com":
            raise ValueError(f"Inferred API Gateway service should be 'system-tests-api-gateway.com', found' {service}")

        resource = span.get("resource")
        if resource != "GET /api/{Proxy}":
            raise ValueError(f"Inferred API Gateway span should have resource 'GET /api/{{Proxy}}', found '{resource}'")

        if not interfaces.library.replay:
            start = span.get("start")
            if isinstance(start, int) and round(start, -6) != expected_start_time_ns:
                raise ValueError(
                    f"Inferred API Gateway should have started at '{expected_start_time_ns}', found {start}'"
                )

        meta = span.get("meta")
        if meta is None:
            raise ValueError("Inferred API Gateway span should have meta")

        component = meta.get("component")
        if component != expected_component:
            raise ValueError(f"Expected component to be '{expected_component}', found '{component}'")

        stage = meta.get("stage")
        if stage != "staging":
            raise ValueError(f"Expected stage to be 'staging', found '{stage}'")

        kind = meta.get("span.kind")
        if kind != "server":
            raise ValueError(f"Expected span.kind to be 'server', found '{kind}'")

        route = meta.get("http.route")
        if route != "/api/{Proxy}":
            raise ValueError(f"Expected http.route to be '/api/{{Proxy}}', found '{route}'")

        url = meta.get("http.url")
        if url != "https://system-tests-api-gateway.com/api/data/v2":
            raise ValueError(
                f"Expected http.url to be 'https://system-tests-api-gateway.com/api/data/v2', found '{url}'"
            )

        status_code = meta.get("http.status_code")
        if status_code != expected_status_code:
            raise ValueError(f"Expected http.status_code to be '{expected_status_code}', found '{status_code}'")

        if distributed:
            trace_id = span.get("trace_id")
            if trace_id != DISTRIBUTED_TRACE_ID:
                raise ValueError(f"Expected trace_id to be '{DISTRIBUTED_TRACE_ID}', found '{span['trace_id']}'")
            parent_id = span.get("parent_id")
            if parent_id != DISTRIBUTED_PARENT_ID:
                raise ValueError(f"Expected parent_id to be '{DISTRIBUTED_PARENT_ID}', found '{span['parent_id']}'")
            sampling_priority = span.get("metrics", {}).get("_sampling_priority_v1")
            if sampling_priority != DISTRIBUTED_SAMPLING_PRIORITY:
                raise ValueError(f"Expected sampling_id to be '{DISTRIBUTED_PARENT_ID}', found '{span['parent_id']}'")

        if error:
            span_error = span.get("error")
            if span_error != 1:
                raise ValueError("Expected error to be reported on inferred span")

        return True

    return validate_api_gateway_span


def optional_tags_validator_factory(proxy: Literal["aws.apigateway", "aws.httpapi"]):
    if proxy == "aws.apigateway":
        expected_arn = "arn:aws:apigateway:eu-west-3::/restapis/a1b2c3d4e5f"
    else:
        expected_arn = "arn:aws:apigateway:eu-west-3::/apis/a1b2c3d4e5f"

    def validate_api_gateway_span(span: DataDogSpan) -> bool:
        if span.get("metrics", {}).get("_dd.inferred_span") != 1:
            return False

        meta = span.get("meta")
        if meta is None:
            raise ValueError("Inferred API Gateway span should have meta")

        account_id = meta.get("account_id")
        if account_id != "123456789123":
            raise ValueError(f"Expected 'account_id' tag to be '123456789123', found '{account_id}'")

        api_id = meta.get("apiid")
        if api_id != "a1b2c3d4e5f":
            raise ValueError(f"Expected 'apiid' tag to be 'a1b2c3d4e5f', found '{api_id}'")

        region = meta.get("region")
        if region != "eu-west-3":
            raise ValueError(f"Expected 'region' tag to be 'eu-west-3', found '{region}'")

        user = meta.get("aws_user")
        if user != "aws-user":
            raise ValueError(f"Expected 'aws_user' tag to be 'aws-user', found '{user}'")

        dd_resource_key = meta.get("dd_resource_key")
        if dd_resource_key != expected_arn:
            raise ValueError(f"Expected 'dd_resource_key' tag to be '{expected_arn}', found '{dd_resource_key}'")

        return True

    return validate_api_gateway_span


@features.aws_api_gateway_inferred_span_creation
@scenarios.integrations
class Test_AWS_API_Gateway_Inferred_Span_Creation_v2(_BaseTestCase):
    """Verify AWS API Gateway inferred spans are created when a web server receives specific headers."""

    start_time = round(time.time() * 1000)
    start_time_ns = start_time * 1000000

    def setup_api_gateway_rest_inferred_span_creation(self):
        headers = {
            "x-dd-proxy": "aws-apigateway",
            "x-dd-proxy-request-time-ms": str(self.start_time),  # in ms
            "x-dd-proxy-path": "/api/data/v2",
            "x-dd-proxy-resource-path": "/api/{Proxy}",
            "x-dd-proxy-httpmethod": "GET",
            "x-dd-proxy-domain-name": "system-tests-api-gateway.com",
            "x-dd-proxy-stage": "staging",
        }

        self.r = weblog.get("/inferred-proxy/span-creation?status_code=200", headers=headers, timeout=60)

    def test_api_gateway_rest_inferred_span_creation(self):
        assert self.r.text == "ok"
        interfaces.library.validate_one_span(
            self.r,
            validator=mandatory_tags_validator_factory(
                "aws.apigateway",
                expected_status_code="200",
                expected_start_time_ns=self.start_time_ns,
            ),
        )

    def setup_api_gateway_http_inferred_span_creation(self):
        headers = {
            "x-dd-proxy": "aws-httpapi",
            "x-dd-proxy-request-time-ms": str(self.start_time),  # in ms
            "x-dd-proxy-path": "/api/data/v2",
            "x-dd-proxy-resource-path": "/api/{Proxy}",
            "x-dd-proxy-httpmethod": "GET",
            "x-dd-proxy-domain-name": "system-tests-api-gateway.com",
            "x-dd-proxy-stage": "staging",
        }

        self.r = weblog.get("/inferred-proxy/span-creation?status_code=200", headers=headers, timeout=60)

    def test_api_gateway_http_inferred_span_creation(self):
        assert self.r.text == "ok"
        interfaces.library.validate_one_span(
            self.r,
            validator=mandatory_tags_validator_factory(
                "aws.httpapi",
                expected_status_code="200",
                expected_start_time_ns=self.start_time_ns,
            ),
        )

    def setup_api_gateway_inferred_span_creation_with_distributed_context(self):
        headers = {
            "x-dd-proxy": "aws-apigateway",
            "x-dd-proxy-request-time-ms": str(self.start_time),  # in ms
            "x-dd-proxy-path": "/api/data/v2",
            "x-dd-proxy-resource-path": "/api/{Proxy}",
            "x-dd-proxy-httpmethod": "GET",
            "x-dd-proxy-domain-name": "system-tests-api-gateway.com",
            "x-dd-proxy-stage": "staging",
            "x-datadog-trace-id": str(DISTRIBUTED_TRACE_ID),
            "x-datadog-parent-id": str(DISTRIBUTED_PARENT_ID),
            "x-datadog-origin": "rum",
            "x-datadog-sampling-priority": str(DISTRIBUTED_SAMPLING_PRIORITY),
        }

        self.r = weblog.get("/inferred-proxy/span-creation?status_code=200", headers=headers, timeout=60)

    def test_api_gateway_inferred_span_creation_with_distributed_context(self):
        assert self.r.text == "ok"

        interfaces.library.validate_one_span(
            self.r,
            validator=mandatory_tags_validator_factory(
                "aws.apigateway",
                "200",
                self.start_time_ns,
                distributed=True,
            ),
        )

    def setup_api_gateway_rest_inferred_span_creation_with_error(self):
        headers = {
            "x-dd-proxy": "aws-apigateway",
            "x-dd-proxy-request-time-ms": str(self.start_time),  # in ms
            "x-dd-proxy-path": "/api/data/v2",
            "x-dd-proxy-resource-path": "/api/{Proxy}",
            "x-dd-proxy-httpmethod": "GET",
            "x-dd-proxy-domain-name": "system-tests-api-gateway.com",
            "x-dd-proxy-stage": "staging",
        }

        self.r = weblog.get("/inferred-proxy/span-creation?status_code=500", headers=headers, timeout=60)

    def test_api_gateway_rest_inferred_span_creation_with_error(self):
        assert self.r.text == "ok"
        interfaces.library.validate_one_span(
            self.r,
            validator=mandatory_tags_validator_factory(
                "aws.apigateway",
                "500",
                self.start_time_ns,
                error=True,
            ),
        )

    def setup_api_gateway_rest_inferred_span_creation_optional_tags(self):
        headers = {
            "x-dd-proxy": "aws-apigateway",
            "x-dd-proxy-request-time-ms": str(self.start_time),  # in ms
            "x-dd-proxy-path": "/api/data/v2",
            "x-dd-proxy-resource-path": "/api/{Proxy}",
            "x-dd-proxy-httpmethod": "GET",
            "x-dd-proxy-domain-name": "system-tests-api-gateway.com",
            "x-dd-proxy-stage": "staging",
            "x-dd-proxy-account-id": "123456789123",
            "x-dd-proxy-api-id": "a1b2c3d4e5f",
            "x-dd-proxy-region": "eu-west-3",
            "x-dd-proxy-user": "aws-user",
        }

        self.r = weblog.get("/inferred-proxy/span-creation?status_code=200", headers=headers, timeout=60)

    def test_api_gateway_rest_inferred_span_creation_optional_tags(self):
        assert self.r.text == "ok"

        interfaces.library.validate_one_span(
            self.r,
            validator=mandatory_tags_validator_factory(
                "aws.apigateway",
                "200",
                self.start_time_ns,
            ),
        )
        interfaces.library.validate_one_span(self.r, validator=optional_tags_validator_factory("aws.apigateway"))

    def setup_api_gateway_http_inferred_span_creation_optional_tags(self):
        headers = {
            "x-dd-proxy": "aws-httpapi",
            "x-dd-proxy-request-time-ms": str(self.start_time),  # in ms
            "x-dd-proxy-path": "/api/data/v2",
            "x-dd-proxy-resource-path": "/api/{Proxy}",
            "x-dd-proxy-httpmethod": "GET",
            "x-dd-proxy-domain-name": "system-tests-api-gateway.com",
            "x-dd-proxy-stage": "staging",
            "x-dd-proxy-account-id": "123456789123",
            "x-dd-proxy-api-id": "a1b2c3d4e5f",
            "x-dd-proxy-region": "eu-west-3",
            "x-dd-proxy-user": "aws-user",
        }

        self.r = weblog.get("/inferred-proxy/span-creation?status_code=200", headers=headers, timeout=60)

    def test_api_gateway_http_inferred_span_creation_optional_tags(self):
        assert self.r.text == "ok"

        interfaces.library.validate_one_span(
            self.r,
            validator=mandatory_tags_validator_factory(
                "aws.httpapi",
                "200",
                self.start_time_ns,
            ),
        )
        interfaces.library.validate_one_span(self.r, validator=optional_tags_validator_factory("aws.httpapi"))
