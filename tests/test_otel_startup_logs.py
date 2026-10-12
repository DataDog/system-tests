"""Required OTel fields in the tracer's startup configuration JSON.

Required keys are checked even when their settings are left at their defaults.
Every environment variable explicitly set by the scenario also has a value test.
Signal-specific OTLP settings belong to their signal's presence test; shared OTLP
settings have their own test. Key order and existing startup fields are unconstrained.
"""

import json
from pathlib import Path
import re

from utils import context, features, interfaces, pytest, scenarios


def _get_startup_configurations() -> list[dict[str, object]]:
    log_interface = interfaces.library_dotnet_managed if context.library == "dotnet" else interfaces.library_stdout
    # Join raw records to also support pretty-printed JSON split by the log interface.
    logs = "\n".join(record["raw"] for record in log_interface.get_data())
    if context.library == "golang":
        # DD_TRACE_LOG_DIRECTORY redirects recent Go tracers to this captured file.
        # Keep stdout/stderr above for tracer versions that still log there.
        log_directory = Path(context.scenario.host_log_folder) / "docker" / "weblog" / "logs"
        for log_file in sorted(log_directory.glob("ddtrace.log*")):
            if log_file.is_file():
                logs += "\n" + log_file.read_text(encoding="utf-8")
    # Log prefixes and separators vary by tracer; only the JSON contents matter.
    pattern = r"\bDATADOG TRACER CONFIGURATION\b[\s:-]*"
    configurations = []
    for match in re.finditer(pattern, logs):
        try:
            configuration, _ = json.JSONDecoder().raw_decode(logs[match.end() :])
        except json.JSONDecodeError as error:
            pytest.fail(f"Invalid DATADOG TRACER CONFIGURATION JSON: {error}")
        assert isinstance(configuration, dict), "Startup configuration must be a JSON object"
        configurations.append(configuration)

    assert configurations, "No DATADOG TRACER CONFIGURATION JSON found in tracer logs"
    return configurations


def _assert_keys(*keys: str) -> None:
    # Do not combine keys across startup records from different workers/processes.
    for index, configuration in enumerate(_get_startup_configurations()):
        missing = set(keys) - configuration.keys()
        assert not missing, f"Startup configuration #{index + 1} is missing keys: {', '.join(sorted(missing))}"


@scenarios.otel_startup_logs
@features.log_tracer_status_at_startup
class Test_OTEL_Startup_Logs:
    @pytest.mark.parametrize(
        ("config_name", "expected"),
        [pytest.param(name, value, id=name) for name, value in scenarios.OTEL_STARTUP_LOGS_ENV.items()],
    )
    def test_configured_value(self, config_name: str, expected: str) -> None:
        accepted_values = [expected]
        if config_name == "OTEL_TRACES_SAMPLER" and expected == "parentbased_always_on":
            # Our tracers do not support parent-based samplers, so falling back
            # to the corresponding non-parent-based sampler (always_on) is expected.
            accepted_values.append("always_on")

        for index, configuration in enumerate(_get_startup_configurations()):
            assert config_name in configuration, f"Startup configuration #{index + 1} is missing {config_name}"
            actual = configuration[config_name]
            # Environment values are strings, while startup JSON can encode booleans natively.
            normalized = str(actual).lower() if isinstance(actual, bool) else actual
            assert normalized in accepted_values, (
                f"Startup configuration #{index + 1}: {config_name}={actual!r}; expected one of {accepted_values!r}"
            )

    def test_traces(self) -> None:
        _assert_keys(
            "DD_TRACE_OTEL_ENABLED",
            "OTEL_TRACES_SAMPLER",
            "OTEL_TRACES_SAMPLER_ARG",
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
            "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL",
            "OTEL_EXPORTER_OTLP_TRACES_HEADERS",
        )

    def test_logs(self) -> None:
        _assert_keys(
            "DD_LOGS_OTEL_ENABLED",
            "OTEL_LOGS_EXPORTER",
            "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
            "OTEL_EXPORTER_OTLP_LOGS_PROTOCOL",
            "OTEL_EXPORTER_OTLP_LOGS_HEADERS",
        )

    def test_logs_blrp(self) -> None:
        _assert_keys(
            "OTEL_BLRP_SCHEDULE_DELAY",
            "OTEL_BLRP_EXPORT_TIMEOUT",
            "OTEL_BLRP_MAX_QUEUE_SIZE",
            "OTEL_BLRP_MAX_EXPORT_BATCH_SIZE",
        )

    def test_metrics(self) -> None:
        _assert_keys(
            "DD_METRICS_OTEL_ENABLED",
            "OTEL_METRIC_EXPORT_INTERVAL",
            "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
            "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL",
            "OTEL_EXPORTER_OTLP_METRICS_HEADERS",
            "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE",
        )

    def test_otlp_exporter(self) -> None:
        _assert_keys(
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "OTEL_EXPORTER_OTLP_PROTOCOL",
            "OTEL_EXPORTER_OTLP_HEADERS",
        )

    def test_otel_enabled(self) -> None:
        _assert_keys("OTEL_ENABLED")

    def test_otel_log_level(self) -> None:
        _assert_keys("OTEL_LOG_LEVEL")

    def test_otel_service_name(self) -> None:
        _assert_keys("OTEL_SERVICE_NAME")

    def test_otel_resource_attributes(self) -> None:
        _assert_keys("OTEL_RESOURCE_ATTRIBUTES")

    def test_otel_propagators(self) -> None:
        _assert_keys("OTEL_PROPAGATORS")
