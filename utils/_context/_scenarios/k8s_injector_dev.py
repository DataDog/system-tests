from pathlib import Path

import pytest

from utils._context.component_version import ComponentVersion, Version

from utils.k8s.k8s_component_image import (
    K8sComponentImage,
    extract_library_version,
    extract_injector_version,
    extract_cluster_agent_version,
)
from utils._logger import logger
from utils.injector_dev.injector_client import InjectorDevClient
from utils.injector_dev.scenario_provision_updater import ScenarioProvisionUpdater
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
        # provision template
        self.scenario_provision = scenario_provision
        # Used to store the path to the actual scenario provision file (with injected component images/log folder)
        self.current_scenario_provision: Path | None = None

    def configure(self, config: pytest.Config):
        # These are the tested components: dd_cluser_agent_version, weblog image, library_init_version, injector version
        self.k8s_weblog = config.option.k8s_weblog

        # Get component images: weblog, lib init, cluster agent, injector
        self.k8s_weblog_img = K8sComponentImage(config.option.k8s_weblog_img, lambda _: "weblog-version-1.0")

        self.k8s_lib_init_img = K8sComponentImage(config.option.k8s_lib_init_img, extract_library_version)

        self.k8s_cluster_img = K8sComponentImage(config.option.k8s_cluster_img, extract_cluster_agent_version)

        self.k8s_injector_img = K8sComponentImage(
            config.option.k8s_injector_img if config.option.k8s_injector_img else "gcr.io/datadoghq/apm-inject:latest",
            extract_injector_version,
        )

        # Get component versions: lib init, cluster agent, injector
        self._library = ComponentVersion(config.option.k8s_library, self.k8s_lib_init_img.version)
        self.components["library"] = self._library.version
        self.components["cluster_agent"] = self.k8s_cluster_img.version
        self._datadog_apm_inject_version = f"v{self.k8s_injector_img.version}"
        self.components["datadog-apm-inject"] = self._datadog_apm_inject_version

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
        logger.stdout(f"Weblog image: {self.k8s_weblog_img.registry_url}")
        logger.stdout(f"Library: {self._library}")
        logger.stdout(f"Lib init image: {self.k8s_lib_init_img.registry_url}")
        logger.stdout(f"Cluster agent version: {self.k8s_cluster_img.version}")
        logger.stdout(f"Cluster agent image: {self.k8s_cluster_img.registry_url}")
        logger.stdout(f"Injector version: {self._datadog_apm_inject_version}")
        logger.stdout(f"Injector image: {self.k8s_injector_img.registry_url}")

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
        # Create a ScenarioProvisionUpdater instance pointing to the logs directory
        logs_dir = Path(f"logs_{self.name}")
        updater = ScenarioProvisionUpdater(logs_dir=logs_dir)

        # Update the scenario file with the component images
        self.current_scenario_provision = updater.update_scenario(
            self.scenario_provision,
            self.k8s_cluster_img,
            self.k8s_injector_img,
            self.k8s_weblog_img,  # Include the weblog image
        )

        logger.info(f"Updated scenario file written to {self.current_scenario_provision}")

        # Apply the updated scenario
        if self.current_scenario_provision:
            self.injector_client.apply_scenario(self.current_scenario_provision, wait=True, debug=True)
        else:
            # Fallback to the original scenario file if update failed
            source_scenario_path = Path("utils") / "build" / "injector-dev" / self.scenario_provision
            logger.warning(f"Using original scenario file at {source_scenario_path}")
            self.injector_client.apply_scenario(source_scenario_path, wait=True, debug=True)

    @property
    def library(self):
        return self._library

    @property
    def weblog_variant(self):
        return self.k8s_weblog

    @property
    def k8s_cluster_agent_version(self):
        return Version(self.k8s_cluster_img.version)

    @property
    def dd_apm_inject_version(self):
        return self._datadog_apm_inject_version
