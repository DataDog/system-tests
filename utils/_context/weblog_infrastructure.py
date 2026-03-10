from abc import ABC, abstractmethod
import json
import os
from pathlib import Path
import sys

from docker.models.networks import Network
import pytest

from utils._context.component_version import ComponentVersion
from utils._context.containers import (
    CassandraContainer,
    DummyServerContainer,
    EnvoyContainer,
    ExternalProcessingContainer,
    HAProxyContainer,
    KafkaContainer,
    MongoContainer,
    MsSqlServerContainer,
    MySqlContainer,
    PostgresContainer,
    RabbitMqContainer,
    StreamProcessingOffloadContainer,
    TestedContainer,
    WeblogContainer,
)
from utils._logger import logger
from utils._weblog import weblog


PROXY_WEBLOGS: dict[str, str] = {
    "envoy": "envoy",
    "haproxy-spoa": "haproxy",
}

EndToEndHttpContainer = WeblogContainer | EnvoyContainer | HAProxyContainer
EndToEndLibraryContainer = WeblogContainer | ExternalProcessingContainer | StreamProcessingOffloadContainer


class WeblogInfra(ABC):
    """Infrastructure shipping the HTTP app (aka weblog) instrumented by a library."""

    @abstractmethod
    def configure(self, config: pytest.Config, host_log_folder: str) -> None:
        """Perform any configuration. Executed only if the weblog will be used"""

    @abstractmethod
    def stop(self) -> None:
        """Stop the tested infra"""

    @abstractmethod
    def get_containers(self) -> tuple[TestedContainer, ...]:
        pass

    @abstractmethod
    def get_image_list(self, library: str, weblog_variant: str) -> list[str]:
        pass


class EndToEndInfra(WeblogInfra):
    @property
    @abstractmethod
    def http_container(self) -> EndToEndHttpContainer:
        pass

    @property
    @abstractmethod
    def library_container(self) -> EndToEndLibraryContainer:
        pass

    @property
    @abstractmethod
    def library_name(self) -> str:
        pass

    @property
    def library(self) -> ComponentVersion:
        return self.library_container.library

    @property
    @abstractmethod
    def weblog_variant(self) -> str:
        pass

    @property
    def tracer_sampling_rate(self) -> float | None:
        return getattr(self.library_container, "tracer_sampling_rate", None)

    @property
    def appsec_rules_file(self) -> str | None:
        return getattr(self.library_container, "appsec_rules_file", None)

    @property
    def uds_socket(self) -> str | None:
        return getattr(self.library_container, "uds_socket", None)

    @property
    def uds_mode(self) -> bool:
        return getattr(self.library_container, "uds_mode", False)

    @property
    def telemetry_heartbeat_interval(self) -> int | float:
        return getattr(self.library_container, "telemetry_heartbeat_interval", 2)

    def set_weblog_domain_for_ipv6(self, network: Network) -> None:
        set_weblog_domain_for_ipv6 = getattr(self.http_container, "set_weblog_domain_for_ipv6", None)
        if callable(set_weblog_domain_for_ipv6):
            set_weblog_domain_for_ipv6(network)
            return

        if sys.platform == "linux":
            weblog.domain = self.http_container.network_ip(network)
            logger.info("Linux => Using Container IPv6 address [%s] as weblog domain", weblog.domain)
            return

        if sys.platform == "darwin":
            logger.info("Mac => Using localhost as weblog domain")
            return

        pytest.exit(f"Unsupported platform {sys.platform} with ipv6 enabled", 1)


