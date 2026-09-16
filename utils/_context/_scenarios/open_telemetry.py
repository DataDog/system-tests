import pytest

from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from utils._logger import logger
from utils import interfaces
from utils.interfaces._core import ProxyBasedInterfaceValidator
from utils.mocked_backend.backend_v2 import get_mocked_backend_v2_container_url
from utils._context.component_version import Version
from utils._context.constants import WeblogCategory

from utils._context.containers import (
    AgentContainer,
    OpenTelemetryCollectorContainer,
    TestedContainer,
    WeblogContainer,
)


from .core import scenario_groups
from .endtoend import DockerScenario


class OpenTelemetryScenario(DockerScenario):
    """Scenario for testing opentelemetry"""

    intake_api_key = "123456789_intake"
    collector_api_key = "123456789_collector"
    agent_api_key = "123456789_agent"

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
            mocked_backend=False,
            extra_containers=extra_containers,
            mocked_backend_v2=True,
        )
        if include_agent:
            # mocked_backend_v2 is not compatible with use_proxy: the agent can't send its traffic to
            # both the proxy and the mocked backend.
            self.agent_container = AgentContainer(use_proxy=False, mocked_backend_v2=True)
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

        dd_site = get_mocked_backend_v2_container_url()
        if self.include_intake:
            self.weblog_container.environment["OTEL_SYSTEST_INCLUDE_INTAKE"] = "True"
            self.weblog_container.environment["DD_API_KEY"] = self.intake_api_key
            self.weblog_container.environment["DD_SITE"] = dd_site
        if self.include_collector:
            self.weblog_container.environment["OTEL_SYSTEST_INCLUDE_COLLECTOR"] = "True"
            self.collector_container.environment["DD_API_KEY"] = self.collector_api_key
            self.collector_container.environment["DD_SITE"] = dd_site
        if self.include_agent:
            self.weblog_container.environment["OTEL_SYSTEST_INCLUDE_AGENT"] = "True"
            interfaces.agent.configure(self.host_log_folder, replay=self.replay)

        interfaces.backend.configure(self.host_log_folder, replay=self.replay)
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
            observer.schedule(Event(interfaces.agent), path=f"{self.host_log_folder}/interfaces/agent")

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
                interfaces.agent.load_data_from_logs()
                interfaces.agent.check_deserialization_errors()

            interfaces.backend.load_data_from_logs()
        elif self.use_proxy:
            self._wait_interface(interfaces.open_telemetry, 5)

        self.close_targets()

        interfaces.library_dotnet_managed.load_data()

    def _wait_interface(self, interface: ProxyBasedInterfaceValidator, timeout: int):
        logger.terminal.write_sep("-", f"Wait for {interface} ({timeout}s)")
        logger.terminal.flush()

        interface.wait(timeout)

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
