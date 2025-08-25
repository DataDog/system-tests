import pytest
import logging
import base64

from utils import scenarios, features
from utils.parametric._library_client import LogLevel

logger = logging.getLogger(__name__)


def find_log_record(log_payloads, logger_name: str, log_message: str):
    """Find a specific log record in the log payloads.

    Args:
        log_payloads: List of log payloads from the test agent
        logger_name: Name of the logger to search for
        log_message: The log message to find

    Returns:
        The matching log record if found, None otherwise

    """
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
    """Extract log correlation attributes from captured logs."""
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
    """Find resource attributes in the resource."""
    attributes = {}
    for attribute in proto_object.get("attributes", []):
        attributes[attribute.get("key")] = list(attribute.get("value", {}).values())[0]
    return attributes


@features.otel_logs_enabled
@scenarios.parametric
class Test_FR01_Enable_OTLP_Log_Collection:
    """FR01: OTLP Log Collection Enable/Disable Tests"""

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_LOGS_OTEL_ENABLED": "true",
                "DD_TRACE_DEBUG": None,
            },
        ],
    )
    def test_fr01_otlp_log_collection_emits_logs_when_otel_logs_enabled_is_true(
        self, test_agent, test_library, library_env
    ):
        """FR01.1: OTLP Logs are emitted when OpenTelemetry Logs support is enabled."""
        log_message = "Test log message - OTLP enabled"
        logger_name = "test_logger"

        with test_library as library:
            library.write_log(log_message, LogLevel.INFO, logger_name, 0)

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        expected_log = find_log_record(log_payloads, logger_name, log_message)
        assert expected_log is not None, f"Log message '{log_message}' not found in payloads {log_payloads}"

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_LOGS_OTEL_ENABLED": "false",
            },
            {
                "DD_LOGS_OTEL_ENABLED": None,
            },
        ],
        ids=["disbale", "default"],
    )
    def test_fr01_otlp_log_collection_does_not_emit_logs_by_default(self, test_agent, test_library):
        """FR01.2: Logs are not emitted when DD_LOGS_OTEL_ENABLED is unset or set to False."""
        log_message = "Test log message - OTLP disabled"
        logger_name = "test_logger"

        with test_library as library:
            library.write_log(log_message, LogLevel.INFO, logger_name, 0)

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
        ids=["otel_attributes"],
    )
    def test_fr03_otel_resources_attributes_applied_to_log_records(self, test_agent, test_library, library_env):
        """FR03.1: OTEL_RESOURCE_ATTRIBUTES values appear in OTLP log records."""
        log_message = "Test log message - OTEL resource attributes"
        logger_name = "test_logger"

        with test_library as library:
            library.write_log(log_message, LogLevel.INFO, logger_name, 0)

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        resource = find_resource(log_payloads, logger_name, log_message)
        assert resource is not None, f"Resource not found for log message '{log_message}': payloads={log_payloads}"
        resource_attributes = find_attributes(resource)
        assert (
            resource_attributes is not None
        ), f"Resource attributes not found for log message '{log_message}': payloads={log_payloads}"

        assert len(resource_attributes) >= 3, f"Expected at least 3 attributes, got {len(resource_attributes)}"
        assert resource_attributes.get("service.name") == "service", resource_attributes
        assert resource_attributes.get("service.version") == "2.0", resource_attributes
        assert resource_attributes.get("deployment.environment") == "otelenv", resource_attributes

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
        ids=["dd_overrides"],
    )
    def test_fr03_dd_env_vars_override_otel_resource_attributes(self, test_agent, test_library, library_env):
        """FR03.2: DD_ env vars (e.g., DD_SERVICE) override conflicting OTEL_RESOURCE_ATTRIBUTES."""
        log_message = "Test log message - DD overrides OTEL"
        logger_name = "test_logger"

        with test_library as library:
            library.write_log(log_message, LogLevel.INFO, logger_name, 0)

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        resource = find_resource(log_payloads, logger_name, log_message)
        assert resource is not None, f"Resource not found for log message '{log_message}': payloads={log_payloads}"

        resource_attributes = find_attributes(resource)
        assert (
            resource_attributes is not None
        ), f"Resource attributes not found for log message '{log_message}': payloads={log_payloads}"

        assert len(resource_attributes) >= 3, f"Expected at least 3 attributes, got {len(resource_attributes)}"
        assert resource_attributes.get("service.name") == "ddservice"
        assert resource_attributes.get("service.version") == "ddver"
        assert resource_attributes.get("deployment.environment") == "ddenv"


