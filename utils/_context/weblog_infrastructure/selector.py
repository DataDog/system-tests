import json
import os
from pathlib import Path

from docker.models.networks import Network
import pytest

from utils._context.component_version import ComponentVersion
from utils._context.containers import TestedContainer

from .base import EndToEndHttpContainer, EndToEndInfra, EndToEndLibraryContainer
from .go_proxies import GoProxiesEndToEndInfra, PROXY_WEBLOGS
from .library_end_to_end import LibraryEndToEndInfra


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
            replay_variant = self._discover_weblog_variant_from_logs(host_log_folder)
            if replay_variant in PROXY_WEBLOGS:
                weblog_variant = replay_variant

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
        except (OSError, json.JSONDecodeError):
            return None

        variant = feature_parity.get("variant")
        return variant if isinstance(variant, str) else None
