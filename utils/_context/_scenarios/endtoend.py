from typing import Any, Literal
import os
import pytest

from docker.models.networks import Network
from docker.types import IPAMConfig, IPAMPool

from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from utils import interfaces
from utils.interfaces._core import ProxyBasedInterfaceValidator
from utils.interfaces._feature_flag_telemetry import FeatureFlagTelemetryInterfaceValidator
from utils.buddies import BuddyHostPorts
from utils.proxy.ports import ProxyPorts
from utils._context.component_version import Version
from utils._context.docker import get_docker_client
from utils._context.containers import (
    WeblogContainer,
    AgentContainer,
    ProxyContainer,
    ServerlessSidecarContainer,
    BuddyContainer,
    TestedContainer,
)
from utils._context.weblog_infrastructure import EndToEndWeblogInfra
from utils.docker_fixtures._core import extra_hosts_for_environment
from utils.docker_fixtures._mock_ffe_agentless_backend import (
    EXPECTED_API_KEY,
    MockFFEAgentlessBackendServer,
    MockFFEAgentlessBackendStatus,
)
from utils._context.constants import WeblogCategory
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
        weblog_categories: list[WeblogCategory] | None = None,
        scenario_groups: list[ScenarioGroup] | None = None,
        enable_ipv6: bool = False,
        use_proxy: bool = True,
        mocked_backend: bool = True,
        rc_api_enabled: bool = False,
        rc_backend_enabled: bool = False,
        meta_structs_disabled: bool = False,
        span_events: bool = True,
        client_drop_p0s: bool | None = None,
        obfuscation_version: int | None | Literal["MISSING"] = None,
        extra_containers: tuple[type[TestedContainer], ...] = (),
    ) -> None:
        super().__init__(
            name,
            doc=doc,
            github_workflow=github_workflow,
            scenario_groups=scenario_groups,
            weblog_categories=weblog_categories,
        )

        self.use_proxy = use_proxy
        self.enable_ipv6 = enable_ipv6
        self.rc_api_enabled = rc_api_enabled
        self.rc_backend_enabled = rc_backend_enabled
        self.meta_structs_disabled = False
        self.span_events = span_events
        self.client_drop_p0s = client_drop_p0s
        self.obfuscation_version = obfuscation_version

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
                obfuscation_version=obfuscation_version,
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
    """Scenario with an instrumented HTTP application and an optional Datadog Agent."""

    def __init__(
        self,
        name: str,
        *,
        doc: str,
        github_workflow: str = "endtoend",
        weblog_categories: list[WeblogCategory],
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
        use_proxy_for_telemetry: bool = False,
        rc_api_enabled: bool = False,
        rc_backend_enabled: bool = False,
        meta_structs_disabled: bool = False,
        span_events: bool = True,
        client_drop_p0s: bool | None = None,
        obfuscation_version: int | None | Literal["MISSING"] = None,
        runtime_metrics_enabled: bool = False,
        backend_interface_timeout: int = 0,
        include_buddies: bool = False,
        include_agent: bool = True,
        include_default_scenario_groups: bool = True,
        include_opentelemetry: bool = False,
        require_api_key: bool = False,
        other_weblog_containers: tuple[type[TestedContainer], ...] = (),
    ) -> None:
        default_scenario_groups = (
            [
                all_scenario_groups.all,
                all_scenario_groups.end_to_end,
                all_scenario_groups.tracer_release,
            ]
            if include_default_scenario_groups
            else []
        )
        scenario_groups = default_scenario_groups + (scenario_groups or [])

        super().__init__(
            name,
            doc=doc,
            github_workflow=github_workflow,
            scenario_groups=scenario_groups,
            weblog_categories=weblog_categories,
            enable_ipv6=enable_ipv6,
            use_proxy=(include_agent and use_proxy_for_agent) or use_proxy_for_weblog or use_proxy_for_telemetry,
            rc_api_enabled=rc_api_enabled,
            rc_backend_enabled=rc_backend_enabled,
            meta_structs_disabled=meta_structs_disabled,
            span_events=span_events,
            client_drop_p0s=client_drop_p0s,
            obfuscation_version=obfuscation_version,
        )

        if include_buddies and not include_agent:
            raise ValueError("include_buddies requires include_agent")

        self.include_agent = include_agent
        self._use_proxy_for_agent = include_agent and use_proxy_for_agent
        self._use_proxy_for_weblog = use_proxy_for_weblog
        self._use_proxy_for_telemetry = use_proxy_for_telemetry
        self._require_api_key = require_api_key

        self.agent_container = AgentContainer(
            use_proxy=use_proxy_for_agent, rc_backend_enabled=rc_backend_enabled, environment=agent_env
        )
        if include_agent:
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

    def get_image_list(self, library: str, weblog: str) -> list[str]:
        return [
            image_name for container in self._containers for image_name in container.get_image_list(library, weblog)
        ] + self.weblog_infra.get_image_list(library, weblog)

    def configure(self, config: pytest.Config):
        if self._require_api_key and "DD_API_KEY" not in os.environ and not self.replay:
            pytest.exit("DD_API_KEY is required for this scenario", 1)

        self.weblog_infra.configure(config)
        self._containers += list(self.weblog_infra.get_containers())

        self._set_containers_dependancies()

        super().configure(config)
        if self.include_agent:
            interfaces.agent.configure(self.host_log_folder, replay=self.replay)
        interfaces.library.configure(self.host_log_folder, replay=self.replay)
        interfaces.backend.configure(self.host_log_folder, replay=self.replay)
        interfaces.library_dotnet_managed.configure(self.host_log_folder, replay=self.replay)
        interfaces.library_stdout.configure(self.host_log_folder, replay=self.replay)
        if self.include_agent:
            interfaces.agent_stdout.configure(self.host_log_folder, replay=self.replay)

        if self.include_opentelemetry:
            interfaces.open_telemetry.configure(self.host_log_folder, replay=self.replay)

        for container in self.buddies:
            container.interface.configure(self.host_log_folder, replay=self.replay)

        library = self.weblog_infra.library_name

        if library in ("nodejs", "python"):
            # Node.js starts the poll interval only after receiving the previous response, so faster
            # polling is safe. Some other languages use a fixed interval regardless of response
            # timing, or have bugs that cause race conditions when the interval is too short.
            self.weblog_infra.library_container.environment.setdefault("DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS", "0.2")

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
            self.warmups.insert(1, self._start_interfaces_watchdog)
            self.warmups.append(self.weblog_infra.get_weblog_system_info)
            self.warmups.append(self._wait_for_app_readiness)
            self.warmups.append(self._set_weblog_domain)
        self.warmups.append(self._set_components)

    def _set_containers_dependancies(self) -> None:
        if self._use_proxy_for_agent:
            self.agent_container.depends_on.append(self.proxy_container)

        proxy_container = self.proxy_container if self._use_proxy_for_weblog else None
        agent_container = self.agent_container if self.include_agent else None
        self.weblog_infra.set_weblog_dependencies(agent_container, proxy_container)

        for buddy in self.buddies:
            buddy.depends_on.append(self.agent_container)

    def _start_interfaces_watchdog(self):
        open_telemetry_interfaces: list[ProxyBasedInterfaceValidator] = (
            [interfaces.open_telemetry] if self.include_opentelemetry else []
        )
        agent_interfaces = [interfaces.agent] if self.include_agent else []
        super().start_interfaces_watchdog(
            [interfaces.library]
            + agent_interfaces
            + [container.interface for container in self.buddies]
            + open_telemetry_interfaces
        )

    def _set_weblog_domain(self):
        if self.enable_ipv6:
            self.weblog_container.set_weblog_domain_for_ipv6(self._network)

    def _set_components(self):
        if self.include_agent:
            self.components["agent"] = self.agent_version
        self.components["library"] = self.library.version
        self.components[self.library.name] = self.library.version

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

            if self.include_agent:
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

            if self.include_agent:
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
        if self.include_agent:
            return self.agent_container.dd_site
        return self.weblog_container.environment.get("DD_SITE", "datad0g.com")

    @property
    def library(self):
        return self.weblog_infra.library

    @property
    def agent_version(self):
        return self.agent_container.agent_version if self.include_agent else Version("0.0.0")

    @property
    def weblog_variant(self) -> str:
        return self.weblog_infra.weblog_variant

    @property
    def tracer_sampling_rate(self):
        return self.weblog_container.tracer_sampling_rate

    @property
    def uds_socket(self) -> str | None:
        return self.weblog_infra.uds_socket

    @property
    def uds_mode(self) -> bool:
        return self.weblog_infra.uds_mode

    @property
    def telemetry_heartbeat_interval(self):
        return self.weblog_container.telemetry_heartbeat_interval

    def get_junit_properties(self) -> dict[str, str]:
        result = super().get_junit_properties()

        result["dd_tags[systest.suite.context.agent]"] = self.agent_version
        result["dd_tags[systest.suite.context.library.name]"] = self.library.name
        result["dd_tags[systest.suite.context.library.version]"] = self.library.version
        result["dd_tags[systest.suite.context.weblog_variant]"] = self.weblog_variant
        result["dd_tags[systest.suite.context.appsec_rules_file]"] = self.appsec_rules_file or ""

        return result

    @property
    def appsec_rules_file(self) -> str | None:
        return self.weblog_infra.appsec_rules_file


