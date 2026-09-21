"""OTLP header configuration, observed on exported requests.

https://opentelemetry.io/docs/specs/otel/protocol/exporter/#specifying-headers-via-environment-variables
"""

import pytest

from tests.parametric.conftest import APMLibrary
from tests.parametric.test_otel_logs import find_log_record
from tests.parametric.test_otel_metrics import generate_default_counter_data_point
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.parametric import LogLevel


VARIABLE = "OTEL_EXPORTER_OTLP_HEADERS"


def _environment(signal: str, value: str | None) -> dict[str, str | None]:
    # Enable the observed signal and use HTTP so its request headers are visible.
    return {
        f"DD_{signal.upper()}_OTEL_ENABLED": "true",
        "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
        VARIABLE: value,
    }


def _assert_headers(signal: str, expected: dict[str, str], test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
    name = "otel_header_configuration"
    with test_library as library:
        if signal == "metrics":
            generate_default_counter_data_point(library, name)
        else:
            library.create_logger(name, LogLevel.INFO)
            library.write_log(name, LogLevel.INFO, name)

    if signal == "metrics":
        metrics = test_agent.wait_for_num_otlp_metrics(1)
        assert metrics[0]["resource_metrics"][0]["scope_metrics"] is not None
    else:
        assert find_log_record(test_agent.wait_for_num_log_payloads(1), name, name) is not None

    requests = [request for request in test_agent.requests() if request["url"].endswith(f"/v1/{signal}")]
    assert requests, f"No OTLP {signal} request was captured"
    for request in requests:
        headers = {key.lower(): value for key, value in request["headers"].items()}
        for key in ("api-key", "other-config-value", "x-global-only"):
            assert headers.get(key) == expected.get(key), f"Unexpected {key}: {headers}"


@features.otel_exporter_otlp_headers
@scenarios.parametric
class Test_OTEL_EXPORTER_OTLP_HEADERS:
    @pytest.mark.parametrize(
        ("library_env", "expected"),
        [
            pytest.param(_environment("metrics", None), {}, id="unset"),
            pytest.param(_environment("metrics", ""), {}, id="empty"),
            pytest.param(_environment("metrics", "api-key=key"), {"api-key": "key"}, id="one-pair"),
            pytest.param(
                _environment("metrics", "api-key=key,other-config-value=value"),
                {"api-key": "key", "other-config-value": "value"},
                id="multiple-pairs",
            ),
        ],
    )
    def test_metrics_headers(
        self, expected: dict[str, str], test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Unset and empty add no custom headers; configured pairs reach the exporter."""
        _assert_headers("metrics", expected, test_agent, test_library)

    @pytest.mark.parametrize(
        "library_env", [_environment("metrics", "api-key=hello%20world%2Cvalue%3D1")], ids=["percent-encoded-value"]
    )
    def test_metrics_percent_encoded_value(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        _assert_headers("metrics", {"api-key": "hello world,value=1"}, test_agent, test_library)

    @pytest.mark.parametrize(
        ("library_env", "expected"),
        [
            pytest.param(_environment("logs", None), {}, id="unset"),
            pytest.param(_environment("logs", ""), {}, id="empty"),
            pytest.param(_environment("logs", "api-key=key"), {"api-key": "key"}, id="one-pair"),
            pytest.param(
                _environment("logs", "api-key=key,other-config-value=value"),
                {"api-key": "key", "other-config-value": "value"},
                id="multiple-pairs",
            ),
        ],
    )
    def test_logs_headers(self, expected: dict[str, str], test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Unset and empty add no custom headers; configured pairs reach the exporter."""
        _assert_headers("logs", expected, test_agent, test_library)

    @pytest.mark.parametrize(
        "library_env", [_environment("logs", "api-key=hello%20world%2Cvalue%3D1")], ids=["percent-encoded-value"]
    )
    def test_logs_percent_encoded_value(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        _assert_headers("logs", {"api-key": "hello world,value=1"}, test_agent, test_library)

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                **_environment("metrics", "api-key=global,x-global-only=global"),
                "OTEL_EXPORTER_OTLP_METRICS_HEADERS": "api-key=signal",
            }
        ],
        ids=["signal-overrides-global"],
    )
    def test_metrics_override(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        _assert_headers("metrics", {"api-key": "signal"}, test_agent, test_library)

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                **_environment("logs", "api-key=global,x-global-only=global"),
                "OTEL_EXPORTER_OTLP_LOGS_HEADERS": "api-key=signal",
            }
        ],
        ids=["signal-overrides-global"],
    )
    def test_logs_override(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        _assert_headers("logs", {"api-key": "signal"}, test_agent, test_library)
