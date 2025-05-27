from pathlib import Path

import pytest

from utils._context.component_version import ComponentVersion, Version

from utils.k8s_lib_injection.k8s_cluster_provider import K8sProviderFactory
from utils._context.containers import (
    _get_client as get_docker_client,
)

from utils._logger import logger
from utils.injector_dev.injector_client import InjectorDevClient
from .core import Scenario, scenario_groups, ScenarioGroup

# Default scenario groups for K8sInjectorDevScenario
DEFAULT_SCENARIO_GROUPS: list[ScenarioGroup] = [scenario_groups.all, scenario_groups.lib_injection]


class K8sInjectorDevScenario(Scenario):
    """Scenario that tests kubernetes lib injection using the injector-dev tool"""

    def __init__(
        self,
        name: str,
        doc: str,
        scenario_provision: str,
        scenario_groups: list[ScenarioGroup] | None = None,
    ) -> None:
        if scenario_groups is None:
            scenario_groups = DEFAULT_SCENARIO_GROUPS
        super().__init__(name, doc=doc, github_workflow="libinjection", scenario_groups=scenario_groups)
        self.scenario_provision = scenario_provision

    def configure(self, config: pytest.Config):
        # These are the tested components: dd_cluser_agent_version, weblog image, library_init_version, injector version
        self.k8s_weblog = config.option.k8s_weblog
        self.k8s_weblog_img = config.option.k8s_weblog_img
        # By default we are going to use kind cluster provider
        self.k8s_provider_name = config.option.k8s_provider if config.option.k8s_provider else "kind"

        # Get Lib init version
        self._library = ComponentVersion(
            config.option.k8s_library, extract_library_version(config.option.k8s_lib_init_img)
        )
        self.k8s_lib_init_img = config.option.k8s_lib_init_img
        self.components["library"] = self._library.version

        # Cluster agent version
        if config.option.k8s_cluster_version is not None and config.option.k8s_cluster_img is not None:
            raise ValueError("You mustn't set both k8s_cluster_version and k8s_cluster_img")
        if config.option.k8s_cluster_version is None and config.option.k8s_cluster_img is None:
            raise ValueError("You must set either k8s_cluster_version or k8s_cluster_img")
        if config.option.k8s_cluster_version is not None:
            logger.stdout("WARNING: The k8s_cluster_version is going to be deprecated, use k8s_cluster_img instead")
            self.k8s_cluster_img = None
            self.k8s_cluster_version = config.option.k8s_cluster_version
            self.components["cluster_agent"] = self.k8s_cluster_version
        else:
            self.k8s_cluster_img = config.option.k8s_cluster_img
            self.k8s_cluster_version = extract_cluster_agent_version(self.k8s_cluster_img)
            self.components["cluster_agent"] = self.k8s_cluster_version

        # Injector image version
        self.k8s_injector_img = (
            config.option.k8s_injector_img if config.option.k8s_injector_img else "gcr.io/datadoghq/apm-inject:latest"
        )
        self._datadog_apm_inject_version = f"v{extract_injector_version(self.k8s_injector_img)}"
        self.components["datadog-apm-inject"] = self._datadog_apm_inject_version

        # Configure the K8s cluster provider
        self.k8s_cluster_provider = K8sProviderFactory().get_provider(self.k8s_provider_name)
        self.k8s_cluster_provider.configure()
        # self.print_context()

        # is it on sleep mode?
        self._sleep_mode = config.option.sleep

        # Check if the scenario_provision file exists
        scenario_provision_path = Path("utils") / "build" / "injector-dev" / self.scenario_provision
        if not scenario_provision_path.exists():
            raise FileNotFoundError(
                f"Scenario provision file not found at {scenario_provision_path}. Please build it first."
            )

        # Initialize the injector client
        self.injector_client = InjectorDevClient()

    def print_context(self):
        logger.stdout(".:: K8s Lib injection test components ::.")
        logger.stdout(f"Weblog: {self.k8s_weblog}")
        logger.stdout(f"Weblog image: {self.k8s_weblog_img}")
        logger.stdout(f"Library: {self._library}")
        logger.stdout(f"Lib init image: {self.k8s_lib_init_img}")
        logger.stdout(f"Cluster agent version: {self.k8s_cluster_version}")
        logger.stdout(f"Cluster agent image: {self.k8s_cluster_img}")
        logger.stdout(f"Injector version: {self._datadog_apm_inject_version}")
        logger.stdout(f"Injector image: {self.k8s_injector_img}")

    def get_warmups(self):
        warmups = super().get_warmups()
        warmups.append(self.print_context)
        warmups.append(lambda: logger.terminal.write_sep("=", "Starting injector-dev", bold=True))
        warmups.append(self._start_injector_dev)
        warmups.append(lambda: logger.terminal.write_sep("=", "Applying injector-dev scenario", bold=True))
        warmups.append(self._apply_scenario_injector_dev)

        return warmups

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int):  # noqa: ARG002
        self.close_targets()

    def close_targets(self):
        logger.info("Destroying cluster")
        self._stop_injector_dev()

    def _start_injector_dev(self):
        """Start the injector-dev tool"""
        self.injector_client.start(debug=True)

    def _stop_injector_dev(self):
        """Stop the injector-dev tool"""
        self.injector_client.stop(clean_k8s=True)

    def _apply_scenario_injector_dev(self):
        """Applies the scenario in yaml format to the injector-dev tool."""
        scenario_path = Path("utils") / "build" / "injector-dev" / self.scenario_provision
        self.injector_client.apply_scenario(scenario_path, wait=True, debug=True)

    @property
    def library(self):
        return self._library

    @property
    def weblog_variant(self):
        return self.k8s_weblog

    @property
    def k8s_cluster_agent_version(self):
        return Version(self.k8s_cluster_version)

    @property
    def dd_apm_inject_version(self):
        return self._datadog_apm_inject_version