@features.otel_logs_enabled
@scenarios.parametric
class Test_FR04_Trace_Span_IDs:
    """FR04: Trace and Span ID Injection Tests"""

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_LOGS_OTEL_ENABLED": "true",
                "DD_TRACE_DEBUG": None,
            },
        ],
    )
    def test_fr04_log_record_includes_trace_and_span_ids_from_dd(self, test_agent, test_library, library_env):
        """FR04.1: When a Datadog span is active, trace_id and span_id appear in the log record."""
        log_message = "Test log with DD span context"
        logger_name = "test_logger"

        with test_library as library, library.dd_start_span("test_span") as span:
            library.write_log(log_message, LogLevel.INFO, logger_name, 0, span_id=span.span_id)

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        expected_log = find_log_record(log_payloads, logger_name, log_message)
        assert expected_log is not None, f"Log message '{log_message}' not found in payloads"
        assert "span_id" in expected_log, f"Span ID not found in log record: {expected_log}"
        assert "trace_id" in expected_log, f"Trace ID not found in log record: {expected_log}"

        assert span.span_id == int(
            base64.b64decode(expected_log["span_id"]).hex(), 16
        ), f"Span ID mismatch: {expected_log['span_id']} can not be decoded to {span.span_id}"
        assert span.trace_id == int(
            base64.b64decode(expected_log["trace_id"]).hex(), 16
        ), f"Trace ID mismatch: {expected_log['trace_id']} can not be decoded to {span.trace_id}"

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_LOGS_OTEL_ENABLED": "true",
                "DD_TRACE_DEBUG": None,
            },
        ],
    )
    def test_fr04_log_record_includes_trace_and_span_ids_from_otel(self, test_agent, test_library):
        """FR04.2: When an OpenTelemetry span is active, trace_id and span_id appear in the log record."""
        log_message = "Test log with DD span context"
        logger_name = "test_logger"

        with test_library as library, library.otel_start_span("test_span") as span:
            library.write_log(log_message, LogLevel.INFO, logger_name, 0, span_id=span.span_id)

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        expected_log = find_log_record(log_payloads, logger_name, log_message)
        assert expected_log is not None, f"Log message '{log_message}' not found in payloads"
        assert "span_id" in expected_log, f"Span ID not found in log record: {expected_log}"
        assert "trace_id" in expected_log, f"Trace ID not found in log record: {expected_log}"

        assert span.span_id == int(
            base64.b64decode(expected_log["span_id"]).hex(), 16
        ), f"Span ID mismatch: {expected_log['span_id']} can not be decoded to {span.span_id}"
        assert span.trace_id == int(
            base64.b64decode(expected_log["trace_id"]).hex(), 16
        ), f"Trace ID mismatch: {expected_log['trace_id']} can not be decoded to {span.trace_id}"


# @features.otel_logs_enabled
# @scenarios.parametric
# class Test_FR05_Custom_Endpoints:
#     """FR05: Custom OTLP Endpoint Tests"""

#     def test_fr05_logs_exported_to_custom_otlp_endpoints(self, test_agent, test_library):
#         """FR05.1: Logs are exported to endpoints defined in OTEL_EXPORTER_OTLP_ENDPOINT."""
#         # This test requires setting OTEL_EXPORTER_OTLP_ENDPOINT to a custom endpoint
#         # and verifying logs are sent there instead of the default agent
#         pass

#     def test_fr05_logs_exported_to_custom_otlp_logs_endpoints(self, test_agent, test_library):
#         """FR05.2: Logs are exported to endpoints defined in OTEL_EXPORTER_OTLP_LOGS_ENDPOINT."""
#         # This test requires setting OTEL_EXPORTER_OTLP_LOGS_ENDPOINT to a custom endpoint
#         # and verifying logs are sent there
#         pass


