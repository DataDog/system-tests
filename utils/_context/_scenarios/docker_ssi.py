import json
import time
import os

import docker
from docker.errors import BuildError

import utils.tools
from utils import context, interfaces
from utils._context.library_version import LibraryVersion, Version
from utils._context.containers import (
    create_network,
    DockerSSIContainer,
    APMTestAgentContainer,
    TestedContainer,
    _get_client as get_docker_client,
)
from utils.docker_ssi.docker_ssi_matrix_utils import resolve_runtime_version
from utils.tools import logger
from utils.virtual_machine.vm_logger import vm_logger

from .core import Scenario


class DockerSSIScenario(Scenario):
    """Scenario test the ssi installer on a docker environment and runs APM test agent """

    def __init__(self, name, doc, scenario_groups=None) -> None:
        super().__init__(name, doc=doc, github_workflow="dockerssi", scenario_groups=scenario_groups)

        self._weblog_injection = DockerSSIContainer(host_log_folder=self.host_log_folder)

        if "GITLAB_CI" in os.environ:
            self.agent_port = utils.tools.get_free_port()
        else:
            self.agent_port = 8126

        self._required_containers: list[TestedContainer] = []
        self._required_containers.append(APMTestAgentContainer(host_log_folder=self.host_log_folder, agent_port=self.agent_port))
        self._required_containers.append(self._weblog_injection)
        self.weblog_url = "http://localhost:18080"
        self._tested_components = {}

    def configure(self, config):
        assert config.option.ssi_library, "library must be set: java,python,nodejs,dotnet,ruby"

        self._base_weblog = config.option.ssi_weblog
        self._library = config.option.ssi_library
        self._base_image = config.option.ssi_base_image
        self._arch = config.option.ssi_arch
        # The runtime that we want to install on the base image. it could be empty if we don't need to install a runtime
        self._installable_runtime = (
            config.option.ssi_installable_runtime
            if config.option.ssi_installable_runtime and config.option.ssi_installable_runtime != "''"
            else None
        )
        self._push_base_images = config.option.ssi_push_base_images
        self._force_build = config.option.ssi_force_build
        self._libray_version = LibraryVersion(self._library, "v9.99.99")
        self._datadog_apm_inject_version = "v9.99.99"
        # The runtime that is installed on the base image (because we installed automatically or because the weblog contains the runtime preinstalled).
        # the language is the language used by the tested datadog library
        self._installed_language_runtime = None
        # usually base_weblog + base_image + (runtime) + arch
        self._weblog_composed_name = None

        logger.stdout(
            f"Configuring scenario with: Weblog: [{self._base_weblog}] Library: [{self._library}] Base Image: [{self._base_image}] Arch: [{self._arch}] Runtime: [{self._installable_runtime}]"
        )

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
            self._base_weblog,
            self._base_image,
            self._library,
            self._arch,
            self._installable_runtime,
            self._push_base_images,
            self._force_build,
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

        if "GITLAB_CI" in os.environ:
            self.weblog_url = self.weblog_url.replace("localhost", "weblog-injection")

        self._weblog_composed_name = f"{self._base_weblog}_{self.ssi_image_builder.get_base_docker_tag()}"
        for container in self._required_containers:
            try:
                container.configure(self.replay)
            except Exception as e:
                logger.error("Failed to configure container ", e)
                logger.stdout("ERROR configuring container. check log file for more details")

    def get_warmups(self):
        warmups = super().get_warmups()

        warmups.append(create_network)

        for container in self._required_containers:
            warmups.append(container.start)
        return warmups

    def close_targets(self):
        for container in reversed(self._required_containers):
            try:
                container.remove()
                logger.info(f"Removing container {container}")
            except:
                logger.exception(f"Failed to remove container {container}")
        # TODO push images only if all tests pass
        # TODO At this point, tests are not yet executed. There is not official hook in the Scenario class to do that,
        # TODO we can add one : pytest_sessionstart, it will contains the test result.
        # TODO The best way is to push the images from pipeline instead of from test runtime
        self.ssi_image_builder.push_base_image()

    def fill_context(self, json_tested_components):
        """ After extract the components from the weblog, fill the context with the data """

        logger.stdout("\nInstalled components:\n")

        for key in json_tested_components:
            if key == "weblog_url" and json_tested_components[key]:
                self.weblog_url = json_tested_components[key].lstrip(" ")
                continue
            if key == "runtime_version" and json_tested_components[key]:
                self._installed_language_runtime = Version(json_tested_components[key].lstrip(" "))
            if key.startswith("datadog-apm-inject") and json_tested_components[key]:
                self._datadog_apm_inject_version = f"v{json_tested_components[key].lstrip(' ')}"
            if key.startswith("datadog-apm-library-") and json_tested_components[key]:
                library_version_number = json_tested_components[key].lstrip(" ")
                self._libray_version = LibraryVersion(self._library, library_version_number)
            self._tested_components[key] = json_tested_components[key].lstrip(" ")
            logger.stdout(f"{key}: {self._tested_components[key]}")

    def post_setup(self):
        logger.stdout("--- Waiting for all traces to be sent to test agent ---")
        time.sleep(5)  # wait for the traces to be sent to the test agent
        interfaces.test_agent.collect_data(f"{self.host_log_folder}/interfaces/test_agent", agent_port=self.agent_port)

    @property
    def library(self):
        return self._libray_version

    @property
    def installed_language_runtime(self):
        return self._installed_language_runtime

    @property
    def components(self):
        return self._tested_components

    @property
    def weblog_variant(self):
        return self._weblog_composed_name

    @property
    def dd_apm_inject_version(self):
        return self._datadog_apm_inject_version


