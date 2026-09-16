"""Prove OTEL_EXPORTER_OTLP_LOGS_COMPRESSION through the encoding of an emitted OTLP request."""

import pytest

from tests.parametric.conftest import APMLibrary
from utils.docker_fixtures.parametric import LogLevel
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI


@pytest.fixture
def library_env(
    compression_env: dict[str, str], test_agent: TestAgentAPI, test_agent_otlp_http_port: int
) -> dict[str, str | None]:
    return {
        "DD_TRACE_DEBUG": None,
        "DD_TRACE_OTEL_ENABLED": "true",
        "DD_METRICS_OTEL_ENABLED": "false",
        "DD_LOGS_OTEL_ENABLED": "true",
        "DD_RUNTIME_METRICS_ENABLED": "false",
        "OTEL_METRICS_EXPORTER": "none",
        "OTEL_LOGS_EXPORTER": "otlp",
        "OTEL_EXPORTER_OTLP_LOGS_PROTOCOL": "http/protobuf",
        "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT": f"http://{test_agent.container_name}:{test_agent_otlp_http_port}/v1/logs",
        "OTEL_EXPORTER_OTLP_COMPRESSION": None,
        "OTEL_EXPORTER_OTLP_LOGS_COMPRESSION": None,
        **compression_env,
    }


@scenarios.parametric
@features.otel_exporter_otlp_logs_compression
class Test_OTEL_EXPORTER_OTLP_LOGS_COMPRESSION:
    @pytest.mark.parametrize(
        ("compression_env", "expected"),
        [
            pytest.param({"OTEL_EXPORTER_OTLP_LOGS_COMPRESSION": "gzip"}, "gzip", id="gzip"),
            pytest.param({"OTEL_EXPORTER_OTLP_LOGS_COMPRESSION": "none"}, "none", id="none"),
        ],
    )
    def test_stable_values(self, test_agent: TestAgentAPI, test_library: APMLibrary, expected: str) -> None:
        self._assert_compression(test_agent, test_library, expected)

    @pytest.mark.parametrize("compression_env", [pytest.param({}, id="unset")])
    def test_default(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        # The specification permits SDK-specific defaults; Java and Python default to no compression.
        self._assert_compression(test_agent, test_library, "none")

    @pytest.mark.parametrize("compression_env", [pytest.param({"OTEL_EXPORTER_OTLP_LOGS_COMPRESSION": ""}, id="empty")])
    def test_empty(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        self._assert_compression(test_agent, test_library, "none")

    @pytest.mark.parametrize(
        "compression_env", [pytest.param({"OTEL_EXPORTER_OTLP_LOGS_COMPRESSION": "not-a-compression"}, id="invalid")]
    )
    def test_invalid(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        self._assert_compression(test_agent, test_library, "none")

    @pytest.mark.parametrize(
        ("compression_env", "expected"),
        [
            pytest.param(
                {"OTEL_EXPORTER_OTLP_COMPRESSION": "gzip", "OTEL_EXPORTER_OTLP_LOGS_COMPRESSION": "none"},
                "none",
                id="signal-none-overrides-gzip",
            ),
            pytest.param(
                {"OTEL_EXPORTER_OTLP_COMPRESSION": "none", "OTEL_EXPORTER_OTLP_LOGS_COMPRESSION": "gzip"},
                "gzip",
                id="signal-gzip-overrides-none",
            ),
        ],
    )
    def test_signal_precedence(self, test_agent: TestAgentAPI, test_library: APMLibrary, expected: str) -> None:
        self._assert_compression(test_agent, test_library, expected)

    @pytest.mark.parametrize(
        "compression_env",
        [
            pytest.param(
                {"OTEL_EXPORTER_OTLP_COMPRESSION": "gzip", "OTEL_EXPORTER_OTLP_LOGS_COMPRESSION": ""},
                id="empty-inherits-gzip",
            )
        ],
    )
    def test_empty_inherits_general(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        self._assert_compression(test_agent, test_library, "gzip")

    def _assert_compression(self, test_agent: TestAgentAPI, test_library: APMLibrary, expected: str) -> None:
        # A single exported artifact proves that the effective compressor is in use.
        with test_library as library:
            library.create_logger("compression_probe", LogLevel.INFO)
            library.write_log("compression_probe", LogLevel.INFO, "compression probe")

        test_agent.wait_for_num_log_payloads(1)
        requests = [request for request in test_agent.otlp_requests() if request["url"].endswith("/v1/logs")]
        assert requests, "No OTLP logs request was captured"
        for request in requests:
            headers = {name.lower(): value.lower() for name, value in request["headers"].items()}
            encoding = headers.get("content-encoding", "identity")
            if expected == "gzip":
                assert encoding == "gzip", headers
            else:
                assert encoding in ("identity", ""), headers