class LibraryEndToEndInfra(EndToEndInfra):
    def __init__(
        self,
        *,
        environment: dict[str, str | None] | None = None,
        tracer_sampling_rate: float | None = None,
        appsec_enabled: bool = True,
        iast_enabled: bool = True,
        runtime_metrics_enabled: bool = False,
        additional_trace_header_tags: tuple[str, ...] = (),
        use_proxy: bool = True,
        volumes: dict | None = None,
        other_containers: tuple[type[TestedContainer], ...] = (),
    ) -> None:
        self._environment = environment
        self._tracer_sampling_rate = tracer_sampling_rate
        self._appsec_enabled = appsec_enabled
        self._iast_enabled = iast_enabled
        self._runtime_metrics_enabled = runtime_metrics_enabled
        self._additional_trace_header_tags = additional_trace_header_tags
        self._use_proxy = use_proxy
        self._volumes = volumes
        self._other_container_types = other_containers
        self._http_container = WeblogContainer(
            environment=environment,
            tracer_sampling_rate=tracer_sampling_rate,
            appsec_enabled=appsec_enabled,
            iast_enabled=iast_enabled,
            runtime_metrics_enabled=runtime_metrics_enabled,
            additional_trace_header_tags=additional_trace_header_tags,
            use_proxy=use_proxy,
            volumes=volumes,
        )
        self._other_containers = [container() for container in self._other_container_types]

        self._http_container.environment |= {
            "INCLUDE_POSTGRES": "true" if PostgresContainer in self._other_container_types else "false",
            "INCLUDE_CASSANDRA": "true" if CassandraContainer in self._other_container_types else "false",
            "INCLUDE_MONGO": "true" if MongoContainer in self._other_container_types else "false",
            "INCLUDE_KAFKA": "true" if KafkaContainer in self._other_container_types else "false",
            "INCLUDE_RABBITMQ": "true" if RabbitMqContainer in self._other_container_types else "false",
            "INCLUDE_MYSQL": "true" if MySqlContainer in self._other_container_types else "false",
            "INCLUDE_SQLSERVER": "true" if MsSqlServerContainer in self._other_container_types else "false",
        }

    @property
    def http_container(self) -> WeblogContainer:
        return self._http_container

    @property
    def library_container(self) -> WeblogContainer:
        return self._http_container

    @property
    def library_name(self) -> str:
        return self._http_container.image.labels["system-tests-library"]

    @property
    def weblog_variant(self) -> str:
        return self._http_container.weblog_variant

    def get_containers(self) -> tuple[TestedContainer, ...]:
        return (self._http_container, *self._other_containers)

    def get_image_list(self, library: str, weblog_variant: str) -> list[str]:
        containers: list[TestedContainer] = [
            WeblogContainer(
                environment=self._environment,
                tracer_sampling_rate=self._tracer_sampling_rate,
                appsec_enabled=self._appsec_enabled,
                iast_enabled=self._iast_enabled,
                runtime_metrics_enabled=self._runtime_metrics_enabled,
                additional_trace_header_tags=self._additional_trace_header_tags,
                use_proxy=self._use_proxy,
                volumes=self._volumes,
            )
        ]
        containers.extend(container() for container in self._other_container_types)
        return [image for container in containers for image in container.get_image_list(library, weblog_variant)]

    def configure(self, config: pytest.Config, host_log_folder: str) -> None:  # noqa: ARG002
        self._http_container.depends_on.extend(self._other_containers)

        if config.option.force_dd_trace_debug:
            self._http_container.environment["DD_TRACE_DEBUG"] = "true"

        if config.option.force_dd_iast_debug:
            self._http_container.environment["_DD_IAST_DEBUG"] = "true"
            self._http_container.environment["DD_IAST_DEBUG_ENABLED"] = "true"

    def stop(self) -> None:
        self._http_container.flush()
        self._http_container.stop()


