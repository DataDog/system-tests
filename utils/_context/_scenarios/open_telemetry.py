import os

import pytest

from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from utils._logger import logger
from utils import interfaces
from utils.interfaces._core import ProxyBasedInterfaceValidator
from utils._context.component_version import Version
from utils._context.constants import WeblogCategory

from utils._context.containers import (
    AgentContainer,
    MockedBackendContainer,
    OpenTelemetryCollectorContainer,
    TestedContainer,
    WeblogContainer,
    CassandraContainer,
    KafkaContainer,
    MongoContainer,
    MsSqlServerContainer,
    MySqlContainer,
    PostgresContainer,
    RabbitMqContainer,
)

from ._core import DockerScenario, FakeDatadogKey, scenario_groups
from utils.mocked_backend import MOCKED_BACKEND_DOMAIN
from utils.proxy.ports import ProxyPorts


class _OpenTelemetryScenario(DockerScenario):
    """Scenario for testing opentelemetry"""

    def __init__(
        self,
        name: str,
        *,
        doc: str,
        weblog_env: dict | None = None,
        include_agent: bool = True,
        include_collector: bool = True,
        include_intake: bool = True,
        extra_containers: tuple[type[TestedContainer], ...] = (),
    ) -> None:
        super().__init__(
            name,
            doc=doc,
            github_workflow="endtoend",
            scenario_groups=[scenario_groups.all, scenario_groups.open_telemetry],
            weblog_categories=[WeblogCategory.open_telemetry],
            use_proxy=True,
            extra_containers=extra_containers,
        )
        self.use_proxy_for_agent = False
        """The agent sends to the mocked backend: interfaces.agent is not used"""
        if include_agent:
            # it serves HTTPS on its domain, and on the intake hostnames derived from it (see MOCKED_BACKEND_DOMAIN)
            self.mocked_backend_container = MockedBackendContainer(tls=True)
            self._containers.append(self.mocked_backend_container)
            self.agent_container = AgentContainer(
                dd_api_key=FakeDatadogKey.DEFAULT,
                use_proxy=False,
                # the mocked backend serves remote config, signed with the TUF roots set by rc_backend_enabled
                rc_backend_enabled=True,
                mocked_backend=True,
            )
            self.agent_container.depends_on.append(self.mocked_backend_container)
            # after the mocked backend: close_targets removes the containers in reverse order, so it receives
            # what the agent sends until the agent stops
            self._containers.append(self.agent_container)
        if include_collector:
            self.collector_container = OpenTelemetryCollectorContainer()
            self._containers.append(self.collector_container)
        self.weblog_container = WeblogContainer(environment=weblog_env)
        if include_agent:
            self.weblog_container.depends_on.append(self.agent_container)
        if include_collector:
            self.weblog_container.depends_on.append(self.collector_container)
        self._containers.append(self.weblog_container)
        self.include_agent = include_agent
        self.include_collector = include_collector
        self.include_intake = include_intake

    def configure(self, config: pytest.Config):
        super().configure(config)
        self._check_env_vars()

        dd_site = MOCKED_BACKEND_DOMAIN
        if self.include_intake:
            self.weblog_container.environment["OTEL_SYSTEST_INCLUDE_INTAKE"] = "True"
            self.weblog_container.environment["DD_API_KEY"] = os.environ.get("DD_API_KEY_2")
            self.weblog_container.environment["DD_SITE"] = dd_site
        if self.include_collector:
            self.weblog_container.environment["OTEL_SYSTEST_INCLUDE_COLLECTOR"] = "True"
            self.collector_container.environment["DD_API_KEY"] = os.environ.get("DD_API_KEY_3")
            self.collector_container.environment["DD_SITE"] = dd_site
        if self.include_agent:
            self.weblog_container.environment["OTEL_SYSTEST_INCLUDE_AGENT"] = "True"
            interfaces.mocked_backend.configure(self.host_log_folder, replay=self.replay)

        interfaces.open_telemetry.configure(self.host_log_folder, replay=self.replay)
        interfaces.library_dotnet_managed.configure(self.host_log_folder, replay=self.replay)

        if not self.replay:
            self.warmups.insert(0, self._start_interface_watchdog)
            self.warmups.append(self._wait_for_app_readiness)

        self.warmups.append(self._set_components)

    def _set_components(self):
        self.components["agent"] = self.agent_version
        self.components["library"] = self.library.version
        self.components[self.library.name] = self.library.version

    def _start_interface_watchdog(self):
        class Event(FileSystemEventHandler):
            def __init__(self, interface: ProxyBasedInterfaceValidator) -> None:
                super().__init__()
                self.interface = interface

            def _ingest(self, event: FileSystemEvent):
                if event.is_directory:
                    return

                self.interface.ingest_file(event.src_path)

            on_modified = _ingest
            on_created = _ingest

        observer = PollingObserver()
        observer.schedule(
            Event(interfaces.open_telemetry), path=f"{self.host_log_folder}/interfaces/open_telemetry", recursive=True
        )
        if self.include_agent:
            observer.schedule(Event(interfaces.mocked_backend), path=interfaces.mocked_backend.log_folder)

        observer.start()

    def _wait_for_app_readiness(self):
        supported_libraries = ("java_otel", "nodejs_otel", "python_otel")
        if self.library.name not in supported_libraries:
            pytest.exit(f"{self.name} scenario support only thoses libraries: {supported_libraries}", 1)

        if self.use_proxy:
            logger.debug("Wait for app readiness")

            if not interfaces.open_telemetry.ready.wait(40):
                raise ValueError("Open telemetry interface not ready")
            logger.debug("Open telemetry ready")

    def post_setup(self, session: pytest.Session):  # noqa: ARG002
        if self.replay:
            logger.terminal.write(
                "\nReplay mode is not fully functional for this scenario, you may encounter errors\n",
                bold=True,
                red=True,
            )
            logger.terminal.write_sep("-", "Load all data from logs")
            logger.terminal.flush()

            interfaces.open_telemetry.load_data_from_logs()
            interfaces.open_telemetry.check_deserialization_errors()

            if self.include_agent:
                interfaces.mocked_backend.load_data_from_logs()
                interfaces.mocked_backend.check_deserialization_errors()
        elif self.use_proxy:
            self._wait_interface(interfaces.open_telemetry, 5)
            if self.include_agent:
                # gives the agent time to send what it received: close_targets removes it without waiting for that
                self._wait_interface(interfaces.mocked_backend, 5)

        self.close_targets()

        if self.include_agent and not self.replay:
            # the watchdog polls files about once per second: the last ones may not be ingested yet. Nothing else
            # can arrive now, so ingest them all instead of waiting an arbitrary time
            interfaces.mocked_backend.ingest_all_files()
            interfaces.mocked_backend.check_deserialization_errors()

        interfaces.library_dotnet_managed.load_data()

    def _wait_interface(self, interface: ProxyBasedInterfaceValidator, timeout: int):
        logger.terminal.write_sep("-", f"Wait for {interface} ({timeout}s)")
        logger.terminal.flush()

        interface.wait(timeout)

    def _check_env_vars(self):
        if self.include_intake:
            assert all(key in os.environ for key in ("DD_API_KEY_2", "DD_APP_KEY_2")), (
                "OTel E2E test requires DD_API_KEY_2 and DD_APP_KEY_2"
            )
        if self.include_collector:
            assert all(key in os.environ for key in ("DD_API_KEY_3", "DD_APP_KEY_3")), (
                "OTel E2E test requires DD_API_KEY_3 and DD_APP_KEY_3"
            )

    @property
    def library(self):
        return self.weblog_container.library

    @property
    def agent_version(self):
        return self.agent_container.agent_version if self.include_agent else Version("0.0.0")

    @property
    def weblog_variant(self):
        return self.weblog_container.weblog_variant

    def get_libraries(self) -> set[str] | None:
        # return {"python_otel", "java_otel", "nodejs_otel"}
        # nodejs_otel is broken since a while
        return {"python_otel", "java_otel"}


class OtelIntegrations(_OpenTelemetryScenario):
    def __init__(self) -> None:
        super().__init__(
            "OTEL_INTEGRATIONS",
            weblog_env={
                "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
                "OTEL_EXPORTER_OTLP_ENDPOINT": f"http://proxy:{ProxyPorts.open_telemetry_weblog}",
                "OTEL_EXPORTER_OTLP_TRACES_HEADERS": "dd-protocol=otlp,dd-otlp-path=agent",
                "OTEL_INTEGRATIONS_TEST": True,
            },
            include_intake=False,
            include_collector=False,
            extra_containers=(
                MsSqlServerContainer,
                MySqlContainer,
                RabbitMqContainer,
                KafkaContainer,
                MongoContainer,
                CassandraContainer,
                PostgresContainer,
            ),
            doc=(
                "We use the open telemetry library to automatically instrument the weblogs instead of using the DD "
                "library."
                "This scenario represents this case in the integration with different external systems, for example "
                "the interaction with sql database."
            ),
        )
