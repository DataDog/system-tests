import shutil
from pathlib import Path

import yaml

from utils._logger import logger
from utils.k8s.k8s_component_image import K8sComponentImage


class ScenarioProvisionParser:
    """A class for updating YAML scenario files with K8s component image information.

    This class reads a YAML scenario file from the utils/build/injector-dev/ directory,
    updates the component image information in the 'versions' section, and writes
    the updated file to the scenario logs directory.

    Attributes:
        source_dir (Path): Path to the directory containing source YAML files
        logs_dir (Path): Path to the directory where updated YAML files will be saved

    """

    def __init__(self, logs_dir: Path | None = None):
        """Initialize a ScenarioProvisionParser instance.

        Args:
            logs_dir: Optional path to the logs directory. If not provided,
                     the current working directory will be used.

        """
        self.source_dir = Path("utils/build/injector-dev")
        self.logs_dir = logs_dir if logs_dir else Path.cwd()

        # Ensure the source directory exists
        if not self.source_dir.exists():
            raise FileNotFoundError(f"Source directory not found: {self.source_dir}")

        # Ensure the logs directory exists
        if not self.logs_dir.exists():
            self.logs_dir.mkdir(parents=True, exist_ok=True)

    def update_scenario(
        self,
        scenario_filename: str,
        cluster_agent_image: K8sComponentImage,
        injector_image: K8sComponentImage,
        weblog_image: K8sComponentImage | None = None,
        k8s_lib_init_img: K8sComponentImage | None = None,
        language: str | None = None,
        container_registry: str | None = None,
    ) -> Path:
        """Update a scenario YAML file with K8s component image information.

        Args:
            scenario_filename: Name of the scenario YAML file
            cluster_agent_image: K8sComponentImage object for the cluster agent
            injector_image: K8sComponentImage object for the injector
            weblog_image: Optional K8sComponentImage object for the weblog/application images
            k8s_lib_init_img: Optional K8sComponentImage object for the library init image
            language: Optional language to update in ddTraceVersions (e.g., 'python', 'java')
            container_registry: Optional container registry URL to set in clusterAgent.admissionController

        Returns:
            Path to the updated YAML file

        Raises:
            FileNotFoundError: If the scenario file doesn't exist
            TypeError: If the YAML file doesn't have the expected structure

        """
        source_path = self.source_dir / scenario_filename
        dest_path = self.logs_dir / scenario_filename

        # Check if the source file exists
        if not source_path.exists():
            raise FileNotFoundError(f"Scenario file not found: {source_path}")

        # Load the YAML file
        try:
            with open(source_path, "r") as f:
                scenario_yaml = yaml.safe_load(f)
        except Exception as e:
            raise ValueError(f"Failed to load YAML file {source_path}: {e}") from e

        # Check if the YAML file has the expected structure
        if not isinstance(scenario_yaml, dict):
            raise TypeError(f"Invalid YAML structure in {source_path}, expected dictionary")

        # Make sure 'helm' key exists
        if "helm" not in scenario_yaml:
            scenario_yaml["helm"] = {}

        # Make sure 'versions' key exists under 'helm'
        if "versions" not in scenario_yaml["helm"]:
            scenario_yaml["helm"]["versions"] = {}

        # Update the cluster_agent version
        scenario_yaml["helm"]["versions"]["cluster_agent"] = {
            # "repository": cluster_agent_image.main_url,
            "tag": cluster_agent_image.tag,
        }

        # Update the injector version to use the repository/tag format
        scenario_yaml["helm"]["versions"]["injector"] = {
            # "repository": injector_image.main_url,
            "tag": injector_image.tag,
        }

        # Update app images if weblog_image is provided
        if weblog_image and "apps" in scenario_yaml.get("helm", {}):
            for app in scenario_yaml["helm"]["apps"]:
                # Ensure the values structure exists
                if "values" not in app:
                    app["values"] = {}

                # Ensure the image structure exists
                if "image" not in app["values"]:
                    app["values"]["image"] = {}

                # Update image repository and tag for all apps
                app["values"]["image"]["repository"] = weblog_image.main_url
                app["values"]["image"]["tag"] = weblog_image.tag
                logger.info(f"Updated image for app {app.get('name', 'unknown')}")

        # Update ddTraceVersions nodes if language and k8s_lib_init_img are provided
        if language and k8s_lib_init_img and "config" in scenario_yaml.get("helm", {}):
            # Check if the datadog.apm.instrumentation.targets structure exists
            datadog_config = scenario_yaml["helm"]["config"].get("datadog", {})
            apm_config = datadog_config.get("apm", {})
            instrumentation_config = apm_config.get("instrumentation", {})
            targets = instrumentation_config.get("targets", [])

            if targets:
                logger.info(f"Found {len(targets)} instrumentation targets")

                # Update ddTraceVersions for each target
                for target in targets:
                    # Check if ddTraceVersions exists, if not create it
                    if "ddTraceVersions" not in target:
                        target["ddTraceVersions"] = {}

                    # Update the specific language version
                    target["ddTraceVersions"][language] = k8s_lib_init_img.tag
                    logger.info(
                        f"Updated ddTraceVersions.{language} = {k8s_lib_init_img.tag} "
                        f"for target {target.get('name', 'unknown')}"
                    )
            else:
                logger.warning("No instrumentation targets found in the scenario YAML")

        # Update containerRegistry if container_registry is provided
        if container_registry:
            # Ensure the config structure exists
            if "config" not in scenario_yaml["helm"]:
                scenario_yaml["helm"]["config"] = {}

            # Ensure the clusterAgent structure exists
            if "clusterAgent" not in scenario_yaml["helm"]["config"]:
                scenario_yaml["helm"]["config"]["clusterAgent"] = {}

            # Ensure the admissionController structure exists
            if "admissionController" not in scenario_yaml["helm"]["config"]["clusterAgent"]:
                scenario_yaml["helm"]["config"]["clusterAgent"]["admissionController"] = {}

            # Set the containerRegistry value
            scenario_yaml["helm"]["config"]["clusterAgent"]["admissionController"]["containerRegistry"] = (
                container_registry
            )
            logger.info(f"Updated clusterAgent.admissionController.containerRegistry = {container_registry}")

            # Ensure the image structure exists for clusterAgent
            if "image" not in scenario_yaml["helm"]["config"]["clusterAgent"]:
                scenario_yaml["helm"]["config"]["clusterAgent"]["image"] = {}

            # Set the registry value for clusterAgent image
            scenario_yaml["helm"]["config"]["clusterAgent"]["image"]["repository"] = (
                container_registry + "/cluster-agent"
            )
            logger.info(f"Updated clusterAgent.image.registry = {container_registry}")

            # Add pullSecrets to clusterAgent image
            scenario_yaml["helm"]["config"]["clusterAgent"]["image"]["pullSecrets"] = [
                {"name": "private-registry-secret"}
            ]
            logger.info("Added pullSecrets to clusterAgent.image")

            # Add imagePullSecrets to all apps when private registry is configured
            if "apps" in scenario_yaml.get("helm", {}):
                for app in scenario_yaml["helm"]["apps"]:
                    # Ensure the values structure exists
                    if "values" not in app:
                        app["values"] = {}

                    # Add imagePullSecrets to the app
                    app["values"]["imagePullSecrets"] = [{"name": "private-registry-secret"}]
                    logger.info(f"Added imagePullSecrets to app {app.get('name', 'unknown')}")
            else:
                logger.warning("No apps found in the scenario YAML to update imagePullSecrets")

        # Write the updated YAML to the destination file
        try:
            with open(dest_path, "w") as f:
                yaml.dump(scenario_yaml, f, default_flow_style=False)
            logger.info(f"Updated scenario file written to {dest_path}")
        except Exception as e:
            raise OSError(f"Failed to write updated YAML file {dest_path}: {e}") from e

        return dest_path

    def copy_scenario(self, scenario_filename: str) -> Path:
        """Copy a scenario YAML file without modifying it.

        Args:
            scenario_filename: Name of the scenario YAML file

        Returns:
            Path to the copied YAML file

        Raises:
            FileNotFoundError: If the scenario file doesn't exist

        """
        source_path = self.source_dir / scenario_filename
        dest_path = self.logs_dir / scenario_filename

        # Check if the source file exists
        if not source_path.exists():
            raise FileNotFoundError(f"Scenario file not found: {source_path}")

        # Copy the file
        try:
            shutil.copy2(source_path, dest_path)
            logger.info(f"Copied scenario file to {dest_path}")
        except Exception as e:
            raise OSError(f"Failed to copy YAML file {dest_path}: {e}") from e

        return dest_path

    def get_app_namespaces(self, scenario_filename: str) -> list[str]:
        """Parse the scenario provision YAML file and extract app namespaces."""
        # Construct the full path to the scenario provision file
        scenario_provision_path = self.source_dir / scenario_filename
        try:
            # Read and parse the YAML file
            with open(scenario_provision_path, "r") as file:
                yaml_content = yaml.safe_load(file)

            # Extract namespaces from helm.apps
            namespaces = set()
            if "helm" in yaml_content and "apps" in yaml_content["helm"]:
                for app in yaml_content["helm"]["apps"]:
                    if "namespace" in app:
                        namespaces.add(app["namespace"])

            return list(namespaces)

        except Exception as e:
            logger.error(f"Error parsing scenario provision file {scenario_filename}: {e!s}")
            raise