class DdTraceEndToEndScenario(EndToEndScenario):
    """Scenario targeting basic feature of a dd-trace library (not SSI or lambda)"""

    def __init__(
        self,
        name: str,
        *,
        doc: str,
        additional_trace_header_tags: tuple[str, ...] = (),
        agent_env: dict[str, str | None] | None = None,
        appsec_enabled: bool = True,
        backend_interface_timeout: int = 0,
        client_drop_p0s: bool | None = None,
        iast_enabled: bool = True,
        include_agent: bool = True,
        include_default_scenario_groups: bool = True,
        include_opentelemetry: bool = False,
        library_interface_timeout: int | None = None,
        meta_structs_disabled: bool = False,
        obfuscation_version: int | None | Literal["MISSING"] = None,
        other_weblog_containers: tuple[type[TestedContainer], ...] = (),
        rc_api_enabled: bool = False,
        rc_backend_enabled: bool = False,
        require_api_key: bool = False,
        runtime_metrics_enabled: bool = False,
        scenario_groups: list[ScenarioGroup] | None = None,
        span_events: bool = True,
        tracer_sampling_rate: float | None = None,
        use_proxy_for_agent: bool = True,
        use_proxy_for_telemetry: bool = False,
        use_proxy_for_weblog: bool = True,
        weblog_env: dict[str, str | None] | None = None,
        weblog_volumes: dict | None = None,
    ) -> None:
        super().__init__(
            name,
            additional_trace_header_tags=additional_trace_header_tags,
            agent_env=agent_env,
            appsec_enabled=appsec_enabled,
            backend_interface_timeout=backend_interface_timeout,
            client_drop_p0s=client_drop_p0s,
            doc=doc,
            iast_enabled=iast_enabled,
            include_agent=include_agent,
            include_default_scenario_groups=include_default_scenario_groups,
            include_opentelemetry=include_opentelemetry,
            library_interface_timeout=library_interface_timeout,
            meta_structs_disabled=meta_structs_disabled,
            obfuscation_version=obfuscation_version,
            other_weblog_containers=other_weblog_containers,
            rc_api_enabled=rc_api_enabled,
            rc_backend_enabled=rc_backend_enabled,
            require_api_key=require_api_key,
            runtime_metrics_enabled=runtime_metrics_enabled,
            scenario_groups=scenario_groups,
            span_events=span_events,
            tracer_sampling_rate=tracer_sampling_rate,
            use_proxy_for_agent=use_proxy_for_agent,
            use_proxy_for_telemetry=use_proxy_for_telemetry,
            use_proxy_for_weblog=use_proxy_for_weblog,
            weblog_categories=[WeblogCategory.dd_trace],
            weblog_env=weblog_env,
            weblog_volumes=weblog_volumes,
        )


