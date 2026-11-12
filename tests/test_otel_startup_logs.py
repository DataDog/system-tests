"""Required OTel fields in the tracer's startup configuration JSON.

Required keys are checked even when their settings are left at their defaults.
Every required key explicitly set by the scenario also has a value test; endpoint
values are compared as URLs, so equivalent forms such as an added root path match.
Signal-specific OTLP settings belong to their signal's presence test; shared OTLP
settings have their own test. Key order and existing startup fields are unconstrained.
"""

import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from utils import context, features, interfaces, pytest, scenarios
from utils._context._scenarios.otel_semantics import OTEL_STARTUP_LOGS_ENV

_TRACES_KEYS = (
    "DD_TRACE_OTEL_ENABLED",
    "OTEL_TRACES_SAMPLER",
    "OTEL_TRACES_SAMPLER_ARG",
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
    "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL",
    "OTEL_EXPORTER_OTLP_TRACES_HEADERS",
)
_LOGS_KEYS = (
    "DD_LOGS_OTEL_ENABLED",
    "OTEL_LOGS_EXPORTER",
    "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
    "OTEL_EXPORTER_OTLP_LOGS_PROTOCOL",
    "OTEL_EXPORTER_OTLP_LOGS_HEADERS",
)
_LOGS_BLRP_KEYS = (
    "OTEL_BLRP_SCHEDULE_DELAY",
    "OTEL_BLRP_EXPORT_TIMEOUT",
    "OTEL_BLRP_MAX_QUEUE_SIZE",
    "OTEL_BLRP_MAX_EXPORT_BATCH_SIZE",
)
_METRICS_KEYS = (
    "DD_METRICS_OTEL_ENABLED",
    "OTEL_METRIC_EXPORT_INTERVAL",
    "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
    "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL",
    "OTEL_EXPORTER_OTLP_METRICS_HEADERS",
    "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE",
)
_OTLP_EXPORTER_KEYS = (
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_EXPORTER_OTLP_PROTOCOL",
    "OTEL_EXPORTER_OTLP_HEADERS",
)
_STANDALONE_KEYS = (
    "OTEL_TRACES_EXPORTER",
    "OTEL_LOG_LEVEL",
    "OTEL_SERVICE_NAME",
    "OTEL_RESOURCE_ATTRIBUTES",
    "OTEL_PROPAGATORS",
)
_REQUIRED_KEYS = frozenset(
    (*_TRACES_KEYS, *_LOGS_KEYS, *_LOGS_BLRP_KEYS, *_METRICS_KEYS, *_OTLP_EXPORTER_KEYS, *_STANDALONE_KEYS)
)
# OTEL_TRACES_SAMPLER_ARG only applies to these samplers.
_RATIO_SAMPLERS = frozenset(("traceidratio", "parentbased_traceidratio"))
_DEFAULT_PORTS = {"http": 80, "https": 443}


def _canonical_url(url: str) -> str:
    # Tracers may log the URL their HTTP client uses, which normalizes the case of the
    # scheme and host, the default port, and an empty path ("http://agent:4318/").
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    port = parts.port or _DEFAULT_PORTS.get(scheme)
    return f"{scheme}://{parts.hostname}:{port}{parts.path or '/'}?{parts.query}#{parts.fragment}"


def _is_same_url(actual: object, expected: str) -> bool:
    if not isinstance(actual, str):
        return False
    try:
        return _canonical_url(actual) == _canonical_url(expected)
    except ValueError:  # invalid port
        return actual == expected


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


def _assert_configuration_keys(index: int, configuration: dict[str, object], keys: set[str]) -> None:
    missing = keys - configuration.keys()
    assert not missing, f"Startup configuration #{index + 1} is missing keys: {', '.join(sorted(missing))}"


def _assert_keys(*keys: str) -> None:
    # Do not combine keys across startup records from different workers/processes.
    for index, configuration in enumerate(_get_startup_configurations()):
        _assert_configuration_keys(index, configuration, set(keys))


@scenarios.otel_startup_logs
@features.log_tracer_status_at_startup
class Test_OTEL_Startup_Logs:
    @pytest.mark.parametrize(
        ("config_name", "expected"),
        [
            pytest.param(name, value, id=name)
            for name, value in OTEL_STARTUP_LOGS_ENV.items()
            # The scenario also sets unrelated settings; only required startup keys are checked.
            if name in _REQUIRED_KEYS
        ],
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
            if config_name.endswith("_ENDPOINT"):
                matches = any(_is_same_url(normalized, value) for value in accepted_values)
            else:
                matches = normalized in accepted_values
            assert matches, (
                f"Startup configuration #{index + 1}: {config_name}={actual!r}; expected one of {accepted_values!r}"
            )

    def test_traces(self) -> None:
        for index, configuration in enumerate(_get_startup_configurations()):
            keys = set(_TRACES_KEYS)
            if configuration.get("OTEL_TRACES_SAMPLER") not in _RATIO_SAMPLERS:
                keys.discard("OTEL_TRACES_SAMPLER_ARG")
            _assert_configuration_keys(index, configuration, keys)

    def test_logs(self) -> None:
        _assert_keys(*_LOGS_KEYS)

    def test_logs_blrp(self) -> None:
        _assert_keys(*_LOGS_BLRP_KEYS)

    def test_metrics(self) -> None:
        _assert_keys(*_METRICS_KEYS)

    def test_otlp_exporter(self) -> None:
        _assert_keys(*_OTLP_EXPORTER_KEYS)

    def test_otel_traces_exporter(self) -> None:
        _assert_keys("OTEL_TRACES_EXPORTER")

    def test_otel_log_level(self) -> None:
        _assert_keys("OTEL_LOG_LEVEL")

    def test_otel_service_name(self) -> None:
        _assert_keys("OTEL_SERVICE_NAME")

    def test_otel_resource_attributes(self) -> None:
        _assert_keys("OTEL_RESOURCE_ATTRIBUTES")

    def test_otel_propagators(self) -> None:
        _assert_keys("OTEL_PROPAGATORS")
