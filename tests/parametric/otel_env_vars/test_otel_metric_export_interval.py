"""The metric reader's effective interval, in milliseconds, including its defaults."""

from utils import features, pytest, scenarios
from utils.docker_fixtures import TestAgentAPI
from tests.parametric.conftest import APMLibrary


VARIABLE = "OTEL_METRIC_EXPORT_INTERVAL"


@pytest.fixture
def library_env(interval: str | None) -> dict[str, str | None]:
    return {
        "DD_METRICS_OTEL_ENABLED": "true",
        # Deliver configuration telemetry within the test agent's bounded wait.
        "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",
        "OTEL_METRICS_EXPORTER": "otlp",
        # Isolate metrics from the apps' logs pipeline startup.
        "OTEL_LOGS_EXPORTER": "none",
        VARIABLE: interval,
        # Avoid a timeout longer than the smallest interval in SDKs that validate both.
        "OTEL_METRIC_EXPORT_TIMEOUT": "1",
    }


def _reader_interval(test_library: APMLibrary) -> int:
    # Resolved configuration avoids telemetry that can retain a rejected input.
    with test_library as library:
        interval = library.config().get("dd_metrics_otel_interval")
    assert interval is not None, "Effective metric reader interval is not exposed by the test app"
    return int(str(interval))


def _telemetry_interval(test_agent: TestAgentAPI, test_library: APMLibrary) -> int:
    with test_library as library:
        library.otel_get_meter("export-interval-configuration", "1.0.0", "", {})
    return _reported_interval(test_agent)


def _initialized_interval(test_agent: TestAgentAPI, test_library: APMLibrary) -> int:
    with test_library as library:
        library.otel_get_meter("export-interval-configuration", "1.0.0", "", {})
        # Accepted telemetry can precede reader initialization and leave the
        # API's proxy provider in place when initialization rejects the value.
        assert library.config()["otel_metrics_initialized"] == "true", "Metrics SDK did not initialize"
    return _reported_interval(test_agent)


def _reported_interval(test_agent: TestAgentAPI) -> int:
    configurations = test_agent.wait_for_telemetry_configurations()
    entries = configurations.get(VARIABLE)
    assert entries, f"No effective configuration for {VARIABLE}"
    # Rejected attempts carry an error and do not override the last accepted value.
    accepted = [entry for entry in entries if not _has_configuration_error(entry.get("error"))]
    assert accepted, f"No accepted configuration for {VARIABLE}: {entries}"
    value = accepted[0].get("value")
    assert value is not None, f"No value for {VARIABLE}: {accepted[0]}"
    return int(str(value))


def _has_configuration_error(error: object) -> bool:
    # An empty error envelope is accepted; a code or message denotes rejection.
    if isinstance(error, dict):
        return bool(error.get("code") or error.get("message"))
    return bool(error)


