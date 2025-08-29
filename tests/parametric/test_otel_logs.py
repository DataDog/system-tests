import pytest
import logging
import base64

from utils import scenarios, features
from utils.parametric._library_client import LogLevel
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def find_log_record(log_payloads, logger_name: str, log_message: str):
    """Find a specific log record in the log payloads."""
    logger.debug(f"Searching for log record: logger_name='{logger_name}', message='{log_message}'")
    logger.debug(f"Number of log payloads to search: {len(log_payloads)}")

    for payload in log_payloads:
        resource_logs = payload["resource_logs"]
        for resource_log in resource_logs:
            scope_logs = resource_log["scope_logs"]
            for scope_log in scope_logs:
                scope_name = scope_log.get("scope", {}).get("name") if scope_log.get("scope") else None
                if scope_name == logger_name:
                    log_records = scope_log["log_records"]
                    for log_record in log_records:
                        record_message = log_record.get("body", {}).get("string_value", "")
                        if record_message == log_message:
                            return log_record
    return None


def find_resource(log_payloads, logger_name: str, log_message: str):
    """Extract resource from captured logs."""
    for payload in log_payloads:
        resource_logs = payload["resource_logs"]
        for resource_log in resource_logs:
            scope_logs = resource_log["scope_logs"]
            for scope_log in scope_logs:
                scope_name = scope_log.get("scope", {}).get("name") if scope_log.get("scope") else None
                if scope_name == logger_name:
                    log_records = scope_log["log_records"]
                    for log_record in log_records:
                        record_message = log_record.get("body", {}).get("string_value", "")
                        if record_message == log_message:
                            logger.debug(f"Found resource_log: {resource_log}")
                            return resource_log["resource"]
    return None


def find_attributes(proto_object):
    """Extract attributes from proto object."""
    attributes = {}
    for attribute in proto_object.get("attributes", []):
        attributes[attribute.get("key")] = list(attribute.get("value", {}).values())[0]
    return attributes


@pytest.fixture
def otlp_endpoint_library_env(library_env, env_name, test_agent_container_name, test_agent_otlp_grpc_port):
    """Set up a custom endpoint for OTLP logs."""
    prev_value = library_env.get(env_name)
    library_env[env_name] = f"http://{test_agent_container_name}:{test_agent_otlp_grpc_port}"
    yield library_env
    library_env[env_name] = prev_value


@features.otel_logs_enabled
@scenarios.parametric
class Test_FR01_Enable_OTLP_Log_Collection:
    """FR01: OTLP Log Collection Enable/Disable Tests"""

    @pytest.mark.parametrize(
        "library_env",
        [
            {"DD_LOGS_OTEL_ENABLED": "true", "DD_TRACE_DEBUG": None},
        ],
    )
    def test_otlp_logs_enabled(self, test_agent, test_library, library_env):
        """OTLP logs are emitted when enabled."""
        with test_library as library:
            library.write_log("Test log", LogLevel.INFO, "test_logger", 0)

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        assert find_log_record(log_payloads, "test_logger", "Test log") is not None

    @pytest.mark.parametrize(
        "library_env",
        [
            {"DD_LOGS_OTEL_ENABLED": "false", "DD_TRACE_DEBUG": None},
            {"DD_LOGS_OTEL_ENABLED": None, "DD_TRACE_DEBUG": None},
        ],
        ids=["disabled", "default"],
    )
    def test_otlp_logs_disabled(self, test_agent, test_library, library_env):
        """Logs are not emitted when disabled."""
        with test_library as library:
            library.write_log("Test log", LogLevel.INFO, "test_logger", 0)

        with pytest.raises(ValueError):
            test_agent.wait_for_num_log_payloads(1)


