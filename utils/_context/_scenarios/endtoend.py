import os
import pytest

from docker.models.networks import Network
from docker.types import IPAMConfig, IPAMPool

from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from utils import interfaces
from utils.interfaces._core import ProxyBasedInterfaceValidator
from utils.buddies import BuddyHostPorts
from utils.proxy.ports import ProxyPorts
from utils._context.docker import get_docker_client
from utils._context.containers import (
    WeblogContainer,
    AgentContainer,
    ProxyContainer,
    BuddyContainer,
    TestedContainer,
)
from utils._context.weblog_infrastructure import EndToEndWeblogInfra

from utils._logger import logger

from .core import Scenario, ScenarioGroup, scenario_groups as all_scenario_groups


class DockerScenario(Scenario):
    """Scenario that tests docker containers"""

    _network: Network = None

    def __init__(
        self,
        name: str,
        *,
        github_workflow: str | None,
        doc: str,
        scenario_groups: list[ScenarioGroup] | None = None,
        enable_ipv6: bool = False,
        use_proxy: bool = True,
        mocked_backend: bool = True,
        rc_api_enabled: bool = False,
        rc_backend_enabled: bool = False,
        meta_structs_disabled: bool = False,
        span_events: bool = True,
        client_drop_p0s: bool | None = None,
        extra_containers: tuple[type[TestedContainer], ...] = (),
    ) -> None:
        super().__init__(name, doc=doc, github_workflow=github_workflow, scenario_groups=scenario_groups)

        self.use_proxy = use_proxy
        self.enable_ipv6 = enable_ipv6
        self.rc_api_enabled = rc_api_enabled
        self.rc_backend_enabled = rc_backend_enabled
        self.meta_structs_disabled = False
        self.span_events = span_events
        self.client_drop_p0s = client_drop_p0s

        if not self.use_proxy and self.rc_api_enabled:
            raise ValueError("rc_api_enabled requires use_proxy")

        if self.rc_backend_enabled and not self.rc_api_enabled:
            raise ValueError("rc_backend_enabled requires rc_api_enabled")

        self._containers: list[TestedContainer] = [container() for container in extra_containers]
        """ list of containers that will be started in this scenario """

        if self.use_proxy:
            self.proxy_container = ProxyContainer(
                rc_api_enabled=rc_api_enabled,
                rc_backend_enabled=rc_backend_enabled,
                meta_structs_disabled=meta_structs_disabled,
                span_events=span_events,
                client_drop_p0s=client_drop_p0s,
                enable_ipv6=enable_ipv6,
                mocked_backend=mocked_backend,
            )

            self._containers.append(self.proxy_container)

    def get_image_list(self, library: str, weblog: str) -> list[str]:
        return [
            image_name for container in self._containers for image_name in container.get_image_list(library, weblog)
        ]

    def configure(self, config: pytest.Config):  # noqa: ARG002
        if not self.replay:
            docker_info = get_docker_client().info()
            self.components["docker.Cgroup"] = docker_info.get("CgroupVersion", None)
            self.warmups.append(self._create_network)
            self.warmups.append(self._start_containers)

        for container in reversed(self._containers):
            container.configure(host_log_folder=self.host_log_folder, replay=self.replay)

        for container in self._containers:
            self.warmups.append(container.post_start)

    def get_container_by_dd_integration_name(self, name: str):
        for container in self._containers:
            if hasattr(container, "dd_integration_service") and container.dd_integration_service == name:
                return container
        return None

    def start_interfaces_watchdog(self, interfaces: list[ProxyBasedInterfaceValidator]):
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

        # lot of issue using the default OS dependant notifiers (not working on WSL, reaching some inotify watcher
        # limits on Linux) -> using the good old bare polling system
        observer = PollingObserver()

        for interface in interfaces:
            observer.schedule(Event(interface), path=interface.log_folder)

        observer.start()

    def _create_network(self) -> None:
        name = "system-tests-ipv6" if self.enable_ipv6 else "system-tests-ipv4"

        for network in get_docker_client().networks.list(names=[name]):
            self._network = network
            logger.debug(f"Network {name} still exists")
            return

        logger.debug(f"Create network {name}")

        if self.enable_ipv6:
            self._network = get_docker_client().networks.create(
                name=name,
                driver="bridge",
                enable_ipv6=True,
                ipam=IPAMConfig(
                    driver="default",
                    pool_configs=[IPAMPool(subnet="2001:db8:1::/64")],
                ),
            )
            assert self._network.attrs["EnableIPv6"] is True, self._network.attrs
        else:
            self._network = get_docker_client().networks.create(name, check_duplicate=True)

    def _start_containers(self):
        logger.stdout("Starting containers...")
        threads = []

        for container in self._containers:
            threads.append(container.async_start(self._network))

        for thread in threads:
            thread.join()

        for container in self._containers:
            if container.healthy is False:
                pytest.exit(f"Container {container.name} can't be started", 1)

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int):  # noqa: ARG002
        self.close_targets()

    def close_targets(self):
        for container in reversed(self._containers):
            container.remove()


