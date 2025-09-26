import json
import os
import random
import socket
import time
from docker.errors import BuildError
from docker.models.networks import Network
import pytest

from utils import interfaces
from utils._context.component_version import ComponentVersion, Version
from utils._context.containers import (
    create_network,
    DockerSSIContainer,
    APMTestAgentContainer,
    TestedContainer,
    _get_client as get_docker_client,
)
from utils.docker_ssi.docker_ssi_matrix_utils import resolve_runtime_version
from utils.docker_ssi.rebuildr_manager import RebuildrManager, RebuildrConfig
from utils.docker_ssi.ssi_rebuildr_factory import SSIRebuildrFactory
from utils._logger import logger
from utils.virtual_machine.vm_logger import vm_logger

from .core import Scenario


class ContainerRemovalError(Exception):
    """Exception raised when a container fails to be removed."""


class ImagePushError(Exception):
    """Exception raised when a docker image push operation fails."""


class DockerSSIScenario(Scenario):
    """Scenario test the ssi installer on a docker environment and runs APM test agent"""

    _network: Network = None

    def __init__(
        self, name, doc, extra_env_vars: dict | None = None, scenario_groups=None, appsec_enabled=None
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
        self._custom_library_version = config.option.ssi_library_version
        self._custom_injector_version = config.option.ssi_injector_version

        # The runtime that we want to install on the base image. it could be empty if we don't need to install a runtime
        self._installable_runtime = (
            config.option.ssi_installable_runtime
            if config.option.ssi_installable_runtime and config.option.ssi_installable_runtime != "''"
            else None
        )
        self._push_base_images = config.option.ssi_push_base_images
        self._force_build = config.option.ssi_force_build
        self._libray_version = ComponentVersion(self._library, "v9.99.99")
        self._datadog_apm_inject_version = "v9.99.99"
        # The runtime that is installed on the base image (because we installed automatically or because the weblog contains the runtime preinstalled).
        # the language is the language used by the tested datadog library
        self._installed_language_runtime: Version | None = None

        logger.stdout(
            f"Configuring scenario with: Weblog: [{self._base_weblog}] Library: [{self._library}] Base Image: [{self._base_image}] Arch: [{self._arch}] Runtime: [{self._installable_runtime}] Env: {self._env}"
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
        #    3.1 Install the ssi to run the auto instrumentation (allway build using the ssi installer image buit in the step 2)
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
            self._force_build,
            self._env,
            self._custom_library_version,
            self._custom_injector_version,
            self._appsec_enabled,
        )
        self.ssi_image_builder.configure()
        self.ssi_image_builder.build()

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

    def _create_network(self):
        self._network = create_network()

    def _start_containers(self):
        for container in self._required_containers:
            container.start(self._network)

    def get_warmups(self):
        warmups = super().get_warmups()

        warmups.append(self._create_network)
        warmups.append(self._start_containers)

        if "GITLAB_CI" in os.environ:
            warmups.append(self.fix_gitlab_network)

        return warmups

    def fix_gitlab_network(self):
        old_weblog_url = self.weblog_url
        self.weblog_url = self.weblog_url.replace("localhost", self._weblog_injection.network_ip(self._network))
        logger.debug(f"GITLAB_CI: Rewritten weblog url from {old_weblog_url} to {self.weblog_url}")
        self.agent_host = self._agent_container.network_ip(self._network)
        logger.debug(f"GITLAB_CI: Set agent host to {self.agent_host}")

    def pytest_sessionfinish(self, session, exitstatus):  # noqa: ARG002
        self.close_targets()

    def close_targets(self):
        for container in reversed(self._required_containers):
            try:
                container.remove()
                logger.info(f"Removing container {container}")
            except Exception as e:
                logger.exception(f"Failed to remove container {container}")
                raise ContainerRemovalError(f"Failed to remove container {container}") from e

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

    def fill_context(self, json_tested_components):
        """After extract the components from the weblog, fill the context with the data"""

        image_internal_name = self.find_image_name(self._base_image, self._arch)
        self.configuration["os"] = image_internal_name
        self.configuration["arch"] = self._arch.replace("linux/", "")

        for key in json_tested_components:
            self.components[key] = json_tested_components[key].lstrip(" ")
            if key == "weblog_url" and json_tested_components[key]:
                self.weblog_url = json_tested_components[key].lstrip(" ")
                continue
            if key == "runtime_version" and json_tested_components[key]:
                self._installed_language_runtime = Version(json_tested_components[key].lstrip(" "))
                # Runtime version is stored as configuration not as dependency
                del self.components[key]
                self.configuration["runtime_version"] = f"{self._installed_language_runtime}"
            if key.startswith("datadog-apm-inject") and json_tested_components[key]:
                self._datadog_apm_inject_version = f"v{json_tested_components[key].lstrip(' ')}"
            if key.startswith("datadog-apm-library-") and self.components[key]:
                library_version_number = json_tested_components[key].lstrip(" ")
                self._libray_version = ComponentVersion(self._library, library_version_number)
                # We store without the lang sufix
                self.components["datadog-apm-library"] = self.components[key]
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
                "❌ Library version not found. Could not get the tracer image or the version of the library could not be extracted"
            )
            if self._custom_library_version:
                logger.stdout(
                    f"🛠️ You have specified a custom version of the library (--ssi-library-version), please check that the reference [{self._custom_library_version}] is correct."
                )
        if not self._datadog_apm_inject_version:
            is_valid = False
            logger.stdout(
                "❌ Injector version not found. Could not get the injector image or the version of the injector could not be extracted"
            )
            if self._custom_injector_version:
                logger.stdout(
                    f"🛠️ You have specified a custom version of the injector (--ssi-injector-version), please check that the reference [{self._custom_injector_version}] is correct."
                )
        if not is_valid:
            logger.stdout(f"🌍 You have set the environment to [{self._env}]. Check the docker build logs.\n\n\n")
            raise ValueError("❌ Error: Could not get the library or injector version. ❌")
        logger.stdout("✅ All components are installed correctly. ✅")

    def post_setup(self, session):  # noqa: ARG002
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


