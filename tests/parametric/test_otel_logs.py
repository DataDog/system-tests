import base64
from collections.abc import Generator
from urllib.parse import urlparse

import pytest

from utils import scenarios, features, logger, irrelevant, context
from utils.docker_fixtures.parametric import LogLevel
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.spec.trace import find_only_span
from utils.docker_fixtures.spec.trace import extract_trace_id_from_otel_span

from .conftest import APMLibrary


def _find_log_components(
    log_payloads: list[dict], logger_name: str, log_message: str
) -> tuple[dict | None, dict | None, dict | None]:
    """Find matching log record, scope_log, and resource_log for a specific logger and message.

    Returns:
        Tuple of (log_record, scope_log, resource_log) or (None, None, None) if not found.

    """
    for payload in log_payloads:
        for resource_log in payload.get("resource_logs", []):
            for scope_log in resource_log.get("scope_logs", []):
                scope_name = scope_log.get("scope", {}).get("name") if scope_log.get("scope") else None
                if scope_name == logger_name:
                    for log_record in scope_log.get("log_records", []):
                        record_message = log_record.get("body", {}).get("string_value", "")
                        if record_message == log_message:
                            return log_record, scope_log, resource_log
    return None, None, None


def find_log_record(log_payloads: list[dict], logger_name: str, log_message: str) -> dict | None:
    """Find a specific log record in the log payloads."""
    logger.debug(f"Searching for log record: logger_name='{logger_name}', message='{log_message}'")
    logger.debug(f"Number of log payloads to search: {len(log_payloads)}")
    log_record, _, _ = _find_log_components(log_payloads, logger_name, log_message)
    return log_record


def find_resource(log_payloads: list[dict], logger_name: str, log_message: str) -> dict | None:
    """Extract resource from captured logs."""
    _, _, resource_log = _find_log_components(log_payloads, logger_name, log_message)
    if resource_log:
        logger.debug(f"Found resource_log: {resource_log}")
        return resource_log.get("resource")
    return None


def find_attributes(proto_object: dict | None) -> dict:
    """Extract attributes from proto object."""
    if proto_object is None:
        return {}
    attributes = {}
    for attribute in proto_object.get("attributes", []):
        attributes[attribute.get("key")] = list(attribute.get("value", {}).values())[0]
    return attributes


def find_scope(log_payloads: list[dict], logger_name: str, log_message: str) -> dict | None:
    """Find ScopeLogs object for a specific log record (includes schema_url at ScopeLogs level)."""
    _, scope_log, _ = _find_log_components(log_payloads, logger_name, log_message)
    return scope_log


