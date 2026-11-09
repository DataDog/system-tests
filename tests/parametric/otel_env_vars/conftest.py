from collections.abc import Callable, Generator
from contextlib import AbstractContextManager, contextmanager
import time

from tests.parametric.conftest import APMLibrary
from tests.parametric.utils import generate_default_counter_data_point
from utils import pytest, scenarios
from utils.docker_fixtures import TestAgentAPI, new_test_id
from utils.docker_fixtures._test_agent import AgentRequest
from utils.docker_fixtures.parametric import LogLevel


APMLibraryFactory = Callable[[dict[str, str | None]], AbstractContextManager[APMLibrary]]
DefaultProtocol = Callable[[str], str]

CONTENT_TYPE_PROTOCOLS = {"application/x-protobuf": "http/protobuf", "application/json": "http/json"}

# SDK defaults cannot change during a session, so each signal is observed once
# per worker. None records that the SDK exported nothing with the protocol unset.
_default_protocols: dict[str, str | None] = {}


# This fixture serves three small use cases: the SDK-default comparison in
# OTEL_PROPAGATORS and OTEL_LOG_LEVEL, the control runs in OTEL_SDK_DISABLED,
# and the default observation for OTEL_EXPORTER_OTLP_*_PROTOCOL. Do not use it
# outside these tests; contact the apm-shared-testing team if another use case
# needs it.
@pytest.fixture
def test_library_factory(
    worker_id: str,
    request: pytest.FixtureRequest,
    test_agent: TestAgentAPI,
    library_extra_command_arguments: list[str],
) -> APMLibraryFactory:
    """Observe fresh SDK processes sequentially without sharing agent data."""

    @contextmanager
    def create(library_env: dict[str, str | None]) -> Generator[APMLibrary, None, None]:
        test_agent.clear()
        scenarios.parametric.parametrized_tests_metadata[request.node.nodeid] = library_env
        with (
            scenarios.parametric.get_apm_library(
                request=request,
                worker_id=worker_id,
                test_id=new_test_id(),
                test_agent=test_agent,
                library_env=library_env,
                library_extra_command_arguments=library_extra_command_arguments,
            ) as library,
            library,
        ):
            yield library

    return create


def _signal_env(signal: str) -> dict[str, str | None]:
    if signal == "traces":
        # Datadog names its trace switch in the singular, traces are only
        # exported over OTLP when it is selected as the exporter, and OTLP trace
        # export always runs with OTel semantics.
        return {
            "DD_TRACE_OTEL_ENABLED": "true",
            "DD_TRACE_OTEL_SEMANTICS_ENABLED": "true",
            "OTEL_TRACES_EXPORTER": "otlp",
        }
    return {f"DD_{signal.upper()}_OTEL_ENABLED": "true"}


def _export(library: APMLibrary, signal: str) -> None:
    if signal == "logs":
        library.create_logger("default-protocol", LogLevel.INFO)
        library.write_log("default-protocol", LogLevel.INFO, "default-protocol")
    elif signal == "traces":
        with library.dd_start_span("default-protocol"):
            pass
        library.dd_flush()
    else:
        generate_default_counter_data_point(library, "default_protocol_counter")


def _export_requests(test_agent: TestAgentAPI, signal: str) -> list[AgentRequest]:
    deadline = time.monotonic() + 5
    while True:
        requests = [request for request in test_agent.requests() if request["url"].endswith(f"/v1/{signal}")]
        if requests or time.monotonic() > deadline:
            return requests
        time.sleep(0.1)


@pytest.fixture
def default_protocol(
    test_agent: TestAgentAPI,
    test_agent_otlp_http_port: int,
    test_agent_otlp_grpc_port: int,
    test_library_factory: APMLibraryFactory,
) -> DefaultProtocol:
    """The protocol this SDK uses for a signal when no protocol variable is set.

    OTel permits retaining a historical gRPC default, and SDKs migrate between
    defaults, so the default is observed from an unset control run instead of
    being hardcoded. The returned callable observes lazily, so tests that never
    need the default do not depend on it.
    """

    def observe(signal: str) -> str | None:
        env: dict[str, str | None] = {
            **_signal_env(signal),
            "OTEL_EXPORTER_OTLP_PROTOCOL": None,
            f"OTEL_EXPORTER_OTLP_{signal.upper()}_PROTOCOL": None,
        }
        # A gRPC exporter cannot deliver to the HTTP listener, so a request there
        # proves an HTTP transport and its content type identifies the encoding.
        endpoint = f"http://{test_agent.container_name}:{test_agent_otlp_http_port}"
        with test_library_factory({**env, "OTEL_EXPORTER_OTLP_ENDPOINT": endpoint}) as library:
            _export(library, signal)
        if requests := _export_requests(test_agent, signal):
            headers = {name.lower(): value for name, value in requests[0]["headers"].items()}
            content_type = headers.get("content-type", "").split(";")[0]
            assert content_type in CONTENT_TYPE_PROTOCOLS, headers
            return CONTENT_TYPE_PROTOCOLS[content_type]

        # The gRPC listener forwards decoded payloads to the HTTP listener, so a
        # request recorded after this run proves delivery over gRPC.
        endpoint = f"http://{test_agent.container_name}:{test_agent_otlp_grpc_port}"
        with test_library_factory({**env, "OTEL_EXPORTER_OTLP_ENDPOINT": endpoint}) as library:
            _export(library, signal)
        return "grpc" if _export_requests(test_agent, signal) else None

    def get(signal: str) -> str:
        if signal not in _default_protocols:
            _default_protocols[signal] = observe(signal)
            # The control runs must not leak payloads into the tested process.
            test_agent.clear()
        protocol = _default_protocols[signal]
        assert protocol is not None, f"No OTLP {signal} export over HTTP or gRPC with the protocol unset"
        return protocol

    return get