class DockerSSIImageBuilder:
    """ Manages the docker image building for the SSI scenario """

    def __init__(
        self, base_weblog, base_image, library, arch, installable_runtime, push_base_images, force_build
    ) -> None:
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

    def configure(self):
        self.docker_tag = self.get_base_docker_tag()
        self._docker_registry_tag = f"ghcr.io/datadog/system-tests/ssi_installer_{self.docker_tag}:latest"
        self.ssi_installer_docker_tag = f"ssi_installer_{self.docker_tag}"
        self.ssi_all_docker_tag = f"ssi_all_{self.docker_tag}"

    def build_weblog(self):
        """ Manages the build process of the weblog image """
        if not self.exist_base_image() or self._push_base_images or self._force_build:
            # Build the base image
            self.build_lang_deps_image()
            self.build_ssi_installer_image()
            self.should_push_base_images = True if not self.exist_base_image() or self._push_base_images else False
        self.build_weblog_image(
            self.ssi_installer_docker_tag
            if self._force_build or self.should_push_base_images
            else self._docker_registry_tag
        )

    def exist_base_image(self):
        """ Check if the base image is available in the docker registry """
        try:
            get_docker_client().images.pull(self._docker_registry_tag)
            logger.info("Base image found on the registry")
            return True
        except Exception:
            logger.info(f"Base image not found on the registry: ssi_{self.docker_tag}")
            return False

    def push_base_image(self):
        """ Push the base image to the docker registry. Base image contains: lang (if it's needed) and ssi installer (only with the installer, without ssi autoinject )"""
        if self.should_push_base_images:
            logger.stdout(f"Pushing base image to the registry: {self._docker_registry_tag}")
            try:
                docker.APIClient().tag(self.ssi_installer_docker_tag, self._docker_registry_tag)
                push_logs = get_docker_client().images.push(self._docker_registry_tag)
                self.print_docker_push_logs(self._docker_registry_tag, push_logs)
            except Exception as e:
                logger.stdout("ERROR pushing docker image. check log file for more details")
                logger.exception(f"Failed to push docker image: {e}")

    def get_base_docker_tag(self):
        """ Resolves and format the docker tag for the base image """
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

    def build_lang_deps_image(self):
        """ Build the lang image. Install the language runtime on the base image.
        We also install some linux deps for the ssi installer
        If there is not runtime installation requirement, we install only the linux deps
        Base lang contains the scrit to install the runtime and the script to install dependencies """
        dockerfile_template = None
        try:
            if self._installable_runtime:
                dockerfile_template = "base/base_lang.Dockerfile"
                logger.stdout(
                    f"[tag: {self.docker_tag}] Installing language runtime [{self._installable_runtime}] and common dependencies on base image [{self._base_image}]."
                )
            else:
                dockerfile_template = "base/base_deps.Dockerfile"
                logger.stdout(
                    f"[tag: {self.docker_tag}] Installing common dependencies on base image [{self._base_image}]. No language runtime installation required."
                )

            _, build_logs = get_docker_client().images.build(
                path="utils/build/ssi/",
                dockerfile=dockerfile_template,
                tag=self.docker_tag,
                platform=self._arch,
                nocache=self._force_build or self.should_push_base_images,
                buildargs={
                    "ARCH": self._arch,
                    "DD_LANG": self._library,
                    "RUNTIME_VERSIONS": self._installable_runtime,
                    "BASE_IMAGE": self._base_image,
                },
            )
            self.print_docker_build_logs(self.docker_tag, build_logs)

        except BuildError as e:
            logger.stdout("ERROR building docker file. check log file for more details")
            logger.exception(f"Failed to build docker image: {e}")
            self.print_docker_build_logs(f"Error building docker file [{dockerfile_template}]", e.build_log)
            raise e

    def build_ssi_installer_image(self):
        """ Build the ssi installer image. Install only the ssi installer on the image """
        try:
            logger.stdout(
                f"[tag:{self.ssi_installer_docker_tag}]Installing DD installer on base image [{self.docker_tag}]."
            )

            _, build_logs = get_docker_client().images.build(
                path="utils/build/ssi/",
                dockerfile="base/base_ssi_installer.Dockerfile",
                nocache=self._force_build or self.should_push_base_images,
                platform=self._arch,
                tag=self.ssi_installer_docker_tag,
                buildargs={"BASE_IMAGE": self.docker_tag},
            )
            self.print_docker_build_logs(self.ssi_installer_docker_tag, build_logs)

        except BuildError as e:
            logger.stdout("ERROR building docker file. check log file for more details")
            logger.exception(f"Failed to build docker image: {e}")
            self.print_docker_build_logs("Error building installer docker file", e.build_log)
            raise e

    def build_weblog_image(self, ssi_installer_docker_tag):
        """ Build the final weblog image. Uses base ssi installer image, install
        the full ssi (to perform the auto inject) and build the weblog image """

        weblog_docker_tag = "weblog-injection:latest"
        logger.stdout(f"Building docker final weblog image with tag: {weblog_docker_tag}")

        logger.stdout(
            f"[tag:{self.ssi_all_docker_tag}]Installing dd ssi for autoinjection on base image [{ssi_installer_docker_tag}]."
        )
        try:
            # Install the ssi to run the auto instrumentation
            _, build_logs = get_docker_client().images.build(
                path="utils/build/ssi/",
                dockerfile="base/base_ssi.Dockerfile",
                platform=self._arch,
                nocache=self._force_build or self.should_push_base_images,
                tag=self.ssi_all_docker_tag,
                buildargs={"DD_LANG": self._library, "BASE_IMAGE": ssi_installer_docker_tag},
            )
            self.print_docker_build_logs(self.ssi_all_docker_tag, build_logs)
            logger.stdout(
                f"0000[tag:{weblog_docker_tag}] Building weblog app on base image [{self.ssi_all_docker_tag}]."
            )
            # Build the weblog image
            self._weblog_docker_image, build_logs = get_docker_client().images.build(
                path=".",
                dockerfile=f"utils/build/ssi/{self._library}/{self._base_weblog}.Dockerfile",
                platform=self._arch,
                tag=weblog_docker_tag,
                nocache=self._force_build or self.should_push_base_images,
                buildargs={"BASE_IMAGE": self.ssi_all_docker_tag},
            )
            logger.info("Weblog build done 000000000!")
            self.print_docker_build_logs(weblog_docker_tag, build_logs)
            logger.info("Weblog build done!")
        except BuildError as e:
            logger.stdout("ERROR building docker file. check log file for more details")
            logger.exception(f"Failed to build docker image: {e}")
            self.print_docker_build_logs("Error building weblog", e.build_log)
            raise e

    def tested_components(self):
        """ Extract weblog versions of lang runtime, agent, installer, tracer.
        Also extracts the weblog url env variable
        Return json with the data"""
        logger.info("Weblog extract tested components")
        result = get_docker_client().containers.run(
            image=self._weblog_docker_image, command=f"/tested_components.sh {self._library}", remove=True
        )
        logger.info(f"Testes components: {result.decode('utf-8')}")
        return json.loads(result.decode("utf-8").replace("'", '"'))

    def print_docker_build_logs(self, image_tag, build_logs):
        """ Print the docker build logs to docker_build.log file """
        scenario_name = context.scenario.name
        vm_logger(scenario_name, "docker_build").info("***************************************************************")
        vm_logger(scenario_name, "docker_build").info(f"    Building docker image with tag: {image_tag}   ")
        vm_logger(scenario_name, "docker_build").info("***************************************************************")

        for chunk in build_logs:
            logger.debug("chunk")
            if "stream" in chunk:
                for line in chunk["stream"].splitlines():
                    vm_logger(scenario_name, "docker_build").info(line)

    def print_docker_push_logs(self, image_tag, push_logs):
        """ Print the docker push logs to docker_push.log file """
        scenario_name = context.scenario.name
        vm_logger(scenario_name, "docker_push").info("***************************************************************")
        vm_logger(scenario_name, "docker_push").info(f"    Push docker image with tag: {image_tag}   ")
        vm_logger(scenario_name, "docker_push").info("***************************************************************")
        vm_logger(scenario_name, "docker_push").info(push_logs)