@features.otel_logs_enabled
@scenarios.parametric
class Test_FR03_Resource_Attributes:
    """FR03: Resource Attributes Tests"""

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_LOGS_OTEL_ENABLED": "true",
                "OTEL_RESOURCE_ATTRIBUTES": "service.name=service,service.version=2.0,deployment.environment=otelenv",
                "DD_TRACE_DEBUG": None,
            },
        ],
    )
    def test_otel_resource_attributes(self, test_agent, test_library, library_env):
        """OTEL_RESOURCE_ATTRIBUTES values appear in log records."""
        with test_library as library:
            library.write_log("Test log", LogLevel.INFO, "test_logger", 0)

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        resource = find_resource(log_payloads, "test_logger", "Test log")
        attrs = find_attributes(resource)

        assert attrs.get("service.name") == "service"
        assert attrs.get("service.version") == "2.0"
        assert attrs.get("deployment.environment") == "otelenv"

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_LOGS_OTEL_ENABLED": "true",
                "OTEL_RESOURCE_ATTRIBUTES": "service.name=service,service.version=2.0,deployment.environment=otelenv",
                "DD_SERVICE": "ddservice",
                "DD_ENV": "ddenv",
                "DD_VERSION": "ddver",
                "DD_TRACE_DEBUG": None,
            },
        ],
    )
    def test_dd_env_vars_override_otel(self, test_agent, test_library, library_env):
        """DD_ env vars override OTEL_RESOURCE_ATTRIBUTES."""
        with test_library as library:
            library.write_log("Test log", LogLevel.INFO, "test_logger", 0)

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        resource = find_resource(log_payloads, "test_logger", "Test log")
        attrs = find_attributes(resource)

        assert attrs.get("service.name") == "ddservice"
        assert attrs.get("service.version") == "ddver"
        assert attrs.get("deployment.environment") == "ddenv"


@features.otel_logs_enabled
@scenarios.parametric
class Test_FR04_Trace_Span_IDs:
    """FR04: Trace and Span ID Injection Tests"""

    @pytest.mark.parametrize(
        "library_env",
        [
            {"DD_LOGS_OTEL_ENABLED": "true", "DD_TRACE_DEBUG": None},
        ],
    )
    def test_dd_span_context_injection(self, test_agent, test_library, library_env):
        """Trace and span IDs from Datadog spans appear in log records."""
        with test_library as library, library.dd_start_span("test_span") as span:
            library.write_log("Test log", LogLevel.INFO, "test_logger", 0, span_id=span.span_id)

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        log_record = find_log_record(log_payloads, "test_logger", "Test log")

        span_id = int(base64.b64decode(log_record["span_id"]).hex(), 16)
        trace_id = int(base64.b64decode(log_record["trace_id"]).hex(), 16)

        assert span_id == span.span_id
        assert trace_id == span.trace_id

    @pytest.mark.parametrize(
        "library_env",
        [
            {"DD_LOGS_OTEL_ENABLED": "true", "DD_TRACE_DEBUG": None},
        ],
    )
    def test_otel_span_context_injection(self, test_agent, test_library):
        """Trace and span IDs from OpenTelemetry spans appear in log records."""
        with test_library as library, library.otel_start_span("test_span") as span:
            library.write_log("Test log", LogLevel.INFO, "test_logger", 0, span_id=span.span_id)

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        log_record = find_log_record(log_payloads, "test_logger", "Test log")

        span_id = int(base64.b64decode(log_record["span_id"]).hex(), 16)
        trace_id = int(base64.b64decode(log_record["trace_id"]).hex(), 16)

        assert span_id == span.span_id
        assert trace_id == span.trace_id


@features.otel_logs_enabled
@scenarios.parametric
class Test_FR05_Custom_Endpoints:
    """FR05: Custom OTLP Endpoint Tests"""

    @pytest.mark.parametrize(
        ("library_env", "env_name", "test_agent_otlp_grpc_port"),
        [
            (
                {"DD_LOGS_OTEL_ENABLED": "true", "DD_TRACE_DEBUG": None},
                "OTEL_EXPORTER_OTLP_ENDPOINT",
                4320,
            ),
        ],
    )
    def test_otlp_custom_endpoint(
        self, library_env, env_name, test_agent_otlp_grpc_port, otlp_endpoint_library_env, test_agent, test_library
    ):
        """Logs are exported to custom OTLP endpoint."""
        with test_library as library:
            library.write_log("Test log", LogLevel.INFO, "test_logger", 0)

        assert urlparse(library_env[env_name]).port == 4320, f"Expected port 4321 in {urlparse(library_env[env_name])}"
        log_payloads = test_agent.wait_for_num_log_payloads(1)
        assert find_log_record(log_payloads, "test_logger", "Test log") is not None

    @pytest.mark.parametrize(
        ("library_env", "env_name", "test_agent_otlp_grpc_port"),
        [
            (
                {
                    "DD_LOGS_OTEL_ENABLED": "true",
                    "DD_TRACE_DEBUG": None,
                    "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT": "http://test_agent_container_name:4320",
                },
                "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
                4321,
            ),
        ],
    )
    def test_otlp_logs_custom_endpoint(
        self, library_env, env_name, test_agent_otlp_grpc_port, otlp_endpoint_library_env, test_agent, test_library
    ):
        """Logs are exported to custom OTLP logs endpoint."""
        with test_library as library:
            library.write_log("Test log", LogLevel.INFO, "test_logger", 0)

        assert urlparse(library_env[env_name]).port == 4321, f"Expected port 4321 in {urlparse(library_env[env_name])}"
        log_payloads = test_agent.wait_for_num_log_payloads(1)
        assert find_log_record(log_payloads, "test_logger", "Test log") is not None