class GoProxiesEndToEndInfra(EndToEndInfra):
    def __init__(
        self,
        weblog_variant: str,
        *,
        environment: dict[str, str | None] | None = None,
        tracer_sampling_rate: float | None = None,
        appsec_enabled: bool = True,
        runtime_metrics_enabled: bool = False,
        additional_trace_header_tags: tuple[str, ...] = (),
        volumes: dict | None = None,
        other_containers: tuple[type[TestedContainer], ...] = (),
    ) -> None:
        self._weblog_variant = weblog_variant
        self._environment = dict(environment) if environment else {}
        self._volumes = volumes
        self._other_container_types = other_containers
        self._library_container: ExternalProcessingContainer | StreamProcessingOffloadContainer
        self._http_container: EnvoyContainer | HAProxyContainer

        if tracer_sampling_rate is not None and "DD_TRACE_SAMPLE_RATE" not in self._environment:
            self._environment["DD_TRACE_SAMPLE_RATE"] = str(tracer_sampling_rate)
            self._environment["DD_TRACE_SAMPLING_RULES"] = json.dumps([{"sample_rate": tracer_sampling_rate}])

        if not appsec_enabled and "DD_APPSEC_ENABLED" not in self._environment:
            self._environment["DD_APPSEC_ENABLED"] = "false"

        if runtime_metrics_enabled and "DD_RUNTIME_METRICS_ENABLED" not in self._environment:
            self._environment["DD_RUNTIME_METRICS_ENABLED"] = "true"

        if additional_trace_header_tags and "DD_TRACE_HEADER_TAGS" not in self._environment:
            self._environment["DD_TRACE_HEADER_TAGS"] = ",".join(additional_trace_header_tags)

        if weblog_variant == "envoy":
            self._library_container = ExternalProcessingContainer(env=self._environment, volumes=self._volumes)
            self._http_container = EnvoyContainer()
        else:
            self._library_container = StreamProcessingOffloadContainer(env=self._environment, volumes=self._volumes)
            self._http_container = HAProxyContainer()

        self._dummy_server = DummyServerContainer()
        self._other_containers = [container() for container in self._other_container_types]

    @property
    def http_container(self) -> EnvoyContainer | HAProxyContainer:
        return self._http_container

    @property
    def library_container(self) -> ExternalProcessingContainer | StreamProcessingOffloadContainer:
        return self._library_container

    @property
    def library_name(self) -> str:
        return PROXY_WEBLOGS[self._weblog_variant]

    @property
    def weblog_variant(self) -> str:
        return self._weblog_variant

    @property
    def appsec_rules_file(self) -> str | None:
        return self._environment.get("DD_APPSEC_RULES")

    def get_containers(self) -> tuple[TestedContainer, ...]:
        return (self._library_container, self._http_container, self._dummy_server, *self._other_containers)

    def get_image_list(self, library: str, weblog_variant: str) -> list[str]:
        infra = GoProxiesEndToEndInfra(
            weblog_variant,
            environment=self._environment,
            additional_trace_header_tags=(),
            volumes=self._volumes,
            other_containers=self._other_container_types,
        )
        return [
            image for container in infra.get_containers() for image in container.get_image_list(library, weblog_variant)
        ]

    def configure(self, config: pytest.Config, host_log_folder: str) -> None:  # noqa: ARG002
        self._http_container.depends_on.extend((self._library_container, self._dummy_server))

        if config.option.force_dd_trace_debug:
            self._library_container.environment["DD_TRACE_DEBUG"] = "true"

    def stop(self) -> None:
        self._dummy_server.stop()
        self._http_container.stop()
        self._library_container.stop()


