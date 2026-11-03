from collections.abc import Callable
import time
from typing import Any

from utils import pytest

from tests.parametric.conftest import APMLibrary
from tests.parametric.otel_env_vars.conftest import APMLibraryFactory
from tests.parametric.otel_env_vars.utils import generate_default_counter_data_point
from tests.parametric.utils import MIN_AGENT_VERSION_FOR_CSS
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.parametric import LogLevel


COUNTER = "otel_sdk_disabled_probe"
LOGGER = "otel_sdk_disabled_probe"
LOG_MESSAGE = "Test log for OTEL_SDK_DISABLED"
SPAN_NAME = "otel-sdk-disabled-span"

OTLP_TRACES_ENV = {
    "OTEL_TRACES_EXPORTER": "otlp",
    "DD_TRACE_OTEL_ENABLED": "true",
    "DD_TRACE_OTEL_SEMANTICS_ENABLED": "true",
}
# Client-side stats are only computed for an agent version that supports them.
CSS_AGENT_ENV = {"TEST_AGENT_VERSION": MIN_AGENT_VERSION_FOR_CSS}

# Runtime metrics and OTLP trace metrics are exported periodically rather than on flush. The control
# must export within this many seconds, and the disabled run must then export nothing for as long.
PERIODIC_EXPORT_WINDOW = 30


@pytest.fixture
def otlp_endpoints(
    library_env: dict[str, str | None], test_agent: TestAgentAPI, test_agent_otlp_http_port: int
) -> None:
    # A reachable collector keeps an ignored OTEL_SDK_DISABLED from passing as a failed export,
    # including for a signal that the test does not opt in to.
    collector = f"http://{test_agent.container_name}:{test_agent_otlp_http_port}"
    for signal in ("traces", "metrics", "logs"):
        library_env[f"OTEL_EXPORTER_OTLP_{signal.upper()}_ENDPOINT"] = f"{collector}/v1/{signal}"
        library_env[f"OTEL_EXPORTER_OTLP_{signal.upper()}_PROTOCOL"] = "http/protobuf"


def _emit_log(library: APMLibrary) -> None:
    assert library.create_logger(LOGGER, LogLevel.INFO)
    assert library.write_log(LOGGER, LogLevel.INFO, LOG_MESSAGE)
    # A disabled SDK may have no logger provider to flush.
    library.otel_logs_flush()


def _emit_span(library: APMLibrary) -> None:
    with library.dd_start_span(name=SPAN_NAME):
        pass
    library.dd_flush()


def _emit_otel_span(library: APMLibrary) -> None:
    with library.otel_start_span(SPAN_NAME):
        pass
    library.otel_flush(1)


def _otlp_urls(test_agent: TestAgentAPI, *signals: str) -> list[str]:
    # The OTLP port also lists the requests of the Datadog port, such as telemetry and remote config.
    paths = tuple(f"/v1/{signal}" for signal in signals)
    return [request["url"] for request in test_agent.otlp_requests() if request["url"].endswith(paths)]


def _dogstatsd_metrics(test_agent: TestAgentAPI) -> list[str]:
    # Service checks and events are sent right away, so they can arrive long before the first
    # metrics are flushed. They still count as exported data in a disabled run.
    return [line for line in test_agent.dogstatsd_metrics() if not line.startswith(("_sc|", "_e{"))]


def _exported(test_agent: TestAgentAPI, *, dogstatsd: bool) -> dict[str, list[Any]]:
    exported: dict[str, list[Any]] = {
        "Datadog traces": test_agent.traces(),
        "Datadog trace stats": test_agent.get_v06_stats_requests(),
        "OTLP": _otlp_urls(test_agent, "traces", "metrics", "logs"),
    }
    if dogstatsd:
        exported["DogStatsD"] = test_agent.dogstatsd_metrics()
    return {channel: payloads for channel, payloads in exported.items() if payloads}


def _assert_nothing_exported(test_agent: TestAgentAPI, seconds: float = 3, *, dogstatsd: bool = False) -> None:
    # Every channel is checked, so a signal cannot pass as disabled by moving to another exporter.
    deadline = time.monotonic() + seconds
    while True:
        exported = _exported(test_agent, dogstatsd=dogstatsd)
        assert not exported, f"OTEL_SDK_DISABLED=true still exported: {exported}"
        if time.monotonic() > deadline:
            return
        time.sleep(0.1)


def _wait_for_periodic_export(probe: Callable[[], object]) -> None:
    """Wait until `probe` sees a payload of the control run."""
    deadline = time.monotonic() + PERIODIC_EXPORT_WINDOW
    while not probe():
        assert time.monotonic() < deadline, f"The control run exported nothing in {PERIODIC_EXPORT_WINDOW}s"
        time.sleep(0.1)


