import pytest
import base64

from utils import scenarios, features, logger
from utils.parametric._library_client import LogLevel
from urllib.parse import urlparse


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
def otlp_endpoint_library_env(library_env, endpoint_env, test_agent_container_name, test_agent_otlp_grpc_port):
    """Set up a custom endpoint for OTLP logs."""
    prev_value = library_env.get(endpoint_env)
    library_env[endpoint_env] = f"http://{test_agent_container_name}:{test_agent_otlp_grpc_port}"
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
    def test_otlp_logs_enabled(self, test_agent, test_library, library_env):
        """OTLP logs are emitted when enabled."""
        with test_library as library:
            library.write_log("test_otlp_logs_enabled", LogLevel.INFO, "test_logger")

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        assert find_log_record(log_payloads, "test_logger", "test_otlp_logs_enabled") is not None

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
            library.write_log("test_otlp_logs_disabled", LogLevel.INFO, "test_logger")

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
            library.write_log("test_otel_resource_attributes", LogLevel.INFO, "test_logger")

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        resource = find_resource(log_payloads, "test_logger", "test_otel_resource_attributes")
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
            library.write_log("test_dd_env_vars_override_otel", LogLevel.INFO, "test_logger")

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        resource = find_resource(log_payloads, "test_logger", "test_dd_env_vars_override_otel")
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
            library.write_log("test_dd_span_context_injection", LogLevel.INFO, "test_logger", span_id=span.span_id)

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        log_record = find_log_record(log_payloads, "test_logger", "test_dd_span_context_injection")

        span_id = int(base64.b64decode(log_record["span_id"]).hex(), 16)
        trace_id = int(base64.b64decode(log_record["trace_id"]).hex(), 16)

        assert span_id == span.span_id
        assert trace_id == span.trace_id

    @pytest.mark.parametrize(
        "library_env",
        [
            {"DD_TRACE_OTEL_ENABLED": "true", "DD_LOGS_OTEL_ENABLED": "true", "DD_TRACE_DEBUG": None},
        ],
    )
    def test_otel_span_context_injection(self, test_agent, test_library):
        """Trace and span IDs from OpenTelemetry spans appear in log records."""
        with test_library as library, library.otel_start_span("test_span") as span:
            library.write_log("test_otel_span_context_injection", LogLevel.INFO, "test_logger", span_id=span.span_id)

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        log_record = find_log_record(log_payloads, "test_logger", "test_otel_span_context_injection")

        span_id = int(base64.b64decode(log_record["span_id"]).hex(), 16)
        trace_id = int(base64.b64decode(log_record["trace_id"]).hex(), 16)

        assert span_id == span.span_id
        assert trace_id == span.trace_id