class EndToEndWeblogInfra(EndToEndInfra):
    def __init__(
        self,
        *,
        environment: dict[str, str | None] | None = None,
        tracer_sampling_rate: float | None = None,
        appsec_enabled: bool = True,
        iast_enabled: bool = True,
        runtime_metrics_enabled: bool = False,
        additional_trace_header_tags: tuple[str, ...] = (),
        use_proxy: bool = True,
        volumes: dict | None = None,
        other_containers: tuple[type[TestedContainer], ...] = (),
    ) -> None:
        self._environment = environment
        self._tracer_sampling_rate = tracer_sampling_rate
        self._appsec_enabled = appsec_enabled
        self._iast_enabled = iast_enabled
        self._runtime_metrics_enabled = runtime_metrics_enabled
        self._additional_trace_header_tags = additional_trace_header_tags
        self._use_proxy = use_proxy
        self._volumes = volumes
        self._other_containers = other_containers
        self._infra: EndToEndInfra = self._build_library_infra()

    @property
    def http_container(self) -> EndToEndHttpContainer:
        return self._infra.http_container

    @property
    def library_container(self) -> EndToEndLibraryContainer:
        return self._infra.library_container

    @property
    def library_name(self) -> str:
        return self._infra.library_name

    @property
    def library(self) -> ComponentVersion:
        return self._infra.library

    @property
    def weblog_variant(self) -> str:
        return self._infra.weblog_variant

    @property
    def tracer_sampling_rate(self) -> float | None:
        return self._infra.tracer_sampling_rate

    @property
    def appsec_rules_file(self) -> str | None:
        return self._infra.appsec_rules_file

    @property
    def uds_socket(self) -> str | None:
        return self._infra.uds_socket

    @property
    def uds_mode(self) -> bool:
        return self._infra.uds_mode

    @property
    def telemetry_heartbeat_interval(self) -> int | float:
        return self._infra.telemetry_heartbeat_interval

    def get_containers(self) -> tuple[TestedContainer, ...]:
        return self._infra.get_containers()

    def get_image_list(self, library: str, weblog_variant: str) -> list[str]:
        if weblog_variant in PROXY_WEBLOGS:
            return self._build_proxy_infra(weblog_variant).get_image_list(library, weblog_variant)
        return self._build_library_infra().get_image_list(library, weblog_variant)

    def configure(self, config: pytest.Config, host_log_folder: str) -> None:
        weblog_variant = config.option.weblog

        if weblog_variant is None and config.option.replay:
            weblog_variant = self._discover_weblog_variant_from_logs(host_log_folder)

        if weblog_variant is None and config.option.replay:
            pytest.exit(
                "Unable to determine weblog variant in replay mode. Pass --weblog or provide feature_parity.json",
                1,
            )

        if weblog_variant in PROXY_WEBLOGS:
            if not isinstance(self._infra, GoProxiesEndToEndInfra) or self._infra.weblog_variant != weblog_variant:
                self._infra = self._build_proxy_infra(weblog_variant)
        elif not isinstance(self._infra, LibraryEndToEndInfra):
            self._infra = self._build_library_infra()

        self._infra.configure(config, host_log_folder)

    def stop(self) -> None:
        self._infra.stop()

    def set_weblog_domain_for_ipv6(self, network: Network) -> None:
        self._infra.set_weblog_domain_for_ipv6(network)

    def _build_library_infra(self) -> LibraryEndToEndInfra:
        return LibraryEndToEndInfra(
            environment=self._environment,
            tracer_sampling_rate=self._tracer_sampling_rate,
            appsec_enabled=self._appsec_enabled,
            iast_enabled=self._iast_enabled,
            runtime_metrics_enabled=self._runtime_metrics_enabled,
            additional_trace_header_tags=self._additional_trace_header_tags,
            use_proxy=self._use_proxy,
            volumes=self._volumes,
            other_containers=self._other_containers,
        )

    def _build_proxy_infra(self, weblog_variant: str) -> GoProxiesEndToEndInfra:
        return GoProxiesEndToEndInfra(
            weblog_variant,
            environment=self._environment,
            tracer_sampling_rate=self._tracer_sampling_rate,
            appsec_enabled=self._appsec_enabled,
            runtime_metrics_enabled=self._runtime_metrics_enabled,
            additional_trace_header_tags=self._additional_trace_header_tags,
            volumes=self._volumes,
            other_containers=self._other_containers,
        )

    @staticmethod
    def _discover_weblog_variant_from_logs(host_log_folder: str) -> str | None:
        host_project_dir = os.environ.get("SYSTEM_TESTS_HOST_PROJECT_DIR", str(Path.cwd()))
        feature_parity_path = Path(host_project_dir) / host_log_folder / "feature_parity.json"

        try:
            with feature_parity_path.open(encoding="utf-8") as file:
                feature_parity = json.load(file)
        except Exception:
            return None

        variant = feature_parity.get("variant")
        return variant if isinstance(variant, str) else None