class FeatureFlaggingAgentlessEndToEndScenario(DdTraceEndToEndScenario):
    """FFE end-to-end scenario with UFC available before the weblog starts."""

    _mock_backend: MockFFEAgentlessBackendServer | None = None
    _last_mock_backend_status: MockFFEAgentlessBackendStatus | None = None

    def __init__(
        self,
        name: str,
        *,
        telemetry_route: Literal["none", "sidecar", "direct"] = "none",
        weblog_env: dict[str, str | None] | None = None,
        other_weblog_containers: tuple[type[TestedContainer], ...] = (),
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        self.telemetry_route = telemetry_route
        environment = dict(weblog_env or {})

        if telemetry_route != "none":
            environment |= {
                "DD_FEATURE_FLAGS_TELEMETRY_TRANSPORT": "auto",
                "DD_FLAGGING_EVALUATION_COUNTS_ENABLED": "true",
                "DD_METRICS_OTEL_ENABLED": "true",
                "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL": "http/protobuf",
                "OTEL_METRIC_EXPORT_INTERVAL": "1000",
                "DD_PROXY_HTTPS": f"http://proxy:{ProxyPorts.ffe_direct}",
            }

        if telemetry_route == "sidecar":
            environment |= {
                "DD_AGENT_HOST": "ffe-serverless-sidecar",
                "DD_TRACE_AGENT_PORT": "8126",
                "DD_TRACE_AGENT_URL": "http://ffe-serverless-sidecar:8126",
                "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT": "http://ffe-serverless-sidecar:4318/v1/metrics",
            }
            other_weblog_containers += (ServerlessSidecarContainer,)
        elif telemetry_route == "direct":
            environment |= {
                "DD_API_KEY": EXPECTED_API_KEY,
                "DD_SITE": "datad0g.com",
                "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT": f"http://proxy:{ProxyPorts.ffe_direct}/v1/metrics",
                "OTEL_EXPORTER_OTLP_METRICS_HEADERS": (f"dd-api-key={EXPECTED_API_KEY},dd-protocol=otlp"),
            }

        super().__init__(
            name,
            weblog_env=environment,
            other_weblog_containers=other_weblog_containers,
            use_proxy_for_telemetry=telemetry_route != "none",
            **kwargs,
        )

    @property
    def telemetry_interface(self) -> FeatureFlagTelemetryInterfaceValidator:
        if self.telemetry_route == "sidecar":
            return interfaces.ffe_sidecar
        if self.telemetry_route == "direct":
            return interfaces.ffe_direct
        raise ValueError("This scenario does not capture Feature Flags telemetry")

    @property
    def unexpected_telemetry_interface(self) -> FeatureFlagTelemetryInterfaceValidator:
        if self.telemetry_route == "sidecar":
            return interfaces.ffe_direct
        if self.telemetry_route == "direct":
            return interfaces.ffe_sidecar
        raise ValueError("This scenario does not capture Feature Flags telemetry")

    def configure(self, config: pytest.Config) -> None:
        if not self.replay:
            worker_id = os.environ.get("PYTEST_XDIST_WORKER", "master")
            self._start_mock_backend(worker_id)

        try:
            if self.telemetry_route != "none":
                interfaces.ffe_sidecar.configure(self.host_log_folder, replay=self.replay)
                interfaces.ffe_direct.configure(self.host_log_folder, replay=self.replay)
            super().configure(config)
        except BaseException:
            self._stop_mock_backend()
            raise

    def _set_containers_dependancies(self) -> None:
        super()._set_containers_dependancies()
        if not self._use_proxy_for_telemetry:
            return

        self.weblog_infra.library_container.depends_on.append(self.proxy_container)
        for container in self._containers:
            if isinstance(container, ServerlessSidecarContainer):
                container.depends_on.append(self.proxy_container)

    def _start_interfaces_watchdog(self) -> None:
        super()._start_interfaces_watchdog()
        if self.telemetry_route != "none":
            self.start_interfaces_watchdog([interfaces.ffe_sidecar, interfaces.ffe_direct])

    def _wait_and_stop_containers(self, *, force_interface_timout_to_zero: bool) -> None:
        super()._wait_and_stop_containers(force_interface_timout_to_zero=force_interface_timout_to_zero)
        if self.telemetry_route == "none":
            return

        if self.replay:
            interfaces.ffe_sidecar.load_data_from_logs()
            interfaces.ffe_direct.load_data_from_logs()
        else:
            for container in self._containers:
                if isinstance(container, ServerlessSidecarContainer):
                    container.stop()
            self._wait_interface(
                self.telemetry_interface,
                0 if force_interface_timout_to_zero else 5,
            )

        interfaces.ffe_sidecar.check_deserialization_errors()
        interfaces.ffe_direct.check_deserialization_errors()

    def _start_mock_backend(self, worker_id: str) -> None:
        assert self._mock_backend is None, "mock FFE agentless backend is already running"

        self._mock_backend = MockFFEAgentlessBackendServer(worker_id)
        self._mock_backend.reset()

        environment = self.weblog_infra.library_container.environment
        environment |= {
            "DD_API_KEY": EXPECTED_API_KEY,
            "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_BASE_URL": self._mock_backend.library_config_url,
        }
        self.weblog_infra.library_container.extra_hosts = extra_hosts_for_environment(environment)

    def mock_backend_status(self) -> MockFFEAgentlessBackendStatus | None:
        if self._mock_backend is not None:
            return self._mock_backend.status()
        return self._last_mock_backend_status

    def _stop_mock_backend(self) -> None:
        if self._mock_backend is None:
            return

        self._last_mock_backend_status = self._mock_backend.status()
        self._mock_backend.close()
        self._mock_backend = None

    def close_targets(self) -> None:
        try:
            super().close_targets()
        finally:
            self._stop_mock_backend()


class GraphQlEndToEndScenario(EndToEndScenario):
    """Scenario targeting GraphQl feature of a dd-trace library"""

    def __init__(
        self,
        name: str,
        *,
        doc: str,
        agent_env: dict[str, str | None] | None = None,
        scenario_groups: list[ScenarioGroup] | None = None,
        weblog_env: dict[str, str | None] | None = None,
        weblog_volumes: dict | None = None,
    ) -> None:
        super().__init__(
            name,
            agent_env=agent_env,
            doc=doc,
            scenario_groups=scenario_groups,
            weblog_categories=[WeblogCategory.dd_trace_graphql],
            weblog_env=weblog_env,
            weblog_volumes=weblog_volumes,
        )