@features.otel_logs_enabled
@scenarios.parametric
class Test_FR05_Custom_Endpoints:
    """FR05: Custom OTLP Endpoint Tests"""

    @pytest.mark.parametrize(
        ("library_env", "endpoint_env", "test_agent_otlp_grpc_port"),
        [
            (
                {"DD_LOGS_OTEL_ENABLED": "true", "DD_TRACE_DEBUG": None},
                "OTEL_EXPORTER_OTLP_ENDPOINT",
                4320,
            ),
        ],
    )
    def test_otlp_custom_endpoint(
        self, library_env, endpoint_env, test_agent_otlp_grpc_port, otlp_endpoint_library_env, test_agent, test_library
    ):
        """Logs are exported to custom OTLP endpoint."""
        with test_library as library:
            library.write_log("test_otlp_custom_endpoint", LogLevel.INFO, "test_logger")

        assert (
            urlparse(library_env[endpoint_env]).port == 4320
        ), f"Expected port 4320 in {urlparse(library_env[endpoint_env])}"
        log_payloads = test_agent.wait_for_num_log_payloads(1)
        assert find_log_record(log_payloads, "test_logger", "test_otlp_custom_endpoint") is not None

    @pytest.mark.parametrize(
        ("library_env", "endpoint_env", "test_agent_otlp_grpc_port"),
        [
            (
                {
                    "DD_LOGS_OTEL_ENABLED": "true",
                    "DD_TRACE_DEBUG": None,
                },
                "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
                4321,
            ),
        ],
    )
    def test_otlp_logs_custom_endpoint(
        self, library_env, endpoint_env, test_agent_otlp_grpc_port, otlp_endpoint_library_env, test_agent, test_library
    ):
        """Logs are exported to custom OTLP logs endpoint."""
        with test_library as library:
            library.write_log("test_otlp_logs_custom_endpoint", LogLevel.INFO, "test_logger")

        assert (
            urlparse(library_env[endpoint_env]).port == 4321
        ), f"Expected port 4321 in {urlparse(library_env[endpoint_env])}"
        log_payloads = test_agent.wait_for_num_log_payloads(1)
        assert find_log_record(log_payloads, "test_logger", "test_otlp_logs_custom_endpoint") is not None


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
            library.write_log("test_otlp_protocols", LogLevel.INFO, "test_logger")

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        assert find_log_record(log_payloads, "test_logger", "test_otlp_protocols") is not None


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
            library.write_log("test_hostname_from_dd_hostname", LogLevel.INFO, "test_logger")

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        resource = find_resource(log_payloads, "test_logger", "test_hostname_from_dd_hostname")
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
            library.write_log("test_hostname_from_otel_resources", LogLevel.INFO, "test_logger")

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        resource = find_resource(log_payloads, "test_logger", "test_hostname_from_otel_resources")
        attrs = find_attributes(resource)

        assert attrs.get("host.name") == "otelenv-host"

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
    def test_hostname_omitted(self, test_agent, test_library, library_env):
        """host.name is omitted when not configured."""
        with test_library as library:
            library.write_log("test_hostname_omitted", LogLevel.INFO, "test_logger")

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        resource = find_resource(log_payloads, "test_logger", "test_hostname_omitted")
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
            library.write_log("test_custom_http_headers_included_in_otlp_export", LogLevel.INFO, "test_logger")

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        assert (
            find_log_record(log_payloads, "test_logger", "test_custom_http_headers_included_in_otlp_export") is not None
        )

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
            library.write_log("test_custom_logs_http_headers_included_in_otlp_export", LogLevel.INFO, "test_logger")

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        assert (
            find_log_record(log_payloads, "test_logger", "test_custom_logs_http_headers_included_in_otlp_export")
            is not None
        )

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
    def test_log_injection_when_otel_enabled(self, test_agent, test_library, library_env):
        """Log injection is disabled when OpenTelemetry Logs support is enabled."""
        with test_library as library, library.dd_start_span("test_span") as span:
            library.write_log(
                "test_log_injection_disabled_when_otel_enabled", LogLevel.INFO, "test_logger", span_id=span.span_id
            )

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        log_record = find_log_record(log_payloads, "test_logger", "test_log_injection_disabled_when_otel_enabled")
        resource = find_resource(log_payloads, "test_logger", "test_log_injection_disabled_when_otel_enabled")

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
        for dd_attr in ("service", "env", "version", "span_id", "trace_id"):
            for log_attr in log_attrs:
                assert (
                    dd_attr not in log_attr
                ), f"Found {dd_attr} in log attributes: {log_attrs}, should not duplicate resource attributes"

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
    def test_log_without_active_span(self, test_agent, test_library, library_env):
        """LogRecords generated without an active span not should have span_id and trace_id."""
        with test_library as library:
            library.write_log("test_log_without_span", LogLevel.INFO, "test_logger")

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        log_record = find_log_record(log_payloads, "test_logger", "test_log_without_span")
        resource = find_resource(log_payloads, "test_logger", "test_log_without_span")

        # Verify no trace correlation when no active span
        assert log_record.get("span_id") is None
        assert log_record.get("trace_id") is None

        # Verify service/env/version are ONLY in resource attributes
        resource_attrs = find_attributes(resource)
        assert resource_attrs.get("service.name") == "testservice"
        assert resource_attrs.get("deployment.environment") == "testenv"
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
    def test_default_timeout(self, test_agent, test_library, library_env):
        """SDK uses default timeout when no timeout env vars are set."""
        with test_library as library:
            library.write_log("test_default_timeout", LogLevel.INFO, "test_logger")

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        assert find_log_record(log_payloads, "test_logger", "test_default_timeout") is not None
        # Wait for telemetry configurations and verify the timeout has the default value of 10s
        configurations_by_name = test_agent.wait_for_telemetry_configurations()
        exporter_timeout = configurations_by_name.get("OTEL_EXPORTER_OTLP_TIMEOUT")
        exporter_logs_timeout = configurations_by_name.get("OTEL_EXPORTER_OTLP_LOGS_TIMEOUT")
        assert exporter_timeout, f"OTEL_EXPORTER_OTLP_TIMEOUT should be set, configurations: {configurations_by_name}"
        assert (
            exporter_logs_timeout
        ), f"OTEL_EXPORTER_OTLP_LOGS_TIMEOUT should be set, configurations: {configurations_by_name}"

        assert (
            exporter_timeout.get("value") == 10000
        ), f"OTEL_EXPORTER_OTLP_TIMEOUT should be 10000, exporter_timeout: {exporter_timeout}"
        assert (
            exporter_logs_timeout.get("value") == 10000
        ), f"OTEL_EXPORTER_OTLP_LOGS_TIMEOUT should be 10000, exporter_logs_timeout: {exporter_logs_timeout}"


