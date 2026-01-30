from abc import ABC, abstractmethod

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
)


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

    def get_containers(self) -> tuple[TestedContainer, ...]:
        return (self.http_container, *self._other_containers)

    def configure(self, config: pytest.Config):
        self.http_container.depends_on.extend(self._other_containers)

        if config.option.force_dd_trace_debug:
            self.http_container.environment["DD_TRACE_DEBUG"] = "true"

        if config.option.force_dd_iast_debug:
            self.http_container.environment["_DD_IAST_DEBUG"] = "true"  # probably not used anymore ?
            self.http_container.environment["DD_IAST_DEBUG_ENABLED"] = "true"

    def stop(self) -> None:
        for container in self._other_containers:
            container.stop()

        if self.library_name in (
            "nodejs",
            "ruby",
        ):
            self.http_container.flush()

        self.http_container.stop()

    @property
    def library_name(self) -> str:
        return self.http_container.image.labels["system-tests-library"]
