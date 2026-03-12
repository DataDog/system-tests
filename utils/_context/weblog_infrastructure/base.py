from abc import ABC, abstractmethod
import sys

from docker.models.networks import Network
import pytest

from utils._context.component_version import ComponentVersion
from utils._context.containers import (
    EnvoyContainer,
    ExternalProcessingContainer,
    HAProxyContainer,
    StreamProcessingOffloadContainer,
    TestedContainer,
    WeblogContainer,
)
from utils._logger import logger
from utils._weblog import weblog

EndToEndHttpContainer = WeblogContainer | EnvoyContainer | HAProxyContainer
EndToEndLibraryContainer = WeblogContainer | ExternalProcessingContainer | StreamProcessingOffloadContainer


class WeblogInfra(ABC):
    @abstractmethod
    def configure(self, config: pytest.Config, host_log_folder: str) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

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