@scenarios.parametric
@features.otel_metric_export_interval
class Test_OTEL_METRIC_EXPORT_INTERVAL:
    @pytest.mark.parametrize(
        "interval",
        [
            pytest.param("1", id="1ms-minimum-positive"),
            pytest.param("12000", id="12000ms"),
            pytest.param("60000", id="60000ms"),
            pytest.param("2147483647", id="int32-max-ms"),
        ],
    )
    def test_stable_values(self, test_agent: TestAgentAPI, test_library: APMLibrary, interval: str) -> None:
        assert _telemetry_interval(test_agent, test_library) == int(interval)

    @pytest.mark.parametrize("interval", [pytest.param("0", id="zero-ms")])
    def test_zero(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        # A duration of zero is zero milliseconds, unlike an unlimited timeout.
        assert _telemetry_interval(test_agent, test_library) == 0

    @pytest.mark.parametrize("interval", [pytest.param(None, id="unset")])
    def test_unset_uses_default(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        assert _telemetry_interval(test_agent, test_library) == 10000

    @pytest.mark.parametrize("interval", [pytest.param("", id="empty")])
    def test_empty_is_unset(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        assert _telemetry_interval(test_agent, test_library) == 10000

    @pytest.mark.parametrize("interval", [pytest.param(None, id="unset")])
    def test_spec_default(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        assert _telemetry_interval(test_agent, test_library) == 60000

    @pytest.mark.parametrize("interval", [pytest.param("-1", id="negative")])
    def test_negative_is_ignored(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        assert _telemetry_interval(test_agent, test_library) == 10000

    @pytest.mark.parametrize("interval", [pytest.param("1.5", id="fractional")])
    def test_fractional_is_ignored(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        assert _telemetry_interval(test_agent, test_library) == 10000

    @pytest.mark.parametrize("interval", [pytest.param("not-an-interval", id="not-an-integer")])
    def test_invalid_values_use_default(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        assert _telemetry_interval(test_agent, test_library) == 10000

    @pytest.mark.parametrize(
        "interval",
        [
            pytest.param("1", id="1ms-minimum-positive"),
            pytest.param("12000", id="12000ms"),
            pytest.param("60000", id="60000ms"),
            pytest.param("2147483647", id="int32-max-ms"),
        ],
    )
    def test_reader_stable_values(self, test_library: APMLibrary, interval: str) -> None:
        assert _reader_interval(test_library) == int(interval)

    @pytest.mark.parametrize("interval", [pytest.param("0", id="zero-ms")])
    def test_reader_zero(self, test_library: APMLibrary) -> None:
        # A duration of zero is zero milliseconds, unlike an unlimited timeout.
        assert _reader_interval(test_library) == 0

    @pytest.mark.parametrize("interval", [pytest.param(None, id="unset")])
    def test_reader_unset_uses_default(self, test_library: APMLibrary) -> None:
        assert _reader_interval(test_library) == 10000

    @pytest.mark.parametrize("interval", [pytest.param("", id="empty")])
    def test_reader_empty_is_unset(self, test_library: APMLibrary) -> None:
        assert _reader_interval(test_library) == 10000

    @pytest.mark.parametrize("interval", [pytest.param("-1", id="negative")])
    def test_reader_negative_is_ignored(self, test_library: APMLibrary) -> None:
        assert _reader_interval(test_library) == 10000

    @pytest.mark.parametrize("interval", [pytest.param("1.5", id="fractional")])
    def test_reader_fractional_is_ignored(self, test_library: APMLibrary) -> None:
        assert _reader_interval(test_library) == 10000

    @pytest.mark.parametrize("interval", [pytest.param("not-an-interval", id="not-an-integer")])
    def test_reader_invalid_values_use_default(self, test_library: APMLibrary) -> None:
        assert _reader_interval(test_library) == 10000

    @pytest.mark.parametrize(
        ("interval", "expected"),
        [
            pytest.param("1", 1, id="1ms-minimum-positive"),
            pytest.param("12000", 12000, id="12000ms"),
            pytest.param("60000", 60000, id="60000ms"),
            pytest.param("2147483647", 2147483647, id="int32-max-ms"),
            pytest.param(None, 10000, id="unset"),
            pytest.param("", 10000, id="empty"),
        ],
    )
    def test_initialized_values(self, test_agent: TestAgentAPI, test_library: APMLibrary, expected: int) -> None:
        assert _initialized_interval(test_agent, test_library) == expected

    @pytest.mark.parametrize(
        ("interval", "expected"),
        [
            pytest.param("0", 0, id="zero-ms"),
            pytest.param("-1", 10000, id="negative"),
            pytest.param("1.5", 10000, id="fractional"),
            pytest.param("not-an-interval", 10000, id="not-an-integer"),
        ],
    )
    def test_initialized_zero_and_invalid_values(
        self, test_agent: TestAgentAPI, test_library: APMLibrary, expected: int
    ) -> None:
        assert _initialized_interval(test_agent, test_library) == expected