class DockerSSIImageBuilder:
    """Manages the docker image building for the SSI scenario"""

    def __init__(
        self,
        scenario_name,
        host_log_folder,
        base_weblog,
        base_image,
        library,
        arch,
        installable_runtime,
        push_base_images,
        force_build,
        env,
        custom_library_version,
        custom_injector_version,
        appsec_enabled=None,
    ) -> None:
        self.scenario_name = scenario_name
        self.host_log_folder = host_log_folder
        self._base_weblog = base_weblog
        self._base_image = base_image
        self._library = library
        self._arch = arch
        self._installable_runtime = installable_runtime
        self._push_base_images = push_base_images
        self._force_build = force_build
        # When do we need to push the base images to the docker registry?
        # Option 1: When we added the run parameter --push-base-images
        # Option 2: When the base image is not found on the registry
        self.should_push_base_images = False
        self._weblog_docker_image = None
        self._env = env
        self._custom_library_version = custom_library_version
        self._custom_injector_version = custom_injector_version
        self._appsec_enabled = appsec_enabled

    @property
    def dd_lang(self) -> str:
        return "js" if self._library == "nodejs" else self._library

    def _raise_config_error(self) -> None:
        """Helper method to raise configuration error."""
        raise ValueError("Language dependencies configuration is None")

    def configure(self):
        logger.stdout("🔧 ========================================")
        logger.stdout("🔧 DOCKER SSI IMAGE BUILDER CONFIGURATION")
        logger.stdout("🔧 ========================================")

        # Generate base docker tags
        self.base_dependencies_image_tag = self.get_base_dependencies_docker_tag()
        logger.stdout(f"📦 Base dependencies docker tag: {self.base_dependencies_image_tag}")
        self.base_runtime_image_tag = self.get_base_runtime_docker_tag()
        logger.stdout(f"📦 Base runtime docker tag: {self.base_runtime_image_tag}")

        # Setup registry and image tags
        self.docker_registry_base_url = os.getenv("PRIVATE_DOCKER_REGISTRY", "")
        if self.docker_registry_base_url:
            logger.stdout(f"🏪 Docker registry: {self.docker_registry_base_url}")
        else:
            logger.stdout("🏪 Docker registry: Not configured (local builds only)")

        # Set registry tag based on whether registry is configured
        if self.docker_registry_base_url:
            self._docker_registry_tag = f"{self.docker_registry_base_url}/system-tests-v2/ssi_installer_{self.base_runtime_image_tag if self._installable_runtime else self.base_dependencies_image_tag}"
        else:
            self._docker_registry_tag = f"ssi_installer_{self.base_runtime_image_tag if self._installable_runtime else self.base_dependencies_image_tag}"
        self.ssi_full_image_tag = (
            f"ssi_full_{self.base_runtime_image_tag if self._installable_runtime else self.base_dependencies_image_tag}"
        )

        logger.stdout(f"🔗 SSI installer tag: {self._docker_registry_tag}")
        logger.stdout(f"🔗 SSI full tag: {self.ssi_full_image_tag}")

        # Initialize rebuildr client
        logger.stdout("⚡ Initializing RebuildrManager singleton...")
        self.rebuildr_client = RebuildrManager.get_instance(
            working_directory="utils/build/ssi/", host_log_folder=self.host_log_folder
        )
        logger.stdout("✅ RebuildrManager initialized successfully")

        # Configure the three main images using RebuildrManager
        logger.stdout("🏗️ Configuring Docker images...")
        self._configure_images()
        logger.stdout("✅ Docker SSI configuration completed")

    def _configure_images(self):
        """Configure the three main images: lang_deps, ssi_installer, and ssi using RebuildrManager."""
        logger.stdout("📋 ──────────────────────────────────────")
        logger.stdout("📋 CONFIGURING DOCKER IMAGES")
        logger.stdout("📋 ──────────────────────────────────────")

        # 1. Configure base_deps_image (base dependencies)
        logger.stdout("🔨 [1/4] Configuring Dependencies Image...")
        logger.stdout(f"⚙️  Base image: {self._base_image}")
        logger.stdout("⚙️  Type: Base dependencies only (no runtime)")
        # Configure base dependencies image using SSI factory
        self.base_deps_config = SSIRebuildrFactory.create_base_deps_config(
            image_repository=self.base_dependencies_image_tag,
            base_image=self._base_image,
            additional_env_vars={},
        )
        logger.stdout("🔍 Calculating SHA256 signature for base deps...")
        self.base_dependencies_image_id = "src-id-" + self.rebuildr_client.get_sha256_signature(self.base_deps_config)
        logger.stdout(f"🔑 Base dependencies image ID: {self.base_dependencies_image_id}")
        logger.stdout("✅ Base dependencies configuration created")

        # 2. Configure base_runtime_image (language runtime )
        logger.stdout("🔨 [2/4] Configuring language runtime Image...")

        # Initialize optional runtime variables with proper type annotations
        self.base_runtime_config: RebuildrConfig | None = None
        self.base_runtime_image_id: str | None = None

        if self._installable_runtime:
            logger.stdout(f"⚙️  Base image: {self.base_runtime_image_tag}")
            logger.stdout("⚙️  Type: Language runtime only")
            logger.stdout(f"⚙️  Runtime: {self._installable_runtime} (using Docker client)")
            self.base_runtime_config = SSIRebuildrFactory.create_base_runtime_config(
                image_repository=self.base_runtime_image_tag,
                base_image=self.base_dependencies_image_tag + ":" + self.base_dependencies_image_id,
                dd_lang=self.dd_lang,
                runtime_versions=self._installable_runtime,
            )
            logger.stdout("🔍 Calculating SHA256 signature for base runtime...")
            self.base_runtime_image_id = "src-id-" + self.rebuildr_client.get_sha256_signature(self.base_runtime_config)
            logger.stdout(f"🔑 Base runtime image ID: {self.base_runtime_image_id}")
            logger.stdout("✅ Base runtime configuration created")
        else:
            logger.stdout("🔨 Skipping language runtime Image...")
            self.base_runtime_config = None
            self.base_runtime_image_id = None

        # 3. Configure ssi_installer_image
        logger.stdout("🔨 [3/4] Configuring SSI Installer Image...")
        base_with_tag = (
            self.base_dependencies_image_tag + ":" + self.base_dependencies_image_id
            if not self._installable_runtime
            else self.base_runtime_image_tag + ":" + self.base_runtime_image_id
        )
        logger.stdout(f"⚙️  Base image: {base_with_tag}")
        logger.stdout(f"⚙️  Registry: {self._docker_registry_tag}")

        self.ssi_installer_config = SSIRebuildrFactory.create_ssi_installer_config(
            image_repository=self._docker_registry_tag,
            base_image=base_with_tag,
            dd_api_key="xxxxxxxxxx",  # Default API key as used in original implementation
            additional_env_vars={},
        )
        logger.stdout("🔍 Calculating SHA256 signature for SSI installer...")
        self.ssi_installer_image_id = "src-id-" + self.rebuildr_client.get_sha256_signature(self.ssi_installer_config)
        logger.stdout(f"🔑 SSI installer image ID: {self.ssi_installer_image_id}")
        logger.stdout("✅ SSI installer configuration created")

        # Check if the SSI installer image exists in registry
        installer_image_with_tag = self._docker_registry_tag + ":" + self.ssi_installer_image_id
        logger.stdout("🔍 Checking if SSI installer image exists in registry...")
        self.ssi_installer_image_exists = self.exist_ssi_installer_image(installer_image_with_tag)
        self.should_push_base_images = True if not self.ssi_installer_image_exists or self._push_base_images else False

        # 3. Configure ssi_image (full SSI with auto-injection)
        logger.stdout("🔨 [3/3] Configuring SSI Full Image...")
        logger.stdout(f"⚙️  Language: {self.dd_lang}")
        logger.stdout(f"⚙️  Environment: {self._env}")
        if self._custom_library_version:
            logger.stdout(f"⚙️  Library version: {self._custom_library_version}")
        if self._custom_injector_version:
            logger.stdout(f"⚙️  Injector version: {self._custom_injector_version}")
        if self._appsec_enabled is not None:
            logger.stdout(f"⚙️  AppSec enabled: {self._appsec_enabled}")

        self.ssi_full_config = SSIRebuildrFactory.create_ssi_config(
            image_repository=self.ssi_full_image_tag,
            base_image=installer_image_with_tag,
            dd_api_key="deadbeef",  # Default API key as used in original implementation
            dd_lang=self.dd_lang,
            ssi_env=self._env,
            dd_installer_library_version=self._custom_library_version or "",
            dd_installer_injector_version=self._custom_injector_version or "",
            dd_appsec_enabled=str(self._appsec_enabled) if self._appsec_enabled is not None else "",
            additional_env_vars={},
        )
        logger.stdout("✅ SSI full configuration created")
        logger.stdout("📋 Image configuration completed successfully")

    def build(self):
        """Manages the build process of the final weblog image with runtime language and ssi installed"""
        logger.stdout("🚀 ========================================")
        logger.stdout("🚀 DOCKER SSI  BUILD PROCESS")
        logger.stdout("🚀 ========================================")

        # Determine build strategy
        if not self.ssi_installer_image_exists:
            logger.stdout("📦 Base image not found in registry - will build from scratch")
        if self._push_base_images:
            logger.stdout("🔄 Force push base images enabled")
        if self._force_build:
            logger.stdout("🔄 Force build enabled")

        if not self.ssi_installer_image_exists or self._push_base_images or self._force_build:
            logger.stdout("🏗️ Building base images (lang deps + SSI installer)...")
            # Build the base image
            self.build_deps_image()
            self.build_runtime_image()
            self.build_ssi_installer_image()
        else:
            logger.stdout("✅ Using existing base images from registry")

        self.should_push_base_images = True if not self.ssi_installer_image_exists or self._push_base_images else False
        self.build_full_ssi_installer_image()
        logger.stdout("🏗️ Building final weblog image...")
        self.build_weblog_image()
        logger.stdout("🚀 Weblog build process completed successfully!")

    def exist_ssi_installer_image(self, image_tag):
        """Check if the SSI installer image is available in the docker registry"""
        try:
            logger.stdout(f"🔍 Searching for image in registry: {image_tag}")
            get_docker_client().images.pull(image_tag)
            logger.stdout("✅ SSI installer image found in registry")
            return True
        except Exception:
            logger.stdout(f"❌ SSI installer image not found in registry: {image_tag}")
            return False

    def get_base_dependencies_docker_tag(self):
        """Resolves and format the docker tag for the base image"""

        return (
            f"{self._base_image}_deps_{self._arch}".replace(".", "_")
            .replace("-", "-")
            .replace(":", "-")
            .replace("/", "-")
            .lower()
        )

    def get_base_runtime_docker_tag(self):
        """Resolves and format the docker tag for the base image"""
        runtime = (
            resolve_runtime_version(self._library, self._installable_runtime) + "_" if self._installable_runtime else ""
        )
        return (
            f"{self._base_image}_{runtime}{self._arch}".replace(".", "_")
            .replace("-", "-")
            .replace(":", "-")
            .replace("/", "-")
            .lower()
        )

    def build_deps_image(self):
        """Build the base dependencies image. Install only basic system dependencies.
        This image contains the system-level dependencies required for SSI installation
        but does not include any language runtime components.
        """
        logger.stdout("🔨 ──────────────────────────────────────")
        logger.stdout("🔨 BUILDING BASE DEPENDENCIES IMAGE")
        logger.stdout("🔨 ──────────────────────────────────────")

        build_result = None
        try:
            logger.stdout("🏗️  Building base dependencies image...")
            logger.stdout(f"📦 Target tag: {self.base_deps_config.image_repository}")
            logger.stdout(f"⚙️  Base image: {self.base_deps_config.args['BASE_IMAGE']}")
            logger.stdout("⚙️  Type: Base dependencies only (no language runtime)")
            logger.stdout("🔧 Using RebuildrManager for build process")
            build_result = self.rebuildr_client.build_image(self.base_deps_config)

            if build_result is not None and build_result.stdout:
                logger.stdout(f"📄 Build output: {build_result.stdout[:200]}...")  # Truncate long output
            logger.stdout("✅ Base dependencies image build completed successfully!")

        except Exception as e:
            logger.stdout(f"❌ ERROR: Unexpected failure during base dependencies build: {e}")
            raise

    def build_runtime_image(self):
        """Build the runtime image. Install the language runtime on the base dependencies image."""
        logger.stdout("🔨 ──────────────────────────────────────")
        logger.stdout("🔨 BUILDING LANGUAGE RUNTIME IMAGE")
        logger.stdout("🔨 ──────────────────────────────────────")

        build_result = None
        try:
            if self._installable_runtime and self.base_runtime_config is not None:
                logger.stdout("🏗️  Building language runtime image...")
                logger.stdout(f"📦 Target tag: {self.base_runtime_config.image_repository}")
                logger.stdout(f"⚙️  Base image: {self.base_runtime_config.args['BASE_IMAGE']}")
                logger.stdout(f"⚙️  Runtime: {self._installable_runtime}")
                logger.stdout(f"⚙️  DD_LANG: {self.base_runtime_config.args['DD_LANG']}")
                logger.stdout(f"⚙️  Architecture: {self._arch}")
                logger.stdout("🔧 Using RebuildrManager for build process")

                logger.stdout("⏳ Starting Rebuildr build process...")
                build_result = self.rebuildr_client.build_image(self.base_runtime_config)
            else:
                logger.stdout("⚠️  Skipping runtime image build - no installable runtime configured")
                return

            if build_result is not None and build_result.stdout:
                logger.stdout(f"📄 Build output: {build_result.stdout[:200]}...")  # Truncate long output
            logger.stdout("✅ Language runtime image build completed successfully!")

        except Exception as e:
            logger.stdout(f"❌ ERROR: Unexpected failure during runtime image build: {e}")
            raise

    def build_ssi_installer_image(self):
        """Build the ssi installer image. Install only the ssi installer on the image"""
        logger.stdout("🔨 ──────────────────────────────────────")
        logger.stdout(f"🔨 BUILDING SSI INSTALLER IMAGE (push: {self.should_push_base_images})")
        logger.stdout("🔨 ──────────────────────────────────────")

        try:
            logger.stdout("🏗️  Building SSI installer image...")
            logger.stdout(f"📦 Target repository: {self.ssi_installer_config.image_repository}")
            logger.stdout(f"⚙️  Base image: {self.ssi_installer_config.args['BASE_IMAGE']}")
            logger.stdout(f"⚙️  Architecture: {self._arch}")
            logger.stdout("🔧 Using RebuildrManager for build process")

            # Use the configured SSI installer image with RebuildrManager
            logger.stdout("⏳ Starting Rebuildr build process...")
            if self.should_push_base_images and self.docker_registry_base_url:
                logger.stdout("⏳ Starting Rebuildr build and push process...")
                build_result = self.rebuildr_client.build_and_push_image(self.ssi_installer_config)
            else:
                build_result = self.rebuildr_client.build_image(self.ssi_installer_config)

            if build_result.stdout:
                logger.stdout(f"📄 Build output: {build_result.stdout[:200]}...")  # Truncate long output
            logger.stdout("✅ SSI installer image build completed successfully!")

        except Exception as e:
            logger.stdout(f"❌ ERROR: Unexpected failure during SSI installer build: {e}")
            raise

    def build_full_ssi_installer_image(self):
        """Build the full ssi (to perform the auto inject)"""
        try:
            # Install the ssi to run the auto instrumentation using RebuildrManager
            # Update the SSI config with the correct base image (_docker_registry_tag)
            # self.ssi_full_config.args["BASE_IMAGE"] = self._docker_registry_tag
            logger.stdout("🔨 ──────────────────────────────────────")
            logger.stdout("🔨 BUILDING SSI FULL IMAGE")
            logger.stdout("🔨 ──────────────────────────────────────")
            logger.stdout("⏳ Starting SSI full image build process...")
            logger.stdout(f"⚙️  Base image: {self.ssi_full_config.args['BASE_IMAGE']}")
            logger.stdout(f"⚙️  Registry: {self.ssi_full_config.image_repository}")
            self.rebuildr_client.build_image(self.ssi_full_config)
            logger.stdout("✅ SSI full image build completed successfully!")

        except Exception as e:
            logger.stdout("❌ ERROR: Failed to build weblog image")
            logger.exception(f"Failed to build docker image: {e}")
            raise

    def build_weblog_image(self):
        """Build the final weblog image. Uses base ssi installer image, install
        the full ssi (to perform the auto inject) and build the weblog image
        """
        weblog_docker_tag = "weblog-injection:latest"
        try:
            logger.stdout("🔨 ──────────────────────────────────────")
            logger.stdout("🔨 BUILDING WEBLOG IMAGE")
            logger.stdout("🔨 ──────────────────────────────────────")
            # Execute rebuildr command using client
            logger.stdout(
                f"[Building:{weblog_docker_tag}] Building weblog app on base image [{self.ssi_full_image_tag}]."
            )
            logger.stdout("⏳ Starting weblog image build process...")
            logger.stdout(f"⚙️  Base image: {self.ssi_full_image_tag}")
            logger.stdout(f"⚙️  Registry: {weblog_docker_tag}")
            # Build the weblog image
            self._weblog_docker_image, build_logs = get_docker_client().images.build(
                path=".",
                dockerfile=f"utils/build/ssi/{self._library}/{self._base_weblog}.Dockerfile",
                platform=self._arch,
                tag=weblog_docker_tag,
                nocache=self._force_build or self.should_push_base_images,
                buildargs={"BASE_IMAGE": self.ssi_full_image_tag},
            )
            self.print_docker_build_logs(weblog_docker_tag, build_logs)
            logger.info("✅ Weblog build done!")
        except BuildError as e:
            logger.stdout("❌ ERROR: Failed to build weblog image")
            logger.exception(f"Failed to build docker image: {e}")
            self.print_docker_build_logs("Error building weblog", e.build_log)
            raise BuildError("Failed to build weblog docker image", e.build_log) from e

    def tested_components(self):
        """Extract weblog versions of lang runtime, agent, installer, tracer.
        Also extracts the weblog url env variable
        Return json with the data
        """
        logger.info("Weblog extract tested components")
        result = get_docker_client().containers.run(
            image=self._weblog_docker_image, command=f"/tested_components.sh {self.dd_lang}", remove=True
        )
        logger.info(f"Testes components: {result.decode('utf-8')}")
        return json.loads(result.decode("utf-8").replace("'", '"'))

    def print_docker_build_logs(self, image_tag, build_logs):
        """Print the docker build logs to docker_build.log file"""
        vm_logger(self.host_log_folder, "docker_build", log_folder=self.host_log_folder).info(
            "***************************************************************"
        )
        vm_logger(self.host_log_folder, "docker_build", log_folder=self.host_log_folder).info(
            f"    Building docker image with tag: {image_tag}   "
        )
        vm_logger(self.host_log_folder, "docker_build", log_folder=self.host_log_folder).info(
            "***************************************************************"
        )

        for chunk in build_logs:
            if "stream" in chunk:
                for line in chunk["stream"].splitlines():
                    vm_logger(self.host_log_folder, "docker_build", log_folder=self.host_log_folder).info(line)

    def print_docker_push_logs(self, image_tag, push_logs):
        """Print the docker push logs to docker_push.log file"""
        vm_logger(self.host_log_folder, "docker_push", log_folder=self.host_log_folder).info(
            "***************************************************************"
        )
        vm_logger(self.host_log_folder, "docker_push", log_folder=self.host_log_folder).info(
            f"    Push docker image with tag: {image_tag}   "
        )
        vm_logger(self.host_log_folder, "docker_push", log_folder=self.host_log_folder).info(
            "***************************************************************"
        )
        vm_logger(self.host_log_folder, "docker_push", log_folder=self.host_log_folder).info(push_logs)


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