def extract_library_version(library_init_image: str) -> str:
    """Pull the library init image and extract the version of the library"""
    logger.info("Get lib init tracer version")
    try:
        lib_init_docker_image = get_docker_client().images.pull(library_init_image)
        result = get_docker_client().containers.run(
            image=lib_init_docker_image, command="cat /datadog-init/package/version", remove=True
        )
        version = result.decode("utf-8")
        logger.info(f"Library version: {version}")
        return version
    except Exception as e:
        logger.error(f"The library init image failed to pull is: {library_init_image}")
        raise ValueError(f"Failed to pull and extract library version: {e}") from e


def extract_injector_version(injector_image: str) -> str:
    """Pull the injector image and extract the version of the injector"""
    logger.info(f"Get injector version from image: {injector_image}")
    try:
        injector_docker_image = get_docker_client().images.pull(injector_image)
        # TODO review this. The version is a folder name under /opt/datadog-packages/datadog-apm-inject/
        result = get_docker_client().containers.run(
            image=injector_docker_image, command="ls /opt/datadog-packages/datadog-apm-inject/", remove=True
        )
        version = result.decode("utf-8").split("\n")[0]

        logger.info(f"Injector version: {version}")
        return version
    except Exception as e:
        logger.error(f"The failed injector image failed to pull is: {injector_image}")
        raise ValueError(f"Failed to pull and extract injector version: {e}") from e


def extract_cluster_agent_version(cluster_image: str) -> str:
    """Pull the datadog cluster image  and extract the version from labels"""
    logger.info("Get cluster agent version")
    try:
        cluster_docker_image = get_docker_client().images.pull(cluster_image)
        version = cluster_docker_image.labels["org.opencontainers.image.version"]
        logger.info(f"Cluster agent version: {version}")
        return version
    except Exception as e:
        logger.error(f"The cluster agent images tried to pull is: {cluster_image}")
        raise ValueError(f"Failed to pull and extract cluster agent version: {e}") from e