def _assert_tracing_kept(
    test_agent: TestAgentAPI, test_library_factory: APMLibraryFactory, library_env: dict[str, str | None]
) -> None:
    # Control: OTEL_SDK_DISABLED=true disables tracing, so tracing below is kept by the tested
    # value rather than by a library that ignores the variable.
    with test_library_factory({**library_env, "OTEL_SDK_DISABLED": "true"}) as library:
        _emit_span(library)
    with pytest.raises(ValueError):
        test_agent.wait_for_num_traces(num=1)

    with test_library_factory(library_env) as library:
        _emit_span(library)
    assert test_agent.wait_for_num_traces(num=1)


UNSET_AND_EMPTY_VALUES = [
    pytest.param({}, id="unset"),
    pytest.param({"OTEL_SDK_DISABLED": ""}, id="empty"),
]


@scenarios.parametric
@features.otel_sdk_disabled
class Test_OTEL_SDK_DISABLED:
    # OTEL_SDK_DISABLED=true maps to DD_TRACE_ENABLED=false.
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "OTEL_SDK_DISABLED": "true",
                "DD_TRACE_ENABLED": None,
            }
        ],
    )
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_true_disables_tracing(
        self, test_agent: TestAgentAPI, test_library_factory: APMLibraryFactory, library_env: dict[str, str | None]
    ) -> None:
        # No control: test_stable_false and test_default_matches_specification check that these spans arrive.
        with test_library_factory(library_env) as library:
            _emit_span(library)
        _assert_nothing_exported(test_agent)

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "OTEL_SDK_DISABLED": "true",
                "DD_TRACE_ENABLED": "true",
            }
        ],
    )
    def test_datadog_configuration_takes_precedence(
        self, test_agent: TestAgentAPI, test_library_factory: APMLibraryFactory, library_env: dict[str, str | None]
    ) -> None:
        # Control: OTEL_SDK_DISABLED=true alone maps to DD_TRACE_ENABLED=false and disables
        # tracing, so DD_TRACE_ENABLED=true below overrides it rather than leaving tracing
        # that was never disabled.
        with test_library_factory({**library_env, "DD_TRACE_ENABLED": None}) as library:
            _emit_span(library)
        with pytest.raises(ValueError):
            test_agent.wait_for_num_traces(num=1)

        with test_library_factory(library_env) as library:
            _emit_span(library)
        assert test_agent.wait_for_num_traces(num=1)

    @pytest.mark.parametrize("library_env", [{"OTEL_SDK_DISABLED": "false"}])
    def test_stable_false(
        self, test_agent: TestAgentAPI, test_library_factory: APMLibraryFactory, library_env: dict[str, str | None]
    ) -> None:
        _assert_tracing_kept(test_agent, test_library_factory, library_env)

    @pytest.mark.parametrize("library_env", UNSET_AND_EMPTY_VALUES)
    def test_default_matches_specification(
        self, test_agent: TestAgentAPI, test_library_factory: APMLibraryFactory, library_env: dict[str, str | None]
    ) -> None:
        _assert_tracing_kept(test_agent, test_library_factory, library_env)

    # Each signal and Datadog product is opted in through its own setting, as an operator
    # auto-install would do. A control run without OTEL_SDK_DISABLED first proves that its data
    # is sent, so a missing feature cannot pass as disabled. OTEL_SDK_DISABLED=true must then
    # keep the SDK from exporting anything, whichever API produced the data and whichever
    # exporter, OpenTelemetry or Datadog, would send it.
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "OTEL_SDK_DISABLED": "true",
                "DD_METRICS_OTEL_ENABLED": "true",
            }
        ],
    )
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_true_disables_otel_metrics(
        self, test_agent: TestAgentAPI, test_library_factory: APMLibraryFactory, library_env: dict[str, str | None]
    ) -> None:
        with test_library_factory({**library_env, "OTEL_SDK_DISABLED": None}) as library:
            generate_default_counter_data_point(library, COUNTER)
        test_agent.wait_for_num_otlp_metrics(num=1)

        with test_library_factory(library_env) as library:
            generate_default_counter_data_point(library, COUNTER)
        _assert_nothing_exported(test_agent)

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "OTEL_SDK_DISABLED": "true",
                "DD_LOGS_OTEL_ENABLED": "true",
            }
        ],
    )
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_true_disables_otel_logs(
        self, test_agent: TestAgentAPI, test_library_factory: APMLibraryFactory, library_env: dict[str, str | None]
    ) -> None:
        with test_library_factory({**library_env, "OTEL_SDK_DISABLED": None}) as library:
            _emit_log(library)
        test_agent.wait_for_num_log_payloads(1)

        with test_library_factory(library_env) as library:
            _emit_log(library)
        _assert_nothing_exported(test_agent)

    @pytest.mark.parametrize("library_env", [{"OTEL_SDK_DISABLED": "true", **OTLP_TRACES_ENV}])
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_true_disables_otel_traces_over_otlp(
        self, test_agent: TestAgentAPI, test_library_factory: APMLibraryFactory, library_env: dict[str, str | None]
    ) -> None:
        with test_library_factory({**library_env, "OTEL_SDK_DISABLED": None}) as library:
            _emit_otel_span(library)
        assert _otlp_urls(test_agent, "traces"), "The control run did not export OTLP traces"

        with test_library_factory(library_env) as library:
            _emit_otel_span(library)
        _assert_nothing_exported(test_agent)

    @pytest.mark.parametrize("library_env", [{"OTEL_SDK_DISABLED": "true", **OTLP_TRACES_ENV}])
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_true_overrides_otel_traces_exporter(
        self, test_agent: TestAgentAPI, test_library_factory: APMLibraryFactory, library_env: dict[str, str | None]
    ) -> None:
        # Control: spans created through the Datadog API are exported over OTLP.
        with test_library_factory({**library_env, "OTEL_SDK_DISABLED": None}) as library:
            _emit_span(library)
        assert _otlp_urls(test_agent, "traces"), "The control run did not export OTLP traces"

        with test_library_factory(library_env) as library:
            _emit_span(library)
        _assert_nothing_exported(test_agent)

    @pytest.mark.parametrize("agent_env", [CSS_AGENT_ENV])
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "OTEL_SDK_DISABLED": "true",
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "true",
                "DD_TRACE_TRACER_METRICS_ENABLED": "true",  # java
            }
        ],
    )
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_true_disables_trace_stats(
        self, test_agent: TestAgentAPI, test_library_factory: APMLibraryFactory, library_env: dict[str, str | None]
    ) -> None:
        # Control: client-side stats are trace metrics that the SDK computes and sends to the agent.
        with test_library_factory({**library_env, "OTEL_SDK_DISABLED": None}) as library:
            _emit_span(library)
        test_agent.wait_for_num_v06_stats(num=1)

        with test_library_factory(library_env) as library:
            _emit_span(library)
        _assert_nothing_exported(test_agent)

    # The disabled run keeps the SDK default, which turns runtime metrics on in .NET and Java. With
    # DD_METRICS_OTEL_ENABLED=true an SDK may send them over OTLP instead of DogStatsD, and disabling
    # OTLP must not send them over DogStatsD again.
    @pytest.mark.parametrize(
        "library_env",
        [
            pytest.param({"OTEL_SDK_DISABLED": "true", "DD_RUNTIME_METRICS_ENABLED": None}, id="default"),
            pytest.param(
                {"OTEL_SDK_DISABLED": "true", "DD_RUNTIME_METRICS_ENABLED": None, "DD_METRICS_OTEL_ENABLED": "true"},
                id="metrics_otel_enabled",
            ),
        ],
    )
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_true_disables_runtime_metrics(
        self, test_agent: TestAgentAPI, test_library_factory: APMLibraryFactory, library_env: dict[str, str | None]
    ) -> None:
        # Control: runtime metrics are sent over DogStatsD or OTLP.
        with test_library_factory({**library_env, "OTEL_SDK_DISABLED": None, "DD_RUNTIME_METRICS_ENABLED": "true"}):
            _wait_for_periodic_export(lambda: _dogstatsd_metrics(test_agent) or _otlp_urls(test_agent, "metrics"))

        with test_library_factory(library_env):
            _assert_nothing_exported(test_agent, PERIODIC_EXPORT_WINDOW, dogstatsd=True)

    # Unlike DD_TRACE_ENABLED=true, DD_RUNTIME_METRICS_ENABLED=true does not override
    # OTEL_SDK_DISABLED=true, like DD_METRICS_OTEL_ENABLED=true.
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "OTEL_SDK_DISABLED": "true",
                "DD_RUNTIME_METRICS_ENABLED": "true",
            }
        ],
    )
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_true_overrides_runtime_metrics_enabled(
        self, test_agent: TestAgentAPI, test_library_factory: APMLibraryFactory, library_env: dict[str, str | None]
    ) -> None:
        # Control: DD_RUNTIME_METRICS_ENABLED=true alone sends runtime metrics over DogStatsD or OTLP.
        with test_library_factory({**library_env, "OTEL_SDK_DISABLED": None}):
            _wait_for_periodic_export(lambda: _dogstatsd_metrics(test_agent) or _otlp_urls(test_agent, "metrics"))

        with test_library_factory(library_env):
            _assert_nothing_exported(test_agent, PERIODIC_EXPORT_WINDOW, dogstatsd=True)

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "OTEL_SDK_DISABLED": "true",
                "OTEL_TRACES_SPAN_METRICS_ENABLED": "true",
                # Shortens the fixed 10 s export period of OTLP trace metrics.
                "_DD_TRACE_METRICS_OTEL_FLUSH_INTERVAL": "1000",
                **OTLP_TRACES_ENV,
            }
        ],
    )
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_true_disables_otlp_trace_metrics(
        self, test_agent: TestAgentAPI, test_library_factory: APMLibraryFactory, library_env: dict[str, str | None]
    ) -> None:
        # Control: the SDK computes trace metrics from the span and exports them over OTLP.
        with test_library_factory({**library_env, "OTEL_SDK_DISABLED": None}) as library:
            _emit_span(library)
            _wait_for_periodic_export(lambda: _otlp_urls(test_agent, "metrics"))

        with test_library_factory(library_env) as library:
            _emit_span(library)
            _assert_nothing_exported(test_agent, PERIODIC_EXPORT_WINDOW)