@features.otel_logs_enabled
@scenarios.parametric
class Test_FR07_OTLP_Protocol:
    """FR07: OTLP v1.7.0 Protocol Tests"""

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
            # {
            #     "DD_LOGS_OTEL_ENABLED": "true",
            #     "OTEL_EXPORTER_OTLP_PROTOCOL": "http/json",
            #     "DD_TRACE_DEBUG": None,
            # },
        ],
        ids=["http_protobuf_fr07", "grpc_fr08"],  # "http_json_fr06"
    )
    def test_otlp_encoding_protocols_v1_7_0(self, test_agent, test_library, library_env):
        """FR07.1: OTLP Logs are emitted in an expected format."""
        log_message = "Test log message - OTLP enabled"
        logger_name = "test_logger"

        with test_library as library:
            library.write_log(log_message, LogLevel.INFO, logger_name, 0)

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        expected_log = find_log_record(log_payloads, logger_name, log_message)
        assert expected_log is not None, f"Log message '{log_message}' not found in payloads {log_payloads}"


@features.otel_logs_enabled
@scenarios.parametric
class Test_FR09_Host_Name:
    """FR09: Host Name Attribute Tests"""

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_LOGS_OTEL_ENABLED": "true",
                "DD_SERVICE": "testservice",
                "DD_HOSTNAME": "ddhostname",
                "DD_TRACE_REPORT_HOSTNAME": "true",
                "DD_TRACE_DEBUG": None,
            },
        ],
    )
    def test_fr9_host_name_set_from_dd_hostname(self, test_agent, test_library, library_env):
        """FR09.1: host.name is set from OTEL_RESOURCE_ATTRIBUTES."""
        log_message = "Test log message - OTEL host.name"
        logger_name = "test_logger"

        with test_library as library:
            library.write_log(log_message, LogLevel.INFO, logger_name, 0)

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        resource = find_resource(log_payloads, logger_name, log_message)
        assert resource is not None, f"Resource not found for log message '{log_message}': payloads={log_payloads}"

        resource_attributes = find_attributes(resource)
        assert (
            resource_attributes is not None
        ), f"Resource attributes not found for log message '{log_message}': payloads={log_payloads}"

        # Verify host.name is set from OTEL_RESOURCE_ATTRIBUTES
        assert (
            resource_attributes.get("host.name") == "ddhostname"
        ), f"Expected host.name='ddhostname', got {resource_attributes.get('host.name')}"
        assert (
            resource_attributes.get("service.name") == "testservice"
        ), f"Expected service.name='testservice', got {resource_attributes.get('service.name')}"

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_LOGS_OTEL_ENABLED": "true",
                "OTEL_RESOURCE_ATTRIBUTES": "host.name=otelenv-host,service.name=testservice",
                "DD_HOSTNAME": "ddhostname",
                "DD_TRACE_REPORT_HOSTNAME": "true",
                "DD_TRACE_DEBUG": None,
            },
        ],
    )
    def test_fr9_host_name_set_from_otel_resources(self, test_agent, test_library, library_env):
        """FR09.2: host.name attribute set by OTEL_RESOURCE_ATTRIBUTES takes precedence over DD_HOSTNAME."""
        log_message = "Test log message - DD_HOSTNAME override"
        logger_name = "test_logger"

        with test_library as library:
            library.write_log(log_message, LogLevel.INFO, logger_name, 0)

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        resource = find_resource(log_payloads, logger_name, log_message)
        assert resource is not None, f"Resource not found for log message '{log_message}': payloads={log_payloads}"

        resource_attributes = find_attributes(resource)
        assert (
            resource_attributes is not None
        ), f"Resource attributes not found for log message '{log_message}': payloads={log_payloads}"

        # Verify OTEL_RESOURCE_ATTRIBUTES takes precedence
        assert (
            resource_attributes.get("host.name") == "otelenv-host"
        ), f"Expected host.name='ddhostname' (DD override), got {resource_attributes.get('host.name')}"
        assert (
            resource_attributes.get("service.name") == "testservice"
        ), f"Expected service.name='testservice', got {resource_attributes.get('service.name')}"

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_LOGS_OTEL_ENABLED": "true",
                "OTEL_RESOURCE_ATTRIBUTES": "service.name=testservice",
                "DD_TRACE_REPORT_HOSTNAME": "false",
                "DD_TRACE_DEBUG": None,
            },
            {
                "DD_LOGS_OTEL_ENABLED": "true",
                "OTEL_RESOURCE_ATTRIBUTES": "service.name=testservice",
                "DD_TRACE_REPORT_HOSTNAME": None,
                "DD_TRACE_DEBUG": None,
            },
        ],
        ids=["hostname_disabled", "hostname_default"],
    )
    def test_fr9_missing_host_name(self, test_agent, test_library, library_env):
        """FR09.3: If host.name is missing from OTEL_RESOURCE_ATTRIBUTES and DD_HOSTNAME is not true, SDKs must omit the host.name attribute."""
        log_message = "Test log message - no host.name"
        logger_name = "test_logger"

        with test_library as library:
            library.write_log(log_message, LogLevel.INFO, logger_name, 0)

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        resource = find_resource(log_payloads, logger_name, log_message)
        assert resource is not None, f"Resource not found for log message '{log_message}': payloads={log_payloads}"

        resource_attributes = find_attributes(resource)
        assert (
            resource_attributes is not None
        ), f"Resource attributes not found for log message '{log_message}': payloads={log_payloads}"

        # Verify host.name is not present in resource attributes
        assert (
            "host.name" not in resource_attributes
        ), f"Expected no host.name attribute, but found: {resource_attributes.get('host.name')}"
        assert (
            resource_attributes.get("service.name") == "testservice"
        ), f"Expected service.name='testservice', got {resource_attributes.get('service.name')}"


