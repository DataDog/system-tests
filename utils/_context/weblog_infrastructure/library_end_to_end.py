import pytest

from utils._context.containers import (
    CassandraContainer,
    KafkaContainer,
    MongoContainer,
    MsSqlServerContainer,
    MySqlContainer,
    PostgresContainer,
    RabbitMqContainer,
    TestedContainer,
    WeblogContainer,
)

from .base import EndToEndInfra


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