@pytest.fixture
def otlp_endpoint_library_env(
    library_env: dict[str, str],
    endpoint_env: str,
    test_agent: TestAgentAPI,
    test_agent_otlp_http_port: int,
    test_agent_otlp_grpc_port: int,
) -> Generator[dict[str, str], None, None]:
    """Set up a custom endpoint for OTLP logs."""
    prev_value = library_env.get(endpoint_env)

    protocol = library_env.get("OTEL_EXPORTER_OTLP_LOGS_PROTOCOL", library_env.get("OTEL_EXPORTER_OTLP_PROTOCOL"))
    if protocol is None:
        raise ValueError(
            "One of the following environment variables must be set in library_env: OTEL_EXPORTER_OTLP_LOGS_PROTOCOL, OTEL_EXPORTER_OTLP_PROTOCOL"
        )

    port = test_agent_otlp_grpc_port if protocol == "grpc" else test_agent_otlp_http_port
    path = "/" if protocol == "grpc" or endpoint_env == "OTEL_EXPORTER_OTLP_ENDPOINT" else "/v1/logs"

    library_env[endpoint_env] = f"http://{test_agent.container_name}:{port}{path}"
    yield library_env
    if prev_value is None:
        del library_env[endpoint_env]
    else:
        library_env[endpoint_env] = prev_value


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
    def test_otlp_logs_enabled(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """OTLP logs are emitted when enabled."""
        with test_library as library:
            library.create_logger("otlp_logs_enabled", LogLevel.INFO)
            library.write_log("otlp_logs_enabled", LogLevel.INFO, "test_otlp_logs_enabled")

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        assert find_log_record(log_payloads, "otlp_logs_enabled", "test_otlp_logs_enabled") is not None

    @pytest.mark.parametrize("library_env", [{"DD_LOGS_OTEL_ENABLED": "false", "DD_TRACE_DEBUG": None}])
    def test_otlp_logs_disabled(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Logs are not emitted when disabled."""
        with test_library as library:
            library.create_logger("otlp_logs_disabled", LogLevel.INFO)
            library.write_log("otlp_logs_disabled", LogLevel.INFO, "test_otlp_logs_disabled")

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
                "OTEL_RESOURCE_ATTRIBUTES": "service.name=service,service.version=2.0,deployment.environment.name=otelenv",
                "DD_TRACE_DEBUG": None,
            },
        ],
    )
    def test_otel_resource_attributes(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """OTEL_RESOURCE_ATTRIBUTES values appear in log records."""
        with test_library as library:
            library.create_logger("otel_resource_attributes", LogLevel.INFO)
            library.write_log("otel_resource_attributes", LogLevel.INFO, "test_otel_resource_attributes")

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        resource = find_resource(log_payloads, "otel_resource_attributes", "test_otel_resource_attributes")
        attrs = find_attributes(resource)

        assert attrs.get("service.name") == "service"
        assert attrs.get("service.version") == "2.0"
        assert attrs.get("deployment.environment.name") == "otelenv"

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_LOGS_OTEL_ENABLED": "true",
                "OTEL_RESOURCE_ATTRIBUTES": "service.name=service,service.version=2.0,deployment.environment.name=otelenv",
                "DD_SERVICE": "ddservice",
                "DD_ENV": "ddenv",
                "DD_VERSION": "ddver",
                "DD_TRACE_DEBUG": None,
            },
        ],
    )
    def test_dd_env_vars_override_otel(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """DD_ env vars override OTEL_RESOURCE_ATTRIBUTES."""
        with test_library as library:
            library.create_logger("dd_env_vars_override_otel", LogLevel.INFO)
            library.write_log("dd_env_vars_override_otel", LogLevel.INFO, "test_dd_env_vars_override_otel")

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        resource = find_resource(log_payloads, "dd_env_vars_override_otel", "test_dd_env_vars_override_otel")
        attrs = find_attributes(resource)

        assert attrs.get("service.name") == "ddservice"
        assert attrs.get("service.version") == "ddver"
        assert attrs.get("deployment.environment.name") == "ddenv"


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
    def test_dd_span_context_injection(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Trace and span IDs from Datadog spans appear in log records."""
        with test_library as library, library.dd_start_span("test_span") as span:
            library.create_logger("dd_span_context_injection", LogLevel.INFO)
            library.write_log(
                "dd_span_context_injection", LogLevel.INFO, "test_dd_span_context_injection", span_id=span.span_id
            )

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        log_record = find_log_record(log_payloads, "dd_span_context_injection", "test_dd_span_context_injection")
        assert log_record is not None

        expected_span_id = base64.b64decode(log_record["span_id"]).hex()
        expected_trace_id = base64.b64decode(log_record["trace_id"]).hex()

        root = find_only_span(test_agent.wait_for_num_traces(1))
        trace_id = extract_trace_id_from_otel_span(root)
        span_id = f"{root['span_id']:016x}"

        assert expected_span_id == span_id, f"Expected span_id {expected_span_id}, got {span_id}, span: {root}"
        assert expected_trace_id == trace_id, f"Expected trace_id {expected_trace_id}, got {trace_id}, span: {root}"

    @pytest.mark.parametrize(
        "library_env",
        [
            {"DD_TRACE_OTEL_ENABLED": "true", "DD_LOGS_OTEL_ENABLED": "true", "DD_TRACE_DEBUG": None},
        ],
    )
    def test_otel_span_context_injection(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Trace and span IDs from OpenTelemetry spans appear in log records."""
        with test_library as library, library.otel_start_span("test_span") as span:
            library.create_logger("otel_span_context_injection", LogLevel.INFO)
            library.write_log(
                "otel_span_context_injection", LogLevel.INFO, "test_otel_span_context_injection", span_id=span.span_id
            )

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        log_record = find_log_record(log_payloads, "otel_span_context_injection", "test_otel_span_context_injection")
        assert log_record is not None

        expected_span_id = base64.b64decode(log_record["span_id"]).hex()
        expected_trace_id = base64.b64decode(log_record["trace_id"]).hex()

        root = find_only_span(test_agent.wait_for_num_traces(1))
        trace_id = extract_trace_id_from_otel_span(root)
        span_id = f"{root['span_id']:016x}"
        assert expected_span_id == span_id, f"Expected span_id {expected_span_id}, got {span_id}, span: {root}"
        assert expected_trace_id == trace_id, f"Expected trace_id {expected_trace_id}, got {trace_id}, span: {root}"


@features.otel_logs_enabled
@scenarios.parametric
class Test_FR05_Custom_Endpoints:
    """FR05: Custom OTLP Endpoint Tests"""

    @pytest.mark.parametrize(
        ("library_env", "endpoint_env", "test_agent_otlp_http_port"),
        [
            (
                {
                    "DD_LOGS_OTEL_ENABLED": "true",
                    "DD_TRACE_DEBUG": None,
                    "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
                },
                "OTEL_EXPORTER_OTLP_ENDPOINT",
                4320,
            ),
        ],
    )
    def test_otlp_custom_endpoint(
        self,
        library_env: dict[str, str],
        endpoint_env: str,
        otlp_endpoint_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """Logs are exported to custom OTLP endpoint."""
        with test_library as library:
            library.create_logger("otlp_custom_endpoint", LogLevel.INFO)
            library.write_log("otlp_custom_endpoint", LogLevel.INFO, "test_otlp_custom_endpoint")

        assert urlparse(library_env[endpoint_env]).port == 4320, (
            f"Expected port 4320 in {urlparse(library_env[endpoint_env])}"
        )
        log_payloads = test_agent.wait_for_num_log_payloads(1)
        assert find_log_record(log_payloads, "otlp_custom_endpoint", "test_otlp_custom_endpoint") is not None


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
    def test_otlp_protocols(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """OTLP logs are emitted in expected format."""
        with test_library as library:
            library.create_logger("otlp_protocols", LogLevel.INFO)
            library.write_log("otlp_protocols", LogLevel.INFO, "test_otlp_protocols")

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        assert find_log_record(log_payloads, "otlp_protocols", "test_otlp_protocols") is not None


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
    @irrelevant(context.library != "python", reason="DD_HOSTNAME is only supported in Python")
    def test_hostname_from_dd_hostname(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """host.name is set from DD_HOSTNAME."""
        with test_library as library:
            library.create_logger("hostname_from_dd_hostname", LogLevel.INFO)
            library.write_log("hostname_from_dd_hostname", LogLevel.INFO, "test_hostname_from_dd_hostname")

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        resource = find_resource(log_payloads, "hostname_from_dd_hostname", "test_hostname_from_dd_hostname")
        attrs = find_attributes(resource)

        assert attrs.get("host.name") == "ddhostname"

    @pytest.mark.parametrize(
        ("library_env", "host_attribute"),
        [
            (
                {
                    "DD_LOGS_OTEL_ENABLED": "true",
                    "OTEL_RESOURCE_ATTRIBUTES": "host.name=otelenv-host",
                    "DD_HOSTNAME": "ddhostname",
                    "DD_TRACE_DEBUG": None,
                },
                "host.name",
            ),
            (
                {
                    "DD_LOGS_OTEL_ENABLED": "true",
                    "OTEL_RESOURCE_ATTRIBUTES": "host.id=otelenv-host",
                    "DD_HOSTNAME": "ddhostname",
                    "DD_TRACE_DEBUG": None,
                },
                "host.id",
            ),
            (
                {
                    "DD_LOGS_OTEL_ENABLED": "true",
                    "OTEL_RESOURCE_ATTRIBUTES": "datadog.host.name=otelenv-host",
                    "DD_HOSTNAME": "ddhostname",
                    "DD_TRACE_DEBUG": None,
                },
                "datadog.host.name",
            ),
        ],
        ids=["host.name", "host.id", "datadog.host.name"],
    )
    def test_hostname_from_otel_resources(
        self, test_agent: TestAgentAPI, test_library: APMLibrary, host_attribute: str
    ):
        """Hostname attributes in OTEL_RESOURCE_ATTRIBUTES takes precedence over DD_HOSTNAME."""
        with test_library as library:
            library.create_logger("hostname_from_otel_resources", LogLevel.INFO)
            library.write_log("hostname_from_otel_resources", LogLevel.INFO, "test_hostname_from_otel_resources")

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        resource = find_resource(log_payloads, "hostname_from_otel_resources", "test_hostname_from_otel_resources")
        attrs = find_attributes(resource)

        assert attrs.get(host_attribute) == "otelenv-host"

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_LOGS_OTEL_ENABLED": "true",
                "DD_HOSTNAME": "ddhostname",
                "DD_TRACE_REPORT_HOSTNAME": "false",
                "DD_TRACE_DEBUG": None,
            },
            {
                "DD_LOGS_OTEL_ENABLED": "true",
                "DD_HOSTNAME": "ddhostname",
                "DD_TRACE_REPORT_HOSTNAME": None,
                "DD_TRACE_DEBUG": None,
            },
            {
                "DD_LOGS_OTEL_ENABLED": "true",
                "DD_TRACE_REPORT_HOSTNAME": None,
                "DD_TRACE_DEBUG": None,
            },
        ],
        ids=["disabled", "hostname_set_via_dd_hostname", "default"],
    )
    def test_hostname_omitted(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """host.name is omitted when not configured."""
        with test_library as library:
            library.create_logger("hostname_omitted", LogLevel.INFO)
            library.write_log("hostname_omitted", LogLevel.INFO, "test_hostname_omitted")

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        resource = find_resource(log_payloads, "hostname_omitted", "test_hostname_omitted")
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
    def test_custom_http_headers_included_in_otlp_export(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Custom headers from OTEL_EXPORTER_OTLP_HEADERS appear in requests."""
        with test_library as library:
            library.create_logger("custom_http_headers_included_in_otlp_export", LogLevel.INFO)
            library.write_log(
                "custom_http_headers_included_in_otlp_export",
                LogLevel.INFO,
                "test_custom_http_headers_included_in_otlp_export",
            )

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        assert (
            find_log_record(
                log_payloads,
                "custom_http_headers_included_in_otlp_export",
                "test_custom_http_headers_included_in_otlp_export",
            )
            is not None
        )

        requests = test_agent.requests()
        logs_request = [r for r in requests if r["url"].endswith("/v1/logs")]
        assert logs_request, f"Expected logs request, got {requests}"
        # Use case-insensitive header lookup
        headers_lower = {k.lower(): v for k, v in logs_request[0]["headers"].items()}
        assert headers_lower.get("api-key") == "key", f"Expected api-key, got {logs_request[0]['headers']}"
        assert headers_lower.get("other-config-value") == "value", (
            f"Expected other-config-value, got {logs_request[0]['headers']}"
        )

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
    def test_custom_logs_http_headers_included_in_otlp_export(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Custom headers from OTEL_EXPORTER_OTLP_LOGS_HEADERS appear in requests."""
        with test_library as library:
            library.create_logger("custom_logs_http_headers_included_in_otlp_export", LogLevel.INFO)
            library.write_log(
                "custom_logs_http_headers_included_in_otlp_export",
                LogLevel.INFO,
                "test_custom_logs_http_headers_included_in_otlp_export",
            )

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        assert (
            find_log_record(
                log_payloads,
                "custom_logs_http_headers_included_in_otlp_export",
                "test_custom_logs_http_headers_included_in_otlp_export",
            )
            is not None
        )

        requests = test_agent.requests()
        logs_request = [r for r in requests if r["url"].endswith("/v1/logs")]
        assert logs_request, f"Expected logs request, got {requests}"
        # Use case-insensitive header lookup
        headers_lower = {k.lower(): v for k, v in logs_request[0]["headers"].items()}
        assert headers_lower.get("api-key") == "key", f"Expected api-key, got {logs_request[0]['headers']}"
        assert headers_lower.get("other-config-value") == "value", (
            f"Expected other-config-value, got {logs_request[0]['headers']}"
        )


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
    def test_log_injection_when_otel_enabled(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Log injection is disabled when OpenTelemetry Logs support is enabled."""
        with test_library as library, library.otel_start_span("test_span") as span:
            library.create_logger("log_injection_when_otel_enabled", LogLevel.INFO)
            library.write_log(
                "log_injection_when_otel_enabled",
                LogLevel.INFO,
                "test_log_injection_disabled_when_otel_enabled",
                span_id=span.span_id,
            )

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        log_record = find_log_record(
            log_payloads, "log_injection_when_otel_enabled", "test_log_injection_disabled_when_otel_enabled"
        )
        assert log_record is not None
        resource = find_resource(
            log_payloads, "log_injection_when_otel_enabled", "test_log_injection_disabled_when_otel_enabled"
        )

        # Verify trace correlation works
        assert log_record.get("span_id") is not None
        assert log_record.get("trace_id") is not None

        # Verify service/env/version are ONLY in resource attributes
        resource_attrs = find_attributes(resource)
        assert resource_attrs.get("service.name") == "testservice"
        assert resource_attrs.get("deployment.environment.name") == "testenv"
        assert resource_attrs.get("service.version") == "1.0.0"

        # Verify no duplication in log record attributes
        log_attrs = find_attributes(log_record)
        for dd_attr in ("service", "env", "version", "span_id", "trace_id"):
            for log_attr in log_attrs:
                assert dd_attr not in log_attr, (
                    f"Found {dd_attr} in log attributes: {log_attrs}, should not duplicate resource attributes"
                )

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
    def test_log_without_active_span(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """LogRecords generated without an active span not should have span_id and trace_id."""
        with test_library as library:
            library.create_logger("log_without_active_span", LogLevel.INFO)
            library.write_log("log_without_active_span", LogLevel.INFO, "test_log_without_span")

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        log_record = find_log_record(log_payloads, "log_without_active_span", "test_log_without_span")
        assert log_record is not None
        resource = find_resource(log_payloads, "log_without_active_span", "test_log_without_span")

        # Verify no trace correlation when no active span
        assert log_record.get("span_id") is None
        assert log_record.get("trace_id") is None

        # Verify service/env/version are ONLY in resource attributes
        resource_attrs = find_attributes(resource)
        assert resource_attrs.get("service.name") == "testservice"
        assert resource_attrs.get("deployment.environment.name") == "testenv"
        assert resource_attrs.get("service.version") == "1.0.0"


@features.otel_logs_enabled
@scenarios.parametric
class Test_FR10_Timeout_Configuration:
    """FR10: Timeout Configuration Tests"""

    @pytest.mark.parametrize(
        "library_env",
        [
            {"DD_LOGS_OTEL_ENABLED": "true", "DD_TRACE_DEBUG": None, "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1"},
        ],
    )
    def test_default_timeout(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """SDK uses default timeout when no timeout env vars are set."""
        with test_library as library:
            library.create_logger("default_timeout", LogLevel.INFO)
            library.write_log("default_timeout", LogLevel.INFO, "test_default_timeout")

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        assert find_log_record(log_payloads, "default_timeout", "test_default_timeout") is not None
        # Wait for telemetry configurations and verify the timeout has the default value of 10s
        configurations_by_name = test_agent.wait_for_telemetry_configurations()

        # Find default configurations (since no env vars are set, these should have default origin)
        exporter_timeout = test_agent.get_telemetry_config_by_origin(
            configurations_by_name, "OTEL_EXPORTER_OTLP_TIMEOUT", "default", fallback_to_first=True
        )
        exporter_logs_timeout = test_agent.get_telemetry_config_by_origin(
            configurations_by_name, "OTEL_EXPORTER_OTLP_LOGS_TIMEOUT", "default", fallback_to_first=True
        )

        assert exporter_timeout is not None, "OTEL_EXPORTER_OTLP_TIMEOUT should be set"
        assert exporter_logs_timeout is not None, "OTEL_EXPORTER_OTLP_LOGS_TIMEOUT should be set"
        assert isinstance(exporter_timeout, dict)
        assert isinstance(exporter_logs_timeout, dict)

        assert str(exporter_timeout.get("value")) == "10000", (
            f"OTEL_EXPORTER_OTLP_TIMEOUT should be 10000, exporter_timeout: {exporter_timeout}"
        )
        assert str(exporter_logs_timeout.get("value")) == "10000", (
            f"OTEL_EXPORTER_OTLP_LOGS_TIMEOUT should be 10000, exporter_logs_timeout: {exporter_logs_timeout}"
        )


@features.otel_logs_enabled
@scenarios.parametric
class Test_FR11_Telemetry:
    """Test OTLP Logs generated via OpenTelemetry API generate telemetry configurations and metrics."""

    @pytest.mark.parametrize(
        ("library_env", "endpoint_env", "test_agent_otlp_http_port"),
        [
            (
                {
                    "DD_LOGS_OTEL_ENABLED": "true",
                    "DD_TRACE_DEBUG": None,
                    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",
                    "OTEL_EXPORTER_OTLP_TIMEOUT": "30000",
                    "OTEL_EXPORTER_OTLP_HEADERS": "api-key=key,other-config-value=value",
                    "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
                },
                "OTEL_EXPORTER_OTLP_ENDPOINT",
                4320,
            ),
        ],
    )
    def test_telemetry_exporter_configurations(
        self,
        library_env: dict[str, str],
        otlp_endpoint_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """Test configurations starting with OTEL_EXPORTER_OTLP_ are sent to the instrumentation telemetry intake."""
        with test_library as library:
            library.create_logger("test_logger", LogLevel.INFO)
            library.write_log("test_logger", LogLevel.INFO, "test_telemetry_exporter_configurations")

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        assert find_log_record(log_payloads, "test_logger", "test_telemetry_exporter_configurations") is not None

        configurations_by_name = test_agent.wait_for_telemetry_configurations()

        for expected_env, expected_value in [
            ("OTEL_EXPORTER_OTLP_TIMEOUT", "30000"),
            ("OTEL_EXPORTER_OTLP_HEADERS", "api-key=key,other-config-value=value"),
            ("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf"),
            ("OTEL_EXPORTER_OTLP_ENDPOINT", library_env["OTEL_EXPORTER_OTLP_ENDPOINT"]),
        ]:
            # Find configuration with env_var origin (since these are set via environment variables)
            config = test_agent.get_telemetry_config_by_origin(
                configurations_by_name, expected_env, "env_var", fallback_to_first=True
            )

            assert isinstance(config, dict), (
                f"No configuration found for '{expected_env}', configurations: {configurations_by_name}"
            )
            assert str(config.get("value", "")).lower() == expected_value.lower(), (
                f"Expected {expected_env} to be {expected_value}, configuration: {config}"
            )

    @pytest.mark.parametrize(
        ("library_env", "endpoint_env", "test_agent_otlp_http_port"),
        [
            (
                {
                    "DD_LOGS_OTEL_ENABLED": "true",
                    "DD_TRACE_DEBUG": None,
                    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",
                    "OTEL_EXPORTER_OTLP_LOGS_TIMEOUT": "30000",
                    "OTEL_EXPORTER_OTLP_LOGS_HEADERS": "api-key=key,other-config-value=value",
                    "OTEL_EXPORTER_OTLP_LOGS_PROTOCOL": "http/protobuf",
                },
                "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
                4325,
            ),
        ],
    )
    def test_telemetry_exporter_logs_configurations(
        self,
        library_env: dict[str, str],
        otlp_endpoint_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """Test Teleemtry configurations starting with OTEL_EXPORTER_OTLP_LOGS_ are sent to the instrumentation telemetry intake."""
        with test_library as library:
            library.create_logger("telemetry_exporter_logs_configurations", LogLevel.INFO)
            library.write_log(
                "telemetry_exporter_logs_configurations", LogLevel.INFO, "test_telemetry_exporter_logs_configurations"
            )

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        assert (
            find_log_record(
                log_payloads, "telemetry_exporter_logs_configurations", "test_telemetry_exporter_logs_configurations"
            )
            is not None
        )

        configurations_by_name = test_agent.wait_for_telemetry_configurations()

        for expected_env, expected_value in [
            ("OTEL_EXPORTER_OTLP_LOGS_TIMEOUT", "30000"),
            ("OTEL_EXPORTER_OTLP_LOGS_HEADERS", "api-key=key,other-config-value=value"),
            ("OTEL_EXPORTER_OTLP_LOGS_PROTOCOL", "http/protobuf"),
            ("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", library_env["OTEL_EXPORTER_OTLP_LOGS_ENDPOINT"]),
        ]:
            # Find configuration with env_var origin (since these are set via environment variables)
            config = test_agent.get_telemetry_config_by_origin(
                configurations_by_name, expected_env, "env_var", fallback_to_first=True
            )
            assert config is not None, f"No configuration found for '{expected_env}'"
            assert isinstance(config, dict)
            assert str(config.get("value")) == expected_value, (
                f"Expected {expected_env} to be {expected_value}, configuration: {config}"
            )

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_LOGS_OTEL_ENABLED": "true",
                "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",
                "OTEL_EXPORTER_OTLP_LOGS_PROTOCOL": "http/protobuf",
                "DD_TRACE_DEBUG": None,
            },
        ],
    )
    def test_telemetry_metrics(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Test telemetry metrics are sent to the instrumentation telemetry intake."""
        with test_library as library:
            library.create_logger("telemetry_metrics", LogLevel.INFO)
            library.write_log("telemetry_metrics", LogLevel.INFO, "test_telemetry_metrics")

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        assert find_log_record(log_payloads, "telemetry_metrics", "test_telemetry_metrics") is not None

        metrics = test_agent.wait_for_telemetry_metrics("otel.log_records")
        assert metrics, f"Expected metrics, got {metrics}"
        for metric in metrics:
            assert metric.get("type") == "count", f"Expected count, got {metric}"
            assert len(metric.get("points", [])) > 0, f"Expected at least 1 point, got {metric}"
            assert metric.get("common") is True, f"Expected common, got {metric}"
            assert metric.get("tags") is not None, f"Expected tags, got {metric}"
            assert "protocol:http" in metric.get("tags")
            assert "encoding:protobuf" in metric.get("tags")


@features.otel_logs_enabled
@scenarios.parametric
class Test_FR12_Log_Levels:
    """FR12: Log Level Tests"""

    @pytest.mark.parametrize(
        ("library_env", "log_level", "expected_severity_text", "expected_severity_number"),
        [
            (
                {"DD_LOGS_OTEL_ENABLED": "true", "DD_TRACE_DEBUG": None},
                LogLevel.DEBUG,
                "DEBUG",
                "SEVERITY_NUMBER_DEBUG",
            ),
            (
                {"DD_LOGS_OTEL_ENABLED": "true", "DD_TRACE_DEBUG": None},
                LogLevel.INFO,
                "INFO",
                "SEVERITY_NUMBER_INFO",
            ),
            (
                {"DD_LOGS_OTEL_ENABLED": "true", "DD_TRACE_DEBUG": None},
                LogLevel.WARN,
                "WARN",
                "SEVERITY_NUMBER_WARN",
            ),
            (
                {"DD_LOGS_OTEL_ENABLED": "true", "DD_TRACE_DEBUG": None},
                LogLevel.ERROR,
                "ERROR",
                "SEVERITY_NUMBER_ERROR",
            ),
        ],
        ids=["debug", "info", "warning", "error"],
    )
    def test_log_levels(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        log_level: LogLevel,
        expected_severity_text: str,
        expected_severity_number: str,
    ):
        """Log records include correct severity_text and severity_number for each log level."""
        message = f"test_log_level_{log_level.value.lower()}"
        with test_library as library:
            library.create_logger("log_levels", level=log_level)
            library.write_log("log_levels", log_level, message)

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        log_record = find_log_record(log_payloads, "log_levels", message)
        assert log_record is not None

        assert log_record.get("severity_text") == expected_severity_text, (
            f"Expected severity_text {expected_severity_text}, got {log_record.get('severity_text')}"
        )
        # severity_number is returned as enum string (e.g., "SEVERITY_NUMBER_DEBUG")
        actual_severity_number = log_record.get("severity_number")
        assert actual_severity_number == expected_severity_number, (
            f"Expected severity_number {expected_severity_number}, got {actual_severity_number}"
        )


@features.otel_logs_enabled
@scenarios.parametric
class Test_FR13_Scope_Fields:
    """FR13: Scope Attributes Tests"""

    @pytest.mark.parametrize(
        "library_env",
        [
            {"DD_LOGS_OTEL_ENABLED": "true", "DD_TRACE_DEBUG": None},
        ],
    )
    def test_scope_attributes_field(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Scope object may include attributes field (optional in OpenTelemetry)."""
        with test_library as library:
            library.create_logger(
                "scope_attributes_field", level=LogLevel.INFO, attributes={"scope.attr": "scope.value"}
            )
            library.write_log("scope_attributes_field", LogLevel.INFO, "test_scope_attributes")

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        scope_log = find_scope(log_payloads, "scope_attributes_field", "test_scope_attributes")
        assert scope_log is not None
        scope = scope_log.get("scope", {})
        assert isinstance(scope.get("attributes"), list), "Scope attributes should be present"
        attributes_list = scope.get("attributes")
        assert attributes_list is not None, "Scope attributes should not be None"
        assert any(attribute.get("key") == "scope.attr" for attribute in attributes_list), (
            "Scope attributes should have scope.attr attribute"
        )

    @pytest.mark.parametrize(
        "library_env",
        [
            {"DD_LOGS_OTEL_ENABLED": "true", "DD_TRACE_DEBUG": None},
        ],
    )
    def test_scope_schema_url_field(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """ScopeLogs may include schema_url field at ScopeLogs level (optional in OpenTelemetry)."""
        with test_library as library:
            library.create_logger(
                "scope_schema_url_field", level=LogLevel.INFO, schema_url="https://opentelemetry.io/schemas/1.21.0"
            )
            library.write_log("scope_schema_url_field", LogLevel.INFO, "test_scope_schema_url")

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        scope_log = find_scope(log_payloads, "scope_schema_url_field", "test_scope_schema_url")
        assert scope_log is not None

        # Scope must have name field
        scope = scope_log.get("scope", {})
        assert "name" in scope, "Scope should have name field"
        assert scope.get("name") == "scope_schema_url_field"

        # schema_url is at ScopeLogs level, not in scope object
        assert "schema_url" in scope_log, "ScopeLogs should have schema_url field when logger created with schema_url"
        assert isinstance(scope_log.get("schema_url"), str), "ScopeLogs schema_url should be a string"
        assert scope_log.get("schema_url") == "https://opentelemetry.io/schemas/1.21.0"

    @pytest.mark.parametrize(
        "library_env",
        [
            {"DD_LOGS_OTEL_ENABLED": "true", "DD_TRACE_DEBUG": None},
        ],
    )
    def test_scope_version_field(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Scope object may include version field (optional in OpenTelemetry)."""
        with test_library as library:
            library.create_logger("scope_version_field", level=LogLevel.INFO, version="1.0.0")
            library.write_log("scope_version_field", LogLevel.INFO, "test_scope_version")

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        scope_log = find_scope(log_payloads, "scope_version_field", "test_scope_version")
        assert scope_log is not None
        scope = scope_log.get("scope", {})
        # Scope must have name field
        assert "name" in scope, "Scope should have name field"
        assert scope.get("name") == "scope_version_field"
        assert "version" in scope, "Scope should have version field when logger created with version"
        assert isinstance(scope.get("version"), str), "Scope version should be a string"
        assert scope.get("version") == "1.0.0"
