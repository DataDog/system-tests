"""Observe exporter selection with one counter rather than an environment echo."""

import json
import re

from utils import features, pytest, scenarios
from utils.docker_fixtures import TestAgentAPI
from tests.parametric.conftest import APMLibrary


VARIABLE = "OTEL_METRICS_EXPORTER"
METER = "metrics-exporter-configuration"
COUNTER = "exporter_selection_probe"


@pytest.fixture
def library_env(
    exporter: str | None, test_agent: TestAgentAPI, test_agent_otlp_http_port: int
) -> dict[str, str | None]:
    return {
        # Opt in to the metrics integration; the selected exporter must still apply.
        "DD_METRICS_OTEL_ENABLED": "true",
        # Keep runtime metrics out of the exporter-none assertion.
        "DD_RUNTIME_METRICS_ENABLED": "false",
        VARIABLE: exporter,
        # Isolate metrics from the apps' logs pipeline startup.
        "OTEL_LOGS_EXPORTER": "none",
        "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL": "http/protobuf",
        "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT": f"http://{test_agent.container_name}:{test_agent_otlp_http_port}/v1/metrics",
        # Keep periodic exports from racing the explicit counter flush.
        "OTEL_METRIC_EXPORT_INTERVAL": "60000",
    }


def _emit_counter(library: APMLibrary) -> None:
    library.otel_get_meter(METER, "1.0.0", "", {})
    library.otel_metrics_force_flush()
    library.otel_create_counter(METER, COUNTER, "", "Exporter selection probe")
    library.otel_counter_add(METER, COUNTER, "", "Exporter selection probe", 42, {})
    library.otel_metrics_force_flush()


def _has_counter(value: object) -> bool:
    if isinstance(value, dict):
        if value.get("name") == COUNTER:
            # Console exporters may use the SDK's `data` structure instead of OTLP's `sum`.
            aggregation = value.get("sum", value.get("data"))
            if isinstance(aggregation, dict):
                points = aggregation.get("data_points", aggregation.get("dataPoints", []))
                if not isinstance(points, list):
                    return False
                for point in points:
                    if not isinstance(point, dict):
                        continue
                    for key in ("as_int", "asInt", "as_double", "asDouble", "value"):
                        if str(point.get(key)) in ("42", "42.0"):
                            return True
        return any(_has_counter(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_counter(item) for item in value)
    return False


def _assert_otlp(test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
    with test_library as library:
        _emit_counter(library)
    metrics = test_agent.wait_for_num_otlp_metrics(num=1)
    assert metrics[0]["resource_metrics"][0]["scope_metrics"] is not None
    assert _has_counter(metrics), f"No exported {COUNTER} counter in {metrics}"


def _assert_none(test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
    """Preserve the previous exporter-none check with an explicit reachable collector."""
    with test_library as library:
        _emit_counter(library)
    with pytest.raises(ValueError):
        test_agent.wait_for_num_otlp_metrics(num=1)


def _assert_console(test_agent: TestAgentAPI, test_library: APMLibrary, *, otlp: bool = False) -> None:
    with test_library as library:
        _emit_counter(library)
    assert not _has_counter(test_agent.metrics())
    decoder = json.JSONDecoder()
    output = test_library.get_logs()
    for offset, character in enumerate(output):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(output[offset:])
        except ValueError:
            continue
        if otlp and (not isinstance(value, dict) or "resourceMetrics" not in value):
            continue
        if _has_counter(value):
            return
    pytest.fail(f"No exported {COUNTER} counter in standard output")


@scenarios.parametric
@features.otel_metrics_exporter
class Test_OTEL_METRICS_EXPORTER:
    @pytest.mark.parametrize("exporter", [pytest.param("otlp", id="otlp")])
    def test_otlp(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        _assert_otlp(test_agent, test_library)

    @pytest.mark.parametrize("exporter", [pytest.param("OTLP", id="OTLP")])
    def test_otlp_case_insensitive(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        _assert_otlp(test_agent, test_library)

    @pytest.mark.parametrize("exporter", [pytest.param("none", id="none")])
    def test_none(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        _assert_none(test_agent, test_library)

    @pytest.mark.parametrize("exporter", [pytest.param("NONE", id="NONE")])
    def test_none_case_insensitive(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        _assert_none(test_agent, test_library)

    @pytest.mark.parametrize("exporter", [pytest.param(None, id="unset")])
    def test_spec_default(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        _assert_otlp(test_agent, test_library)

    @pytest.mark.parametrize("exporter", [pytest.param("", id="empty")])
    def test_empty_is_unset(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        _assert_otlp(test_agent, test_library)

    @pytest.mark.parametrize("exporter", [pytest.param("not-an-exporter", id="invalid")])
    def test_invalid_is_ignored(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        _assert_otlp(test_agent, test_library)

    @pytest.mark.parametrize("exporter", [pytest.param("console", id="console")])
    def test_console(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        _assert_console(test_agent, test_library)

    @pytest.mark.parametrize("exporter", [pytest.param("prometheus", id="prometheus")])
    def test_prometheus(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with test_library as library:
            _emit_counter(library)
            success, output = library.container_exec_run("curl --fail --silent http://127.0.0.1:9464/metrics")
            assert success, output
            assert re.search(rf"(?m)^{COUNTER}(?:_total)?(?:\{{[^\n]*\}})? 42(?:\.0)?(?: |$)", output), output
        assert not _has_counter(test_agent.metrics())

    @pytest.mark.parametrize("exporter", [pytest.param("logging", id="logging-deprecated")])
    def test_deprecated_values(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        _assert_console(test_agent, test_library)

    @pytest.mark.parametrize("exporter", [pytest.param("otlp/stdout", id="otlp-stdout")])
    def test_development_values(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        _assert_console(test_agent, test_library, otlp=True)
