from utils import pytest

from utils import context, logger
from tests.parametric.conftest import APMLibrary

parametrize = pytest.mark.parametrize

# Minimum test agent version that supports client-side stats according to the spec
MIN_AGENT_VERSION_FOR_CSS = "7.65.0"


def enable_tracestats(
    sample_rate: float | None = None, extra_env: dict[str, str] | None = None
) -> pytest.MarkDecorator:
    env = {
        "DD_TRACE_STATS_COMPUTATION_ENABLED": "true",  # reference, dotnet, python, golang
        "DD_TRACE_TRACER_METRICS_ENABLED": "true",  # java
    }
    if context.library == "golang" and context.library.version < "v1.55.0":
        env["DD_TRACE_FEATURES"] = "discovery"
    if sample_rate is not None:
        assert 0 <= sample_rate <= 1.0
        env.update({"DD_TRACE_SAMPLE_RATE": str(sample_rate)})
    if extra_env is not None:
        env.update(extra_env)

    return parametrize("library_env", [env])


telemetry_name_mapping: dict[str, dict[str, str | list[str]]] = {
    "instrumentation_source": {
        "java": "DD_INSTRUMENTATION_SOURCE",
        "nodejs": "instrumentationSource",
    },
    "ssi_injection_enabled": {
        "python": "DD_INJECTION_ENABLED",
        "java": "DD_INJECTION_ENABLED",
        "ruby": "DD_INJECTION_ENABLED",
        "nodejs": "DD_INJECTION_ENABLED",
        "golang": ["DD_INJECTION_ENABLED", "injection_enabled"],
    },
    "ssi_forced_injection_enabled": {
        "python": "DD_INJECT_FORCE",
        "ruby": "DD_INJECT_FORCE",
        "java": "DD_INJECT_FORCE",
        "nodejs": "DD_INJECT_FORCE",
        "golang": ["DD_INJECT_FORCE", "inject_force"],
    },
    "trace_sample_rate": {
        "dotnet": "DD_TRACE_SAMPLE_RATE",
        "java": "DD_TRACE_SAMPLE_RATE",
        "nodejs": "DD_TRACE_SAMPLE_RATE",
        "python": "DD_TRACE_SAMPLE_RATE",
        "ruby": "DD_TRACE_SAMPLE_RATE",
        "golang": ["DD_TRACE_SAMPLE_RATE", "trace_sample_rate"],
    },
    "logs_injection_enabled": {
        "dotnet": "DD_LOGS_INJECTION",
        "nodejs": "DD_LOGS_INJECTION",
        "python": "DD_LOGS_INJECTION",
        "php": "DD_TRACE_LOGS_ENABLED",
        "ruby": "DD_LOGS_INJECTION",
        "golang": ["DD_LOGS_INJECTION", "trace.logs_enabled"],
        "java": "DD_LOGS_INJECTION_ENABLED",
    },
    "trace_header_tags": {
        "dotnet": "DD_TRACE_HEADER_TAGS",
        "nodejs": "DD_TRACE_HEADER_TAGS",
        "python": "DD_TRACE_HEADER_TAGS",
        "golang": ["DD_TRACE_HEADER_TAGS", "trace_header_tags"],
        "java": "DD_TRACE_HEADER_TAGS",
        "ruby": "DD_TRACE_HEADER_TAGS",
    },
    "trace_tags": {
        "dotnet": "DD_TAGS",
        "java": "DD_TRACE_TAGS",
        "nodejs": "DD_TAGS",
        "python": "DD_TAGS",
        "golang": ["DD_TAGS", "trace_tags"],
        "ruby": "DD_TAGS",
    },
    "trace_enabled": {
        "dotnet": "DD_TRACE_ENABLED",
        "java": "DD_TRACE_ENABLED",
        "nodejs": "DD_TRACE_ENABLED",
        "python": "DD_TRACE_ENABLED",
        "ruby": "DD_TRACE_ENABLED",
        "golang": ["DD_TRACE_ENABLED", "trace_enabled"],
    },
    "profiling_enabled": {
        "dotnet": "DD_PROFILING_ENABLED",
        "nodejs": "DD_PROFILING_ENABLED",
        "python": "DD_PROFILING_ENABLED",
        "ruby": "DD_PROFILING_ENABLED",
        "golang": ["DD_PROFILING_ENABLED", "profiling_enabled"],
        "java": "DD_PROFILING_ENABLED",
    },
    "appsec_enabled": {
        "dotnet": "DD_APPSEC_ENABLED",
        "nodejs": "DD_APPSEC_ENABLED",
        "python": "DD_APPSEC_ENABLED",
        "ruby": "DD_APPSEC_ENABLED",
        "golang": ["DD_APPSEC_ENABLED", "appsec_enabled"],
        "java": "DD_APPSEC_ENABLED",
    },
    "data_streams_enabled": {
        "dotnet": "DD_DATA_STREAMS_ENABLED",
        "nodejs": "DD_DATA_STREAMS_ENABLED",
        "python": "DD_DATA_STREAMS_ENABLED",
        "java": "DD_DATA_STREAMS_ENABLED",
        "golang": ["DD_DATA_STREAMS_ENABLED", "data_streams_enabled"],
        "ruby": "DD_DATA_STREAMS_ENABLED",
    },
    "runtime_metrics_enabled": {
        "java": "DD_RUNTIME_METRICS_ENABLED",
        "dotnet": "DD_RUNTIME_METRICS_ENABLED",
        "nodejs": "DD_RUNTIME_METRICS_ENABLED",
        "python": "DD_RUNTIME_METRICS_ENABLED",
        "ruby": "DD_RUNTIME_METRICS_ENABLED",
        "golang": ["DD_RUNTIME_METRICS_ENABLED", "runtime_metrics_enabled"],
    },
    "dynamic_instrumentation_enabled": {
        "java": "DD_DYNAMIC_INSTRUMENTATION_ENABLED",
        "dotnet": "DD_DYNAMIC_INSTRUMENTATION_ENABLED",
        "nodejs": "DD_DYNAMIC_INSTRUMENTATION_ENABLED",
        "python": "DD_DYNAMIC_INSTRUMENTATION_ENABLED",
        "php": "DD_DYNAMIC_INSTRUMENTATION_ENABLED",
        "ruby": "DD_DYNAMIC_INSTRUMENTATION_ENABLED",
        "golang": ["DD_DYNAMIC_INSTRUMENTATION_ENABLED", "dynamic_instrumentation_enabled"],
    },
    "code_origin_enabled": {
        "nodejs": "DD_CODE_ORIGIN_FOR_SPANS_ENABLED",
    },
    "live_debugging_enabled": {
        "nodejs": "DD_DYNAMIC_INSTRUMENTATION_ENABLED",
    },
    "tracing_sampling_rules": {
        "dotnet": "DD_TRACE_SAMPLING_RULES",
        "java": "DD_TRACE_SAMPLING_RULES",
        "nodejs": "DD_TRACE_SAMPLING_RULES",
        "python": "DD_TRACE_SAMPLING_RULES",
        "ruby": "DD_TRACE_SAMPLING_RULES",
        "golang": ["DD_TRACE_SAMPLING_RULES", "tracing_sampling_rules"],
    },
    "trace_debug_enabled": {
        "php": "DD_TRACE_DEBUG",
        "java": "DD_TRACE_DEBUG",
        "ruby": "DD_TRACE_DEBUG",
        "python": "DD_TRACE_DEBUG",
        "golang": ["trace_debug_enabled", "DD_TRACE_DEBUG"],
    },
    "tags": {
        "java": "DD_TRACE_TAGS",
        "dotnet": "DD_TAGS",
        "python": "DD_TAGS",
        "nodejs": "DD_TAGS",
        "golang": ["DD_TAGS", "trace_tags"],
        "ruby": "DD_TAGS",
    },
    "trace_propagation_style": {
        "java": "DD_TRACE_PROPAGATION_STYLE",
        "dotnet": "DD_TRACE_PROPAGATION_STYLE",
        "php": "DD_TRACE_PROPAGATION_STYLE",
        "golang": ["DD_TRACE_PROPAGATION_STYLE", "trace.propagation_style"],
        "ruby": "DD_TRACE_PROPAGATION_STYLE",
    },
}


