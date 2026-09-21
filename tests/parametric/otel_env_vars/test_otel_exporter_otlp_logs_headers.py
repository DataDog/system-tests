"""OTLP header configuration, observed on exported requests.

https://opentelemetry.io/docs/specs/otel/protocol/exporter/#specifying-headers-via-environment-variables
"""

import pytest

from tests.parametric.conftest import APMLibrary
from tests.parametric.test_otel_logs import find_log_record
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.parametric import LogLevel


VARIABLE = "OTEL_EXPORTER_OTLP_LOGS_HEADERS"


# Pin HTTP/protobuf in library_env so captured headers belong to the exporter request.
# Some SDKs default to gRPC; the collector forwards decoded gRPC payloads over
# HTTP, whose headers do not represent the original request.
def _environment(value: str | None) -> dict[str, str | None]:
    return {
        "DD_LOGS_OTEL_ENABLED": "true",
        "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
        VARIABLE: value,
    }


def _assert_headers(expected: dict[str, str], test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
    name = "otel_header_configuration"
    with test_library as library:
        library.create_logger(name, LogLevel.INFO)
        library.write_log(name, LogLevel.INFO, name)
    assert find_log_record(test_agent.wait_for_num_log_payloads(1), name, name) is not None

    requests = [request for request in test_agent.requests() if request["url"].endswith("/v1/logs")]
    assert requests, "No OTLP logs request was captured"
    for request in requests:
        headers = {key.lower(): value for key, value in request["headers"].items()}
        for key in ("api-key", "other-config-value", "x-global-only"):
            assert headers.get(key) == expected.get(key), f"Unexpected {key}: {headers}"


@features.otel_exporter_otlp_logs_headers
@scenarios.parametric
class Test_OTEL_EXPORTER_OTLP_LOGS_HEADERS:
    @pytest.mark.parametrize(
        ("library_env", "expected"),
        [
            pytest.param(_environment(None), {}, id="unset"),
            pytest.param(_environment(""), {}, id="empty"),
            pytest.param(_environment("api-key=key"), {"api-key": "key"}, id="one-pair"),
            pytest.param(
                _environment("api-key=key,other-config-value=value"),
                {"api-key": "key", "other-config-value": "value"},
                id="multiple-pairs",
            ),
        ],
    )
    def test_logs_headers(self, expected: dict[str, str], test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Unset and empty add no custom headers; configured pairs reach the exporter."""
        _assert_headers(expected, test_agent, test_library)

    @pytest.mark.parametrize(
        "library_env", [_environment("api-key=hello%20world%2Cvalue%3D1")], ids=["percent-encoded-value"]
    )
    def test_logs_percent_encoded_value(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        _assert_headers({"api-key": "hello world,value=1"}, test_agent, test_library)

    @pytest.mark.parametrize(
        "library_env",
        [{**_environment(None), "OTEL_EXPORTER_OTLP_HEADERS": "api-key=global,x-global-only=global"}],
        ids=["unset-falls-back"],
    )
    def test_unset_falls_back(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        _assert_headers({"api-key": "global", "x-global-only": "global"}, test_agent, test_library)

    @pytest.mark.parametrize(
        "library_env",
        [{**_environment(""), "OTEL_EXPORTER_OTLP_HEADERS": "api-key=global,x-global-only=global"}],
        ids=["empty-falls-back"],
    )
    def test_empty_falls_back(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        _assert_headers({"api-key": "global", "x-global-only": "global"}, test_agent, test_library)

    @pytest.mark.parametrize(
        "library_env",
        [{**_environment("api-key=signal"), "OTEL_EXPORTER_OTLP_HEADERS": "api-key=global,x-global-only=global"}],
        ids=["signal-overrides"],
    )
    def test_signal_overrides(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        _assert_headers({"api-key": "signal"}, test_agent, test_library)
