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


def _effective_interval(test_agent: TestAgentAPI, test_library: APMLibrary) -> int:
    # Java telemetry reports the original input, including rejected values.
    # Its public Config getter exposes the resolved interval instead.
    # Go also needs the reader observation for values its OTel reader can
    # reject after publishing configuration telemetry.
    if test_library.lang in ("java", "golang"):
        interval = test_library.config().get("dd_metrics_otel_interval")
        assert interval is not None, "Effective metric reader interval is not exposed by the test app"
        return int(str(interval))
    test_library.otel_get_meter("export-interval-configuration", "1.0.0", "", {})
    if test_library.lang == "python":
        # Python can publish an accepted value before the OTel reader rejects
        # it during initialization and leaves the API's proxy provider in place.
        assert test_library.config()["otel_metrics_initialized"] == "true", "Metrics SDK did not initialize"

    configurations = test_agent.wait_for_telemetry_configurations()
    entries = configurations.get(VARIABLE)
    assert entries, f"No effective configuration for {VARIABLE}"
    # Telemetry may also report attempted inputs. Rejected entries carry an error
    # and do not override the last accepted value (notably in Node.js).
    accepted = [entry for entry in entries if not _has_configuration_error(entry.get("error"))]
    assert accepted, f"No accepted configuration for {VARIABLE}: {entries}"
    value = accepted[0].get("value")
    assert value is not None, f"No value for {VARIABLE}: {accepted[0]}"
    return int(str(value))


def _has_configuration_error(error: object) -> bool:
    # Go serializes the zero-valued error envelope even for accepted settings.
    # Node.js reports rejected attempts with a message and a null error code.
    if isinstance(error, dict):
        return bool(error.get("code") or error.get("message"))
    return bool(error)


def _default_interval(test_library: APMLibrary) -> int:
    # The registry documents Datadog's intentional 10s default, except PHP's 60s.
    return 60000 if test_library.lang == "php" else 10000


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
        assert _effective_interval(test_agent, test_library) == int(interval)

    @pytest.mark.parametrize("interval", [pytest.param("0", id="zero-ms")])
    def test_zero(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        # A duration of zero is zero milliseconds, unlike an unlimited timeout.
        assert _effective_interval(test_agent, test_library) == 0

    @pytest.mark.parametrize("interval", [pytest.param(None, id="unset")])
    def test_unset_uses_default(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        assert _effective_interval(test_agent, test_library) == _default_interval(test_library)

    @pytest.mark.parametrize("interval", [pytest.param("", id="empty")])
    def test_empty_is_unset(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        assert _effective_interval(test_agent, test_library) == _default_interval(test_library)

    @pytest.mark.parametrize("interval", [pytest.param(None, id="unset")])
    def test_spec_default(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        assert _effective_interval(test_agent, test_library) == 60000

    @pytest.mark.parametrize("interval", [pytest.param("-1", id="negative")])
    def test_negative_is_ignored(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        assert _effective_interval(test_agent, test_library) == _default_interval(test_library)

    @pytest.mark.parametrize("interval", [pytest.param("1.5", id="fractional")])
    def test_fractional_is_ignored(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        assert _effective_interval(test_agent, test_library) == _default_interval(test_library)

    @pytest.mark.parametrize("interval", [pytest.param("not-an-interval", id="not-an-integer")])
    def test_invalid_values_use_default(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        assert _effective_interval(test_agent, test_library) == _default_interval(test_library)
