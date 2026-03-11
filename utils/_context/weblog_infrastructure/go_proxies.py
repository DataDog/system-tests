import json

import pytest

from utils._context.containers import (
    DummyServerContainer,
    EnvoyContainer,
    ExternalProcessingContainer,
    HAProxyContainer,
    StreamProcessingOffloadContainer,
    TestedContainer,
)

from .base import EndToEndInfra

PROXY_WEBLOGS: dict[str, str] = {
    "envoy": "envoy",
    "haproxy-spoa": "haproxy",
}


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