@features.otel_logs_enabled
@scenarios.parametric
class Test_FR11_Telemetry:
    """Test OTLP Logs generated via OpenTelemetry API generate telemetry configurations and metrics."""

    @pytest.mark.parametrize(
        ("library_env", "endpoint_env", "test_agent_otlp_grpc_port"),
        [
            (
                {
                    "DD_LOGS_OTEL_ENABLED": "true",
                    "DD_TRACE_DEBUG": None,
                    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",
                    "OTEL_EXPORTER_OTLP_TIMEOUT": "30000",
                    "OTEL_EXPORTER_OTLP_HEADERS": "api-key=key,other-config-value=value",
                    "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc",
                },
                "OTEL_EXPORTER_OTLP_ENDPOINT",
                4320,
            ),
        ],
    )
    def test_telemetry_exporter_configurations(
        self, library_env, endpoint_env, test_agent_otlp_grpc_port, otlp_endpoint_library_env, test_agent, test_library
    ):
        """Test configurations starting with OTEL_EXPORTER_OTLP_ are sent to the instrumentation telemetry intake."""
        with test_library as library:
            library.write_log("test_telemetry_exporter_configurations", LogLevel.INFO, "test_logger")

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        assert find_log_record(log_payloads, "test_logger", "test_telemetry_exporter_configurations") is not None

        configurations_by_name = test_agent.wait_for_telemetry_configurations()

        for expected_env, expected_value in [
            ("OTEL_EXPORTER_OTLP_TIMEOUT", 30000),
            ("OTEL_EXPORTER_OTLP_HEADERS", "api-key=key,other-config-value=value"),
            ("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc"),
            ("OTEL_EXPORTER_OTLP_ENDPOINT", library_env["OTEL_EXPORTER_OTLP_ENDPOINT"]),
        ]:
            config = configurations_by_name.get(expected_env)
            assert config, f"Expected {expected_env} to be set, configurations: {configurations_by_name}"
            assert (
                config.get("value") == expected_value
            ), f"Expected {expected_env} to be {expected_value}, configuration: {config}"

    @pytest.mark.parametrize(
        ("library_env", "endpoint_env", "test_agent_otlp_grpc_port"),
        [
            (
                {
                    "DD_LOGS_OTEL_ENABLED": "true",
                    "DD_TRACE_DEBUG": None,
                    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",
                    "OTEL_EXPORTER_OTLP_LOGS_TIMEOUT": "30000",
                    "OTEL_EXPORTER_OTLP_LOGS_HEADERS": "api-key=key,other-config-value=value",
                    "OTEL_EXPORTER_OTLP_LOGS_PROTOCOL": "grpc",
                },
                "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
                4325,
            ),
        ],
    )
    def test_telemetry_exporter_logs_configurations(
        self, library_env, endpoint_env, test_agent_otlp_grpc_port, otlp_endpoint_library_env, test_agent, test_library
    ):
        """Test Teleemtry configurations starting with OTEL_EXPORTER_OTLP_LOGS_ are sent to the instrumentation telemetry intake."""
        with test_library as library:
            library.write_log("test_telemetry_exporter_logs_configurations", LogLevel.INFO, "test_logger")

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        assert find_log_record(log_payloads, "test_logger", "test_telemetry_exporter_logs_configurations") is not None

        configurations_by_name = test_agent.wait_for_telemetry_configurations()

        for expected_env, expected_value in [
            ("OTEL_EXPORTER_OTLP_LOGS_TIMEOUT", 30000),
            ("OTEL_EXPORTER_OTLP_LOGS_HEADERS", "api-key=key,other-config-value=value"),
            ("OTEL_EXPORTER_OTLP_LOGS_PROTOCOL", "grpc"),
            ("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", library_env["OTEL_EXPORTER_OTLP_LOGS_ENDPOINT"]),
        ]:
            config = configurations_by_name.get(expected_env)
            assert config, f"Expected {expected_env} to be set, configurations: {configurations_by_name}"
            assert (
                config.get("value") == expected_value
            ), f"Expected {expected_env} to be {expected_value}, configuration: {config}"

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_LOGS_OTEL_ENABLED": "true",
                "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",
                "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc",
                "DD_TRACE_DEBUG": None,
            },
        ],
    )
    def test_telemetry_metrics(self, library_env, test_agent, test_library):
        """Test telemetry metrics are sent to the instrumentation telemetry intake."""
        with test_library as library:
            library.write_log("test_telemetry_metrics", LogLevel.INFO, "test_logger")

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        assert find_log_record(log_payloads, "test_logger", "test_telemetry_metrics") is not None

        metrics = test_agent.wait_for_telemetry_metrics("otel.log_records")
        assert metrics, f"Expected metrics, got {metrics}"
        for metric in metrics:
            assert metric.get("type") == "count", f"Expected count, got {metric}"
            assert len(metric.get("points", [])) > 0, f"Expected at least 1 point, got {metric}"
            assert metric.get("common") is True, f"Expected common, got {metric}"
            assert metric.get("tags") is not None, f"Expected tags, got {metric}"
            assert "protocol:grpc" in metric.get("tags")
            assert "encoding:protobuf" in metric.get("tags")