def _mapped_telemetry_name(apm_telemetry_name: str) -> list[str]:
    if apm_telemetry_name in telemetry_name_mapping:
        lang_mapping = telemetry_name_mapping[apm_telemetry_name]
        mapped_name = lang_mapping.get(context.library.name)
        if mapped_name is not None:
            if isinstance(mapped_name, list):
                return mapped_name
            return [mapped_name]
    return [apm_telemetry_name]


def find_log_components(
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
    log_record, _, _ = find_log_components(log_payloads, logger_name, log_message)
    return log_record


DEFAULT_METER_NAME = "parametric-api"

DEFAULT_METER_VERSION = "1.0.0"

# schema_url is not supported by .NET's System.Diagnostics.Metrics API
DEFAULT_SCHEMA_URL = "https://opentelemetry.io/schemas/1.21.0"

DEFAULT_INSTRUMENT_UNIT = "triggers"

DEFAULT_INSTRUMENT_DESCRIPTION = "test_description"

DEFAULT_SCOPE_ATTRIBUTES = {"scope.attr": "scope.value"}

DEFAULT_MEASUREMENT_ATTRIBUTES = {"test_attr": "test_value"}


def generate_default_counter_data_point(test_library: APMLibrary, instrument_name: str) -> None:
    test_library.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
    test_library.otel_metrics_force_flush()
    test_library.otel_create_counter(
        DEFAULT_METER_NAME, instrument_name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION
    )
    test_library.otel_counter_add(
        DEFAULT_METER_NAME,
        instrument_name,
        DEFAULT_INSTRUMENT_UNIT,
        DEFAULT_INSTRUMENT_DESCRIPTION,
        42,
        DEFAULT_MEASUREMENT_ATTRIBUTES,
    )
    test_library.otel_metrics_force_flush()
