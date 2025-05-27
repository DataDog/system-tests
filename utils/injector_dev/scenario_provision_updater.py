import shutil
from pathlib import Path

import yaml

from utils._logger import logger
from utils.k8s.k8s_component_image import K8sComponentImage


class ScenarioProvisionUpdater:
    """A class for updating YAML scenario files with K8s component image information.

    This class reads a YAML scenario file from the utils/build/injector-dev/ directory,
    updates the component image information in the 'versions' section, and writes
    the updated file to the scenario logs directory.

    Attributes:
        source_dir (Path): Path to the directory containing source YAML files
        logs_dir (Path): Path to the directory where updated YAML files will be saved

    """

    def __init__(self, logs_dir: Path | None = None):
        """Initialize a ScenarioProvisionUpdater instance.

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
    ) -> Path:
        """Update a scenario YAML file with K8s component image information.

        Args:
            scenario_filename: Name of the scenario YAML file
            cluster_agent_image: K8sComponentImage object for the cluster agent
            injector_image: K8sComponentImage object for the injector

        Returns:
            Path to the updated YAML file

        Raises:
            FileNotFoundError: If the scenario file doesn't exist
            ValueError: If the YAML file doesn't have the expected structure

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
            "repository": cluster_agent_image.main_url,
            "tag": cluster_agent_image.tag,
        }

        # Update the injector version to use the repository/tag format
        scenario_yaml["helm"]["versions"]["injector"] = {
            "repository": injector_image.main_url,
            "tag": injector_image.tag,
        }

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
