import json
import os
import random
import socket
import time
from docker.models.networks import Network
import pytest

from utils import interfaces
from utils._context.component_version import ComponentVersion, Version
from utils._context.containers import (
    create_network,
    DockerSSIContainer,
    APMTestAgentContainer,
    TestedContainer,
)
from utils.docker_ssi.image_builder import DockerSSIImageBuilder
from utils._logger import logger

from .core import Scenario, ScenarioGroup


class DockerSSIScenario(Scenario):
    """Scenario test the ssi installer on a docker environment and runs APM test agent"""

    _network: Network = None

    def __init__(
        self,
        name: str,
        doc: str,
        extra_env_vars: dict | None = None,
        scenario_groups: list[ScenarioGroup] | None = None,
        *,
        appsec_enabled: bool | None = None,
    ) -> None:
        super().__init__(name, doc=doc, github_workflow="dockerssi", scenario_groups=scenario_groups)

        self._appsec_enabled = appsec_enabled
        self.agent_port = _get_free_port()
        self.agent_host = "localhost"
        self._weblog_injection = DockerSSIContainer(extra_env_vars=extra_env_vars)
        self._agent_container = APMTestAgentContainer(agent_port=self.agent_port)

        self._required_containers: list[TestedContainer] = []
        self._required_containers.append(self._agent_container)
        self._required_containers.append(self._weblog_injection)
        self.weblog_url = "http://localhost:18080"
        # scenario configuration that is going to be reported in the final report
        self._configuration = {"app_type": "docker_ssi"}

    def configure(self, config: pytest.Config):
        assert config.option.ssi_library, "library must be set: java,python,nodejs,dotnet,ruby,php,rust"

        self._base_weblog = config.option.ssi_weblog
        self._library = config.option.ssi_library
        self._base_image = config.option.ssi_base_image
        self._arch = config.option.ssi_arch

        self._env = "prod" if config.option.ssi_env is None or config.option.ssi_env == "prod" else "dev"
        self.configuration["env"] = self._env
        self._custom_library_version = config.option.ssi_library_version
        self._custom_injector_version = config.option.ssi_injector_version

        # The runtime that we want to install on the base image. it could be empty if we don't need to install a runtime
        self._installable_runtime = (
            config.option.ssi_installable_runtime
            if config.option.ssi_installable_runtime and config.option.ssi_installable_runtime != "''"
            else None
        )
        self._push_base_images = config.option.ssi_push_base_images
        self._libray_version = ComponentVersion(self._library, "v9.99.99")
        self._datadog_apm_inject_version = "v9.99.99"
        # The runtime that is installed on the base image (because we installed automatically or because the weblog
        # contains the runtime preinstalled). The language is the language used by the tested datadog library
        self._installed_language_runtime: Version | None = None

        logger.stdout(
            f"Configuring scenario with: Weblog: [{self._base_weblog}] Library: [{self._library}] "
            f"Base Image: [{self._base_image}] Arch: [{self._arch}] Runtime: [{self._installable_runtime}] "
            f"Env: {self._env}"
        )
        if self._custom_injector_version:
            logger.stdout(f"Using custom injector version: {self._custom_injector_version}")
        if self._custom_library_version:
            logger.stdout(f"Using custom library version: {self._custom_library_version}")

        # Build the docker images to generate the weblog image
        # Steps to build the docker ssi image:
        # 1. Build the base image with the language runtime and the common dependencies
        #    If the runtime is not needed, we install only the common dependencies
        # 2. Build the ssi installer image with the ssi installer
        #    This image will be push in the registry
        # 3. Build the weblog image with the ssi installer and the weblog app
        #    3.1 Install the ssi to run the auto instrumentation (allway build using the ssi installer image buit in
        #        the step 2)
        #    3.2 Build the weblog image using the ssi image built in the step 3.1
        self.ssi_image_builder = DockerSSIImageBuilder(
            self.name,
            self.host_log_folder,
            self._base_weblog,
            self._base_image,
            self._library,
            self._arch,
            self._installable_runtime,
            self._push_base_images,
            self._env,
            self._custom_library_version,
            self._custom_injector_version,
            appsec_enabled=self._appsec_enabled,
        )
        self.ssi_image_builder.configure()
        self.ssi_image_builder.build_weblog()

        # Folder for messages from the test agent
        self._create_log_subfolder("interfaces/test_agent")
        # Socket folder for the communication between the test agent and the weblog
        self._create_log_subfolder("interfaces/test_agent_socket")

        # Extract version of the components that we are testing.
        json_tested_component = self.ssi_image_builder.tested_components()
        self.fill_context(json_tested_component)
        self.print_installed_components()

        for container in self._required_containers:
            try:
                container.configure(host_log_folder=self.host_log_folder, replay=self.replay)
            except Exception as e:
                logger.error("Failed to configure container ", e)
                logger.stdout("ERROR configuring container. check log file for more details")

        self.warmups.append(self._create_network)
        self.warmups.append(self._start_containers)

        if "GITLAB_CI" in os.environ:
            self.warmups.append(self.fix_gitlab_network)

    def _create_network(self):
        self._network = create_network()

    def _start_containers(self):
        for container in self._required_containers:
            container.start(self._network)

    def fix_gitlab_network(self):
        old_weblog_url = self.weblog_url
        self.weblog_url = self.weblog_url.replace("localhost", self._weblog_injection.network_ip(self._network))
        logger.debug(f"GITLAB_CI: Rewritten weblog url from {old_weblog_url} to {self.weblog_url}")
        self.agent_host = self._agent_container.network_ip(self._network)
        logger.debug(f"GITLAB_CI: Set agent host to {self.agent_host}")

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:  # noqa: ARG002
        self.close_targets()

    def close_targets(self):
        for container in reversed(self._required_containers):
            container.remove()

    def find_image_name(self, image: str, architecture: str) -> str | None:
        """Search for the image name given its image URL and architecture.

        Args:
            json_path (str): Path to the JSON file.
            image (str): The image URL (e.g., "public.ecr.aws/lts/ubuntu:22.04").
            architecture (str): The architecture (e.g., "linux/amd64").

        Returns:
            Optional[str]: The matching name, or None if not found.

        """
        json_path = "utils/docker_ssi/docker_ssi_images.json"
        with open(json_path, "r") as f:
            data = json.load(f)

        for entry in data.get("docker_ssi_images", []):
            if entry["image"] == image and entry["architecture"] == architecture:
                return entry["name"]

        return None

    def fill_context(self, json_tested_components: dict):
        """After extract the components from the weblog, fill the context with the data"""

        image_internal_name = self.find_image_name(self._base_image, self._arch)
        self.configuration["os"] = image_internal_name
        self.configuration["arch"] = self._arch.replace("linux/", "")

        for key, value in json_tested_components.items():
            try:
                self.components[key] = ComponentVersion(
                    key.removeprefix("datadog-apm-library-"),
                    value.lstrip(" "),
                ).version
            except ValueError:
                self.components[key] = value.lstrip(" ")
            if key == "weblog_url" and value:
                self.weblog_url = value.lstrip(" ")
                continue
            if key == "runtime_version" and value:
                self._installed_language_runtime = Version(value.lstrip(" "))
                # Runtime version is stored as configuration not as dependency
                del self.components[key]
                self.configuration["runtime_version"] = f"{self._installed_language_runtime}"
            if key.startswith("datadog-apm-inject") and value:
                self._datadog_apm_inject_version = f"v{value.lstrip(' ')}"
            if key.startswith("datadog-apm-library-") and self.components[key]:
                library_version_number = value.lstrip(" ")
                self._libray_version = ComponentVersion(self._library, str(library_version_number))
                # We store without the lang sufix
                self.components["datadog-apm-library"] = self.components[key]
                self.components[self._library] = self.components[key]
                del self.components[key]

    def print_installed_components(self):
        logger.stdout("Installed components")
        for component in self.components:
            logger.stdout(f"{component}: {self.components[component]}")

        logger.stdout("Configuration")
        for conf in self.configuration:
            logger.stdout(f"{conf}: {self.configuration[conf]}")

    def check_installed_components(self):
        """Check the the injector and library versions are present"""
        is_valid = True
        if not self.components.get("datadog-apm-library"):
            is_valid = False
            logger.stdout(
                "❌ Library version not found. Could not get the tracer image or the version of the library "
                "could not be extracted"
            )
            if self._custom_library_version:
                logger.stdout(
                    f"🛠️ You have specified a custom version of the library (--ssi-library-version), please check "
                    f"that the reference [{self._custom_library_version}] is correct."
                )
        if not self._datadog_apm_inject_version:
            is_valid = False
            logger.stdout(
                "❌ Injector version not found. Could not get the injector image or the version of the injector "
                "could not be extracted"
            )
            if self._custom_injector_version:
                logger.stdout(
                    f"🛠️ You have specified a custom version of the injector (--ssi-injector-version), please check "
                    f"that the reference [{self._custom_injector_version}] is correct."
                )
        if not is_valid:
            logger.stdout(f"🌍 You have set the environment to [{self._env}]. Check the docker build logs.\n\n\n")
            raise ValueError("❌ Error: Could not get the library or injector version. ❌")
        logger.stdout("✅ All components are installed correctly. ✅")

    def post_setup(self, session: pytest.Session) -> None:  # noqa: ARG002
        self.check_installed_components()

        logger.stdout("--- Waiting for all traces and telemetry to be sent to test agent ---")
        time.sleep(15)
        interfaces.test_agent.collect_data(
            f"{self.host_log_folder}/interfaces/test_agent", agent_host=self.agent_host, agent_port=self.agent_port
        )

    @property
    def library(self):
        return self._libray_version

    @property
    def installed_language_runtime(self):
        return self._installed_language_runtime

    @property
    def weblog_variant(self):
        return self._base_weblog

    @property
    def dd_apm_inject_version(self):
        return self._datadog_apm_inject_version

    @property
    def configuration(self):
        return self._configuration

    def get_junit_properties(self) -> dict[str, str]:
        result = super().get_junit_properties()

        result["dd_tags[systest.suite.context.library.name]"] = self.library.name
        result["dd_tags[systest.suite.context.library.version]"] = self.library.version
        result["dd_tags[systest.suite.context.weblog_variant]"] = self.weblog_variant
        result["dd_tags[systest.suite.context.agent]"] = self.components["agent"]
        result["dd_tags[systest.suite.context.datadog-apm-inject.version]"] = self.dd_apm_inject_version
        result["dd_tags[systest.suite.context.datadog-installer.version]"] = self.components["datadog-installer"]
        result["dd_tags[systest.suite.context.installed_language_runtime]"] = self.installed_language_runtime or ""
        result["dd_tags[systest.suite.context.os]"] = self.configuration["os"]
        result["dd_tags[systest.suite.context.arch]"] = self.configuration["arch"]

        return result


def _get_free_port():
    last_allowed_port = 32000
    port = random.randint(1100, last_allowed_port - 600)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    while port <= last_allowed_port:
        try:
            sock.bind(("", port))
            sock.close()
            return port
        except OSError:
            port += 1
    raise OSError("no free ports")
