"""Observe exporter selection through one log record, without reading environment values back."""

import json

import pytest

from tests.parametric.conftest import APMLibrary
from tests.parametric.test_otel_logs import find_log_record
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.parametric import LogLevel


@pytest.fixture
def library_env(
    exporter_env: dict[str, str], test_agent: TestAgentAPI, test_agent_otlp_http_port: int
) -> dict[str, str | None]:
    return {
        "DD_TRACE_DEBUG": None,
        "DD_TRACE_OTEL_ENABLED": "true",
        # This enables the logs integration; OTEL_LOGS_EXPORTER must still select its exporter.
        "DD_LOGS_OTEL_ENABLED": "true",
        "DD_METRICS_OTEL_ENABLED": "false",
        "OTEL_METRICS_EXPORTER": "none",
        "OTEL_LOGS_EXPORTER": None,
        "OTEL_EXPORTER_OTLP_LOGS_PROTOCOL": "http/protobuf",
        "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT": f"http://{test_agent.container_name}:{test_agent_otlp_http_port}/v1/logs",
        **exporter_env,
    }


@scenarios.parametric
@features.otel_logs_exporter
class Test_OTEL_LOGS_EXPORTER:
    @pytest.mark.parametrize(
        ("exporter_env", "exporter"),
        [
            pytest.param({"OTEL_LOGS_EXPORTER": "otlp"}, "otlp", id="otlp"),
            pytest.param({"OTEL_LOGS_EXPORTER": "none"}, "none", id="none"),
        ],
    )
    def test_stable_values(self, test_agent: TestAgentAPI, test_library: APMLibrary, exporter: str) -> None:
        self._assert_exporter(test_agent, test_library, exporter)

    # Console support is independent of the OTLP pipeline, so declare it separately.
    @pytest.mark.parametrize("exporter_env", [pytest.param({"OTEL_LOGS_EXPORTER": "console"}, id="console")])
    def test_console(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        self._assert_exporter(test_agent, test_library, "console")

    @pytest.mark.parametrize("exporter_env", [pytest.param({"OTEL_LOGS_EXPORTER": "logging"}, id="logging-deprecated")])
    def test_deprecated_values(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        self._assert_exporter(test_agent, test_library, "console")

    @pytest.mark.parametrize("exporter_env", [pytest.param({"OTEL_LOGS_EXPORTER": "otlp/stdout"}, id="otlp-stdout")])
    def test_development_values(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        self._assert_exporter(test_agent, test_library, "otlp/stdout")

    @pytest.mark.parametrize("exporter_env", [pytest.param({}, id="unset")])
    def test_spec_default(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        self._assert_exporter(test_agent, test_library, "otlp")

    @pytest.mark.parametrize("exporter_env", [pytest.param({"OTEL_LOGS_EXPORTER": ""}, id="empty")])
    def test_empty(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        self._assert_exporter(test_agent, test_library, "otlp")

    @pytest.mark.parametrize("exporter_env", [pytest.param({"OTEL_LOGS_EXPORTER": "not-an-exporter"}, id="invalid")])
    def test_invalid(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        self._assert_exporter(test_agent, test_library, "otlp")

    def _assert_exporter(self, test_agent: TestAgentAPI, test_library: APMLibrary, exporter: str) -> None:
        logger_name = "exporter_selection_probe"
        message = "OTEL exporter selection probe 2329"
        with test_library as library:
            assert library.create_logger(logger_name, LogLevel.INFO)
            assert library.write_log(logger_name, LogLevel.INFO, message)
            flushed, detail = library.otel_logs_flush()
            assert flushed, detail

        if exporter == "otlp":
            payloads = test_agent.wait_for_num_log_payloads(1)
            assert find_log_record(payloads, logger_name, message) is not None
        else:
            # The library context flushes the logger provider before returning.
            assert find_log_record(test_agent.logs(), logger_name, message) is None
            if exporter in ("console", "otlp/stdout"):
                assert _has_exported_record(
                    test_library.get_logs(), logger_name, message, otlp=exporter == "otlp/stdout"
                )
            else:
                assert not _has_exported_record(test_library.get_logs(), logger_name, message)


def _has_log_body(value: object, message: str) -> bool:
    if isinstance(value, dict):
        if "body" in value and ("severity_number" in value or "severityNumber" in value):
            body = value["body"]
            if body in (message, {"stringValue": message}, {"string_value": message}):
                return True
        return any(_has_log_body(item, message) for item in value.values())
    if isinstance(value, list):
        return any(_has_log_body(item, message) for item in value)
    return False


def _has_exported_record(output: str, logger_name: str, message: str, *, otlp: bool = False) -> bool:
    # Decode exporter JSON, including multiline console output. A server log echoing
    # the write_log API request is not an exported LogRecord (no body/severity fields).
    decoder = json.JSONDecoder()
    for offset, character in enumerate(output):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(output[offset:])
        except ValueError:
            continue
        if otlp and (not isinstance(value, dict) or "resourceLogs" not in value):
            continue
        if logger_name in json.dumps(value) and _has_log_body(value, message):
            return True
    return False