@features.otel_logs_enabled
@scenarios.parametric
class Test_FR06_OTLP_Protocols:
    """FR06: OTLP Protocol Tests"""

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_LOGS_OTEL_ENABLED": "true",
                "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
                "DD_TRACE_DEBUG": None,
            },
            {
                "DD_LOGS_OTEL_ENABLED": "true",
                "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc",
                "DD_TRACE_DEBUG": None,
            },
        ],
        ids=["http_protobuf", "grpc"],
    )
    def test_otlp_protocols(self, test_agent, test_library, library_env):
        """OTLP logs are emitted in expected format."""
        with test_library as library:
            library.write_log("Test log", LogLevel.INFO, "test_logger", 0)

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        assert find_log_record(log_payloads, "test_logger", "Test log") is not None


@features.otel_logs_enabled
@scenarios.parametric
class Test_FR07_Host_Name:
    """FR07: Host Name Attribute Tests"""

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_LOGS_OTEL_ENABLED": "true",
                "DD_HOSTNAME": "ddhostname",
                "DD_TRACE_REPORT_HOSTNAME": "true",
                "DD_TRACE_DEBUG": None,
            },
        ],
    )
    def test_hostname_from_dd_hostname(self, test_agent, test_library, library_env):
        """host.name is set from DD_HOSTNAME."""
        with test_library as library:
            library.write_log("Test log", LogLevel.INFO, "test_logger", 0)

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        resource = find_resource(log_payloads, "test_logger", "Test log")
        attrs = find_attributes(resource)

        assert attrs.get("host.name") == "ddhostname"

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_LOGS_OTEL_ENABLED": "true",
                "OTEL_RESOURCE_ATTRIBUTES": "host.name=otelenv-host",
                "DD_HOSTNAME": "ddhostname",
                "DD_TRACE_REPORT_HOSTNAME": "true",
                "DD_TRACE_DEBUG": None,
            },
        ],
    )
    def test_hostname_from_otel_resources(self, test_agent, test_library, library_env):
        """OTEL_RESOURCE_ATTRIBUTES host.name takes precedence over DD_HOSTNAME."""
        with test_library as library:
            library.write_log("Test log", LogLevel.INFO, "test_logger", 0)

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        resource = find_resource(log_payloads, "test_logger", "Test log")
        attrs = find_attributes(resource)

        assert attrs.get("host.name") == "otelenv-host"

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_LOGS_OTEL_ENABLED": "true",
                "DD_TRACE_REPORT_HOSTNAME": "false",
                "DD_TRACE_DEBUG": None,
            },
            {
                "DD_LOGS_OTEL_ENABLED": "true",
                "DD_TRACE_REPORT_HOSTNAME": None,
                "DD_TRACE_DEBUG": None,
            },
        ],
        ids=["disabled", "default"],
    )
    def test_hostname_omitted(self, test_agent, test_library, library_env):
        """host.name is omitted when not configured."""
        with test_library as library:
            library.write_log("Test log", LogLevel.INFO, "test_logger", 0)

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        resource = find_resource(log_payloads, "test_logger", "Test log")
        attrs = find_attributes(resource)

        assert "host.name" not in attrs