class EndToEndScenario(DockerScenario):
    """Scenario that implier an instrumented HTTP application shipping a datadog tracer (weblog) and an datadog agent"""

    def __init__(
        self,
        name: str,
        *,
        doc: str,
        github_workflow: str = "endtoend",
        scenario_groups: list[ScenarioGroup] | None = None,
        weblog_env: dict[str, str | None] | None = None,
        weblog_volumes: dict | None = None,
        agent_env: dict[str, str | None] | None = None,
        enable_ipv6: bool = False,
        tracer_sampling_rate: float | None = None,
        appsec_enabled: bool = True,
        iast_enabled: bool = True,
        additional_trace_header_tags: tuple[str, ...] = (),
        library_interface_timeout: int | None = None,
        agent_interface_timeout: int = 5,
        use_proxy_for_weblog: bool = True,
        use_proxy_for_agent: bool = True,
        rc_api_enabled: bool = False,
        rc_backend_enabled: bool = False,
        meta_structs_disabled: bool = False,
        span_events: bool = True,
        client_drop_p0s: bool | None = None,
        runtime_metrics_enabled: bool = False,
        backend_interface_timeout: int = 0,
        include_buddies: bool = False,
        include_opentelemetry: bool = False,
        require_api_key: bool = False,
        other_weblog_containers: tuple[type[TestedContainer], ...] = (),
    ) -> None:
        scenario_groups = [
            all_scenario_groups.all,
            all_scenario_groups.end_to_end,
            all_scenario_groups.tracer_release,
        ] + (scenario_groups or [])

        super().__init__(
            name,
            doc=doc,
            github_workflow=github_workflow,
            scenario_groups=scenario_groups,
            enable_ipv6=enable_ipv6,
            use_proxy=use_proxy_for_agent or use_proxy_for_weblog,
            rc_api_enabled=rc_api_enabled,
            rc_backend_enabled=rc_backend_enabled,
            meta_structs_disabled=meta_structs_disabled,
            span_events=span_events,
            client_drop_p0s=client_drop_p0s,
        )

        self._use_proxy_for_agent = use_proxy_for_agent
        self._use_proxy_for_weblog = use_proxy_for_weblog
        self._require_api_key = require_api_key

        self.agent_container = AgentContainer(
            use_proxy=use_proxy_for_agent, rc_backend_enabled=rc_backend_enabled, environment=agent_env
        )
        self._containers.append(self.agent_container)

        self._weblog_env = dict(weblog_env) if weblog_env else {}
        self.weblog_infra = EndToEndWeblogInfra(
            environment=self._weblog_env,
            tracer_sampling_rate=tracer_sampling_rate,
            appsec_enabled=appsec_enabled,
            iast_enabled=iast_enabled,
            runtime_metrics_enabled=runtime_metrics_enabled,
            additional_trace_header_tags=additional_trace_header_tags,
            use_proxy=use_proxy_for_weblog,
            volumes=weblog_volumes,
            other_containers=other_weblog_containers,
        )
        self._containers += self.weblog_infra.get_containers()

        # buddies are a set of weblog app that are not directly the test target
        # but are used only to test feature that invlove another app with a datadog tracer
        self.buddies: list[BuddyContainer] = []
        if include_buddies:
            # so far, only python, nodejs, java, ruby and golang are supported.
            # This list contains :
            # 1. the language
            # 2. the trace agent port where the buddy connect to the agent
            # 3. and the host port where the buddy is accessible
            supported_languages = [
                ("python", ProxyPorts.python_buddy, BuddyHostPorts.python, "datadog/system-tests:python_buddy-v2"),
                ("nodejs", ProxyPorts.nodejs_buddy, BuddyHostPorts.nodejs, "datadog/system-tests:nodejs_buddy-v1"),
                ("java", ProxyPorts.java_buddy, BuddyHostPorts.java, "datadog/system-tests:java_buddy-v1"),
                ("ruby", ProxyPorts.ruby_buddy, BuddyHostPorts.ruby, "datadog/system-tests:ruby_buddy-v2"),
                ("golang", ProxyPorts.golang_buddy, BuddyHostPorts.golang, "datadog/system-tests:golang_buddy-v2"),
            ]

            self.buddies += [
                BuddyContainer(
                    f"{language}_buddy",
                    image_name,
                    host_port=host_port,
                    trace_agent_port=trace_agent_port,
                    environment=self._weblog_env,
                )
                for language, trace_agent_port, host_port, image_name in supported_languages
            ]

        self._containers += self.buddies

        self.agent_interface_timeout = agent_interface_timeout
        self.backend_interface_timeout = backend_interface_timeout
        self._library_interface_timeout = library_interface_timeout
        self.include_opentelemetry = include_opentelemetry

    def configure(self, config: pytest.Config):
        if self._require_api_key and "DD_API_KEY" not in os.environ and not self.replay:
            pytest.exit("DD_API_KEY is required for this scenario", 1)

        self.weblog_infra.configure(config)
        self._set_containers_dependancies()

        super().configure(config)
        interfaces.agent.configure(self.host_log_folder, replay=self.replay)
        interfaces.library.configure(self.host_log_folder, replay=self.replay)
        interfaces.backend.configure(self.host_log_folder, replay=self.replay)
        interfaces.library_dotnet_managed.configure(self.host_log_folder, replay=self.replay)
        interfaces.library_stdout.configure(self.host_log_folder, replay=self.replay)
        interfaces.agent_stdout.configure(self.host_log_folder, replay=self.replay)

        if self.include_opentelemetry:
            interfaces.open_telemetry.configure(self.host_log_folder, replay=self.replay)

        for container in self.buddies:
            container.interface.configure(self.host_log_folder, replay=self.replay)

        library = self.weblog_infra.library_name

        if self._library_interface_timeout is None:
            if library == "java":
                self.library_interface_timeout = 25
            elif library in ("golang",):
                self.library_interface_timeout = 10
            elif library in ("nodejs", "ruby"):
                self.library_interface_timeout = 0
            elif library in ("php",):
                # possibly something weird on obfuscator, let increase the delay for now
                self.library_interface_timeout = 10
            elif library in ("python",):
                self.library_interface_timeout = 5
            else:
                self.library_interface_timeout = 40
        else:
            self.library_interface_timeout = self._library_interface_timeout

        if not self.replay:
            self.post_collection_warmups.append(self._start_interfaces_watchdog)
            self.post_collection_warmups.append(self._get_weblog_system_info)
            self.post_collection_warmups.append(self._wait_for_app_readiness)
            self.post_collection_warmups.append(self._set_weblog_domain)

        if (
            not self.replay
            and self.weblog_container._library is not None
            and self.agent_container.agent_version is not None
        ):
            # Both versions known from image labels: defer container startup to post-collection
            # so containers are skipped entirely when no tests are selected
            self._set_library_component()
            self._defer_container_startup()
        elif self.weblog_container._library is not None:
            self._set_library_component()
            self.warmups.append(self._set_agent_component)
        else:
            self.warmups.append(self._set_library_component)
            self.warmups.append(self._set_agent_component)

    def _defer_container_startup(self):
        """Move container startup warmups to post_collection_warmups (inserted before interface warmups)."""
        container_warmups = [self._create_network, self._start_containers] + [c.post_start for c in self._containers]
        for w in container_warmups:
            self.warmups.remove(w)
        self.post_collection_warmups[0:0] = container_warmups + [self._set_agent_component]

    def _set_containers_dependancies(self) -> None:
        if self._use_proxy_for_agent:
            self.agent_container.depends_on.append(self.proxy_container)

        for container in self.weblog_infra.get_containers():
            container.depends_on.append(self.agent_container)

            if self._use_proxy_for_weblog:
                container.depends_on.append(self.proxy_container)

        for buddy in self.buddies:
            buddy.depends_on.append(self.agent_container)

    def _get_weblog_system_info(self):
        try:
            code, (stdout, stderr) = self.weblog_container.exec_run("uname -a", demux=True)
            if code or stdout is None:
                message = f"Failed to get weblog system info: [{code}] {stderr.decode()} {stdout.decode()}"
            else:
                message = stdout.decode()
        except BaseException:
            logger.exception("can't get weblog system info")
        else:
            logger.stdout(f"Weblog system: {message.strip()}")

        if self.weblog_container.environment.get("DD_TRACE_DEBUG") == "true":
            logger.stdout("\t/!\\ Debug logs are activated in weblog")

        logger.stdout("")

    def _start_interfaces_watchdog(self):
        open_telemetry_interfaces: list[ProxyBasedInterfaceValidator] = (
            [interfaces.open_telemetry] if self.include_opentelemetry else []
        )
        super().start_interfaces_watchdog(
            [interfaces.library, interfaces.agent]
            + [container.interface for container in self.buddies]
            + open_telemetry_interfaces
        )

    def _set_weblog_domain(self):
        if self.enable_ipv6:
            self.weblog_container.set_weblog_domain_for_ipv6(self._network)

    def _set_library_component(self):
        self.components["library"] = self.library.version
        self.components[self.library.name] = self.library.version

    def _set_agent_component(self):
        self.components["agent"] = self.agent_version

    def _set_components(self):
        self._set_library_component()
        self._set_agent_component()

    def _wait_for_app_readiness(self):
        if self._use_proxy_for_weblog:
            logger.debug("Wait for app readiness")

            if not interfaces.library.ready.wait(40):
                raise ValueError("Library not ready")

            logger.debug("Library ready")

            for container in self.buddies:
                if not container.interface.ready.wait(5):
                    raise ValueError(f"{container.name} not ready")

                logger.debug(f"{container.name} ready")

        if self._use_proxy_for_agent:
            if not interfaces.agent.ready.wait(40):
                raise ValueError("Datadog agent not ready")
            logger.debug("Agent ready")

    def post_setup(self, session: pytest.Session):
        # if no test are run, skip interface tomeouts
        is_empty_test_run = session.config.option.skip_empty_scenario and len(session.items) == 0

        try:
            self._wait_and_stop_containers(force_interface_timout_to_zero=is_empty_test_run)
        finally:
            self.close_targets()

        interfaces.library_dotnet_managed.load_data()

    def _wait_and_stop_containers(self, *, force_interface_timout_to_zero: bool):
        if self.replay:
            logger.terminal.write_sep("-", "Load all data from logs")
            logger.terminal.flush()

            interfaces.library.load_data_from_logs()
            interfaces.library.check_deserialization_errors()

            for container in self.buddies:
                container.interface.load_data_from_logs()
                container.interface.check_deserialization_errors()

            interfaces.agent.load_data_from_logs()
            interfaces.agent.check_deserialization_errors()

            interfaces.backend.load_data_from_logs()

            if self.include_opentelemetry:
                interfaces.open_telemetry.load_data_from_logs()
                interfaces.open_telemetry.check_deserialization_errors()

        else:
            self._wait_interface(
                interfaces.library, 0 if force_interface_timout_to_zero else self.library_interface_timeout
            )

            self.weblog_infra.stop()
            interfaces.library.check_deserialization_errors()

            for container in self.buddies:
                # we already have waited for self.library_interface_timeout, so let's timeout=0
                self._wait_interface(container.interface, 0)
                container.stop()
                container.interface.check_deserialization_errors()

            self._wait_interface(
                interfaces.agent, 0 if force_interface_timout_to_zero else self.agent_interface_timeout
            )
            self.agent_container.stop()
            interfaces.agent.check_deserialization_errors()

            self._wait_interface(
                interfaces.backend, 0 if force_interface_timout_to_zero else self.backend_interface_timeout
            )

            if self.include_opentelemetry:
                self._wait_interface(
                    interfaces.open_telemetry, 0 if force_interface_timout_to_zero else self.backend_interface_timeout
                )

    def _wait_interface(self, interface: ProxyBasedInterfaceValidator, timeout: int):
        logger.terminal.write_sep("-", f"Wait for {interface} ({timeout}s)")
        logger.terminal.flush()

        interface.wait(timeout)

    @property
    def weblog_container(self) -> WeblogContainer:
        return self.weblog_infra.http_container

    @property
    def dd_site(self):
        return self.agent_container.dd_site

    @property
    def library(self):
        return self.weblog_container.library

    @property
    def agent_version(self):
        return self.agent_container.agent_version

    @property
    def weblog_variant(self):
        return self.weblog_container.weblog_variant

    @property
    def tracer_sampling_rate(self):
        return self.weblog_container.tracer_sampling_rate

    @property
    def appsec_rules_file(self):
        return self.weblog_container.appsec_rules_file

    @property
    def uds_socket(self):
        return self.weblog_container.uds_socket

    @property
    def uds_mode(self):
        return self.weblog_container.uds_mode

    @property
    def telemetry_heartbeat_interval(self):
        return self.weblog_container.telemetry_heartbeat_interval

    def get_junit_properties(self) -> dict[str, str]:
        result = super().get_junit_properties()

        result["dd_tags[systest.suite.context.agent]"] = self.agent_version
        result["dd_tags[systest.suite.context.library.name]"] = self.library.name
        result["dd_tags[systest.suite.context.library.version]"] = self.library.version
        result["dd_tags[systest.suite.context.weblog_variant]"] = self.weblog_variant
        result["dd_tags[systest.suite.context.appsec_rules_file]"] = self.weblog_container.appsec_rules_file or ""

        return result
