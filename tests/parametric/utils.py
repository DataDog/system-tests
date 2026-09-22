import pytest

from utils import context

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