# @features.otel_logs_enabled
# @scenarios.parametric
# class Test_FR10_Timeout_Configuration:
#     """FR10: Timeout Configuration Tests"""

#     def test_fr10_otlp_export_timeout_respected_from_env(self, test_agent, test_library):
#         """FR10.1: OTLP export times out according to OTEL_EXPORTER_OTLP_TIMEOUT."""
#         # This test requires setting OTEL_EXPORTER_OTLP_TIMEOUT and testing timeout behavior
#         # Commented out as it involves timeout testing
#         pass

#     def test_fr10_otlp_export_timeout_respected_from_logs_env(self, test_agent, test_library):
#         """FR10.2: OTLP export times out according to OTEL_EXPORTER_OTLP_LOGS_TIMEOUT."""
#         # This test requires setting OTEL_EXPORTER_OTLP_LOGS_TIMEOUT and testing timeout behavior
#         # Commented out as it involves timeout testing
#         pass

#     def test_fr10_default_timeout_used_when_not_set(self, test_agent, test_library):
#         """FR10.3: SDK uses default timeout if no value is set."""
#         # This test requires running without timeout env vars and verifying default behavior
#         pass


# @features.otel_logs_enabled
# @scenarios.parametric
# class Test_FR11_Custom_Headers:
#     """FR11: Custom HTTP Headers Tests"""

#     def test_fr11_custom_http_headers_included_in_otlp_export(self, test_agent, test_library):
#         """FR11.1: Custom headers from OTEL_EXPORTER_OTLP_HEADERS appear in requests."""
#         # This test requires setting OTEL_EXPORTER_OTLP_HEADERS and verifying headers in requests
#         pass

#     def test_fr11_custom_logs_http_headers_included_in_otlp_export(self, test_agent, test_library):
#         """FR11.2: Custom headers from OTEL_EXPORTER_OTLP_LOGS_HEADERS appear in requests."""
#         # This test requires setting OTEL_EXPORTER_OTLP_LOGS_HEADERS and verifying headers in requests
#         pass


@features.otel_logs_enabled
@scenarios.parametric
# @missing_feature(context.library <= "python@3.13.0", reason="Does not disable log injection when OTEL is enabled")
class Test_FR12_Log_Injection:
    """FR12: Log Injection Tests"""

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_LOGS_OTEL_ENABLED": "true",
                "DD_SERVICE": "testservice",
                "DD_ENV": "testenv",
                "DD_VERSION": "1.0.0",
                "DD_LOGS_INJECTION": None,
                "DD_TRACE_DEBUG": None,
            },
        ],
        ids=["otel_enabled"],
    )
    def test_fr12_log_injection_disabled_when_otel_enabled(self, test_agent, test_library, library_env):
        """FR12.1: Log injection is disabled when OpenTelemetry Logs support is enabled."""
        with test_library as library, library.dd_start_span("test_span") as span:
            library.write_log("Test log - OTEL enabled", LogLevel.INFO, "test_logger", 0, span_id=span.span_id)

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        log_record = find_log_record(log_payloads, "test_logger", "Test log - OTEL enabled")
        resource = find_resource(log_payloads, "test_logger", "Test log - OTEL enabled")

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
            ), f"Foud {ddattr} in {log_attrs}, log should not duplicate resource attributes"
