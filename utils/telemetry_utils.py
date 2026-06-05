from utils._context.component_version import ComponentVersion


# Distinct, recognizable sentinel values for each OTLP header variant. Each is set as the value of a
# header in the corresponding OTEL_EXPORTER_OTLP_*_HEADERS environment variable. None of these values
# may appear in any configuration telemetry value: tracers either omit the configuration entry or
# redact its value, so the configured header value is never reported.
OTLP_HEADER_SENTINELS: dict[str, str] = {
    "OTEL_EXPORTER_OTLP_HEADERS": "SENTINEL_OTLP_BASE",
    "OTEL_EXPORTER_OTLP_TRACES_HEADERS": "SENTINEL_OTLP_TRACES",
    "OTEL_EXPORTER_OTLP_METRICS_HEADERS": "SENTINEL_OTLP_METRICS",
    "OTEL_EXPORTER_OTLP_LOGS_HEADERS": "SENTINEL_OTLP_LOGS",
}

# Sentinel values for the Datadog key family. Set as the value of the corresponding environment
# variable; the value must not appear in any configuration telemetry value.
DD_KEY_SENTINELS: dict[str, str] = {
    "DD_API_KEY": "SENTINEL_DD_API_KEY",
    "DD_APP_KEY": "SENTINEL_DD_APP_KEY",
}


def assert_no_sensitive_value_in_telemetry(configurations_by_name: dict[str, list[dict]], sentinels: list[str]) -> None:
    """Assert that no configuration telemetry entry reports any of the given sentinel values.

    `configurations_by_name` is the mapping returned by TestAgentAPI.wait_for_telemetry_configurations():
    configuration name -> list of {name, value, origin, ...} entries. A tracer satisfies the invariant
    by either omitting an entry (its value never appears) or redacting it (e.g. `<redacted>`, `<hidden>`),
    so this check passes for both idioms and fails only if a real configured value is reported.
    """
    for config_list in configurations_by_name.values():
        for config in config_list:
            value = str(config.get("value"))
            for sentinel in sentinels:
                assert sentinel not in value, (
                    f"Sensitive value '{sentinel}' must not appear in configuration telemetry, configuration: {config}"
                )


def assert_no_otlp_header_value_in_telemetry(configurations_by_name: dict[str, list[dict]]) -> None:
    """Assert that no OTLP header sentinel value appears in any configuration telemetry value."""
    assert_no_sensitive_value_in_telemetry(configurations_by_name, list(OTLP_HEADER_SENTINELS.values()))


class TelemetryUtils:
    test_loaded_dependencies = {
        "dotnet": {"NodaTime": False},
        "nodejs": {"glob": False},
        "java": {"org.apache.httpcomponents:httpclient": False},
        "ruby": {"bundler": False},
        "python": {"requests": False},
        "golang": {"github.com/tinylib/msgp": False},
        "php": {"weblog/acme": False},
    }

    @staticmethod
    def get_loaded_dependency(library: str) -> dict[str, bool]:
        return TelemetryUtils.test_loaded_dependencies[library]

    @staticmethod
    def get_dd_appsec_sca_enabled_names(_library: ComponentVersion) -> list[str]:
        return ["DD_APPSEC_SCA_ENABLED", "appsec.sca.enabled", "appsec.sca_enabled"]