@features.otel_logs_enabled
@scenarios.parametric
class Test_FR08_Custom_Headers:
    """FR08: Custom HTTP Headers Tests"""

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_LOGS_OTEL_ENABLED": "true",
                "DD_TRACE_DEBUG": None,
                "OTEL_EXPORTER_OTLP_HEADERS": "api-key=key,other-config-value=value",
                "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
            },
        ],
    )
    def test_custom_http_headers_included_in_otlp_export(self, test_agent, test_library, library_env):
        """Custom headers from OTEL_EXPORTER_OTLP_HEADERS appear in requests."""
        with test_library as library:
            library.write_log("Test log", LogLevel.INFO, "test_logger", 0)

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        assert find_log_record(log_payloads, "test_logger", "Test log") is not None

        requests = test_agent.requests()
        logs_request = [r for r in requests if r["url"].endswith("/v1/logs")]
        assert logs_request, f"Expected logs request, got {requests}"
        assert logs_request[0]["headers"].get("api-key") == "key", f"Expected api-key, got {logs_request[0]['headers']}"
        assert (
            logs_request[0]["headers"].get("other-config-value") == "value"
        ), f"Expected other-config-value, got {logs_request[0]['headers']}"

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_LOGS_OTEL_ENABLED": "true",
                "DD_TRACE_DEBUG": None,
                "OTEL_EXPORTER_OTLP_LOGS_HEADERS": "api-key=key,other-config-value=value",
                "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
            },
        ],
    )
    def test_custom_logs_http_headers_included_in_otlp_export(self, test_agent, test_library, library_env):
        """Custom headers from OTEL_EXPORTER_OTLP_LOGS_HEADERS appear in requests."""
        with test_library as library:
            library.write_log("Test log", LogLevel.INFO, "test_logger", 0)

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        assert find_log_record(log_payloads, "test_logger", "Test log") is not None

        requests = test_agent.requests()
        logs_request = [r for r in requests if r["url"].endswith("/v1/logs")]
        assert logs_request, f"Expected logs request, got {requests}"
        assert logs_request[0]["headers"].get("api-key") == "key", f"Expected api-key, got {logs_request[0]['headers']}"
        assert (
            logs_request[0]["headers"].get("other-config-value") == "value"
        ), f"Expected other-config-value, got {logs_request[0]['headers']}"


@features.otel_logs_enabled
@scenarios.parametric
class Test_FR09_Log_Injection:
    """FR09: Log Injection Tests"""

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_LOGS_OTEL_ENABLED": "true",
                "DD_SERVICE": "testservice",
                "DD_ENV": "testenv",
                "DD_VERSION": "1.0.0",
                "DD_TRACE_DEBUG": None,
            },
        ],
    )
    def test_log_injection_disabled_when_otel_enabled(self, test_agent, test_library, library_env):
        """Log injection is disabled when OpenTelemetry Logs support is enabled."""
        with test_library as library, library.dd_start_span("test_span") as span:
            library.write_log("Test log", LogLevel.INFO, "test_logger", 0, span_id=span.span_id)

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        log_record = find_log_record(log_payloads, "test_logger", "Test log")
        resource = find_resource(log_payloads, "test_logger", "Test log")

        # Verify trace correlation works
        assert log_record.get("span_id") is not None
        assert log_record.get("trace_id") is not None

        # Verify service/env/version are ONLY in resource attributes
        resource_attrs = find_attributes(resource)
        assert resource_attrs.get("service.name") == "testservice"
        assert resource_attrs.get("deployment.environment") == "testenv"
        assert resource_attrs.get("service.version") == "1.0.0"

        # Verify no duplication in log record attributes
        log_attrs = find_attributes(log_record)
        for ddattr in ("dd.service", "dd.env", "dd.version"):
            assert (
                ddattr not in log_attrs
            ), f"Found {ddattr} in log attributes, should not duplicate resource attributes"


@features.otel_logs_enabled
@scenarios.parametric
class Test_FR10_Timeout_Configuration:
    """FR10: Timeout Configuration Tests"""

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_LOGS_OTEL_ENABLED": "true",
                "DD_TRACE_DEBUG": None,
            },
        ],
    )
    def test_default_timeout(self, test_agent, test_library, library_env):
        """SDK uses default timeout when no timeout env vars are set."""
        with test_library as library:
            library.write_log("Test log with default timeout", LogLevel.INFO, "test_logger", 0)

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        assert find_log_record(log_payloads, "test_logger", "Test log with default timeout") is not None

        # Wait for telemetry configurations and verify the timeout has the default value of 10s
        configurations_by_name = test_agent.wait_for_telemetry_configurations()
        assert (
            configurations_by_name.get("OTEL_EXPORTER_OTLP_TIMEOUT") == 10000
        ), f"OTEL_EXPORTER_OTLP_TIMEOUT should be 10000, configurations: {configurations_by_name}"
        assert (
            configurations_by_name.get("OTEL_EXPORTER_OTLP_LOGS_TIMEOUT") == 10000
        ), f"OTEL_EXPORTER_OTLP_LOGS_TIMEOUT should be 10000, configurations: {configurations_by_name}"
