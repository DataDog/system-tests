from abc import ABC, abstractmethod
from typing import Literal, get_args

import pytest

from utils._context.containers import (
    WeblogContainer,
    TestedContainer,
    KafkaContainer,
    RabbitMqContainer,
    PostgresContainer,
    CassandraContainer,
    MongoContainer,
    MySqlContainer,
    MsSqlServerContainer,
    DummyServerContainer,
    EnvoyContainer,
    HAProxyContainer,
    ExternalProcessingContainer,
    StreamProcessingOffloadContainer,
    GoProcessorContainer,
)

GoProxyWeblogs = Literal["envoy", "haproxy"]


class WeblogInfra(ABC):
    """Infrastructure shipping the HTTP app (aka weblog) instrumented by a library."""

    @abstractmethod
    def configure(self, config: pytest.Config) -> None:
        """Perform any configuration. Executed only if the weblog will be used"""

    @abstractmethod
    def stop(self) -> None:
        """Stop the tested infra"""


class EndToEndWeblogInfra(WeblogInfra):
    """Infrastructure shipping the HTTP app (aka weblog) instrumented by a library.
    This class is meant to work with EndToEndScenario
    """

    _go_proxy_weblog: GoProxyWeblogs | None = None
    _processor_container: GoProcessorContainer
    """the Datadog library under test, running as an Envoy external processor
    or an HAProxy SPOA agent. It intercepts HTTP traffic from the proxy runtime to apply
    AppSec rules and emit traces. This is the "weblog" from the library's point of view."""

    _proxy_runtime_container: EnvoyContainer | HAProxyContainer
    """the reverse proxy (Envoy or HAProxy) that sits in front of the
    dummy HTTP server and forwards requests through the processor. It is the actual HTTP
    entry point for test requests, exposing the weblog port to the test suite."""

    _dummy_server_container: DummyServerContainer
    """a minimal HTTP server that the proxy runtime proxies to.
    It has no Datadog instrumentation and simply returns responses.
    """

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
        self._environment = environment or {}
        self._volumes = volumes or {}

        self.http_container = WeblogContainer(
            environment=environment,
            tracer_sampling_rate=tracer_sampling_rate,
            appsec_enabled=appsec_enabled,
            iast_enabled=iast_enabled,
            runtime_metrics_enabled=runtime_metrics_enabled,
            additional_trace_header_tags=additional_trace_header_tags,
            use_proxy=use_proxy,
            volumes=volumes,
        )
        self._other_containers = [container() for container in other_containers]

        self.http_container.environment |= {
            "INCLUDE_POSTGRES": "true" if PostgresContainer in other_containers else "false",
            "INCLUDE_CASSANDRA": "true" if CassandraContainer in other_containers else "false",
            "INCLUDE_MONGO": "true" if MongoContainer in other_containers else "false",
            "INCLUDE_KAFKA": "true" if KafkaContainer in other_containers else "false",
            "INCLUDE_RABBITMQ": "true" if RabbitMqContainer in other_containers else "false",
            "INCLUDE_MYSQL": "true" if MySqlContainer in other_containers else "false",
            "INCLUDE_SQLSERVER": "true" if MsSqlServerContainer in other_containers else "false",
        }

        self.appsec_rules_file: str | None = self._environment.get("DD_APPSEC_RULES", None)

    def configure(self, config: pytest.Config):
        self._configure_proxy_weblog(config.option.weblog)

        self.library_container.depends_on.extend(self._other_containers)

        if config.option.force_dd_trace_debug:
            self.library_container.environment["DD_TRACE_DEBUG"] = "true"

        if config.option.force_dd_iast_debug:
            self.library_container.environment["_DD_IAST_DEBUG"] = "true"  # probably not used anymore ?
            self.library_container.environment["DD_IAST_DEBUG_ENABLED"] = "true"

    def _configure_proxy_weblog(self, weblog: str) -> None:
        """Configure Proxy weblog if weblog argument correspond tyo any value of GoProxyWeblogs"""

        if weblog not in get_args(GoProxyWeblogs):
            return

        self._go_proxy_weblog = weblog

        if self._go_proxy_weblog == "envoy":
            self._processor_container = ExternalProcessingContainer()
            self._proxy_runtime_container = EnvoyContainer()
        elif self._go_proxy_weblog == "haproxy":
            self._processor_container = StreamProcessingOffloadContainer()
            self._proxy_runtime_container = HAProxyContainer()

        self._processor_container.environment |= self._environment
        self._processor_container.volumes |= self._volumes

        self._dummy_server_container = DummyServerContainer()

        self._proxy_runtime_container.depends_on = [self._processor_container, self._dummy_server_container]

    def set_weblog_dependencies(
        self, agent_container: TestedContainer, proxy_container: TestedContainer | None
    ) -> None:
        """Wire container start-order dependencies for all weblog containers.

        Handles both the standard weblog topology and the go-proxies one transparently.
        """
        self.library_container.depends_on.append(agent_container)
        if proxy_container is not None:
            self.library_container.depends_on.append(proxy_container)

    @property
    def _is_proxy_weblog(self) -> bool:
        return self._go_proxy_weblog is not None

    @property
    def weblog_variant(self) -> str:
        if self._go_proxy_weblog is not None:
            return self._go_proxy_weblog

        return self.http_container.weblog_variant

    @property
    def library(self):
        if self._is_proxy_weblog:
            return self._processor_container.library

        return self.http_container.library

    @property
    def library_container(self) -> TestedContainer:
        """Container whose library version and metadata represent the tested library.

        In go-proxies mode this is the security processor, not the HTTP entry point.
        """
        if self._is_proxy_weblog:
            return self._processor_container
        return self.http_container

    def get_image_list(self, library: str, weblog: str) -> list[str]:
        self._configure_proxy_weblog(weblog)

        return [
            image_name
            for container in self.get_containers()
            for image_name in container.get_image_list(library, weblog)
        ]

    def get_containers(self) -> tuple[TestedContainer, ...]:
        if self._is_proxy_weblog:
            return (
                self._processor_container,
                self._proxy_runtime_container,
                self._dummy_server_container,
                *self._other_containers,
            )
        return (self.http_container, *self._other_containers)

    def stop(self) -> None:
        if self._is_proxy_weblog:
            if self._proxy_runtime_container:
                self._proxy_runtime_container.stop()
            if self._processor_container:
                self._processor_container.stop()
            if self._dummy_server_container:
                self._dummy_server_container.stop()
        else:
            self.http_container.flush()
            self.http_container.stop()

    @property
    def library_name(self) -> str:
        if self._is_proxy_weblog:
            return "golang"

        return self.library_container.image.labels["system-tests-library"]

    @property
    def uds_socket(self) -> str | None:
        if self._is_proxy_weblog:
            return None

        return self.http_container.uds_socket

    @property
    def uds_mode(self) -> bool:
        return self.uds_socket is not None
