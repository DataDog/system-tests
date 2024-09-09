import os
import subprocess
import json
import docker
from docker.errors import DockerException, BuildError
from functools import lru_cache

from utils._context.library_version import LibraryVersion
from utils import context
from utils._context.containers import (
    create_network,
    DockerSSIContainer,
    APMTestAgentContainer,
    TestedContainer,
)
from utils.tools import logger

from .core import Scenario
from utils.virtual_machine.vm_logger import vm_logger
from utils.docker_ssi.docker_ssi_matrix_utils import resolve_runtime_version


class DockerSSIScenario(Scenario):
    """Scenario test the ssi installer on a docker environment and runs APM test agent """

    def __init__(self, name, doc, github_workflow=None, scenario_groups=None) -> None:
        super().__init__(name, doc=doc, github_workflow=github_workflow, scenario_groups=scenario_groups)

        self._weblog_injection = DockerSSIContainer(host_log_folder=self.host_log_folder)

        self._required_containers: list(TestedContainer) = []
        self._required_containers.append(APMTestAgentContainer(host_log_folder=self.host_log_folder))
        self._required_containers.append(self._weblog_injection)
        self.weblog_url = "http://localhost:18080"
        self._tested_components = {}

    def configure(self, config):
        assert "TEST_LIBRARY" in os.environ, "TEST_LIBRARY must be set: java,python,nodejs,dotnet,ruby"

        self._weblog = config.option.ssi_weblog
        self._library = config.option.ssi_library
        self._base_image = config.option.ssi_base_image
        self._arch = config.option.ssi_arch
        self._runtime = config.option.ssi_runtime
        self._push_base_images = config.option.ssi_push_base_images
        self._force_build = config.option.ssi_force_build
        self._libray_version = LibraryVersion(os.getenv(self._library), "")
        self._installed_runtime = None

        logger.stdout(
            f"Configuring scenario with: Weblog: [{self._weblog}] Library: [{self._library}] Base Image: [{self._base_image}] Arch: [{self._arch}] Runtime: [{self._runtime}]"
        )

        # Build the docker images to generate the weblog image
        self.ssi_image_builder = DockerSSIImageBuilder(
            self._weblog,
            self._base_image,
            self._library,
            self._arch,
            self._runtime,
            self._push_base_images,
            self._force_build,
        )
        self.ssi_image_builder.configure()
        self.ssi_image_builder.build_weblog()

        # Extract version of the components that we are testing.
        json_tested_component = self.ssi_image_builder.tested_components()
        self.fill_context(json_tested_component)

        for container in self._required_containers:
            container.configure(self.replay)

    # def session_start(self):
    #    """called at the very begning of the process"""
    #    super().session_start()
    #    container_weblog_url = self._weblog_injection.get_env("WEBLOG_URL")
    #    if container_weblog_url:
    #        self.weblog_url = container_weblog_url
    #    logger.info(f"Weblog URL: {self.weblog_url}")

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
        self.ssi_image_builder.push_base_image()

    def fill_context(self, json_tested_components):
        logger.stdout("\nInstalled components:\n")

        for key in json_tested_components:
            if key == "weblog_url" and json_tested_components[key]:
                self.weblog_url = json_tested_components[key].lstrip(" ")
                continue
            if key == "runtime_version" and json_tested_components[key]:
                self._installed_runtime = json_tested_components[key].lstrip(" ")
            if key.startswith("datadog-apm-library-") and json_tested_components[key]:
                library_version_number = json_tested_components[key].lstrip(" ")
                self._libray_version = LibraryVersion(self._library, library_version_number)
            self._tested_components[key] = json_tested_components[key].lstrip(" ")
            logger.stdout(f"{key}: {self._tested_components[key]}")

    @property
    def library(self):
        return self._libray_version

    @property
    def installed_runtime(self):
        return self._installed_runtime

    @property
    def components(self):
        return self._tested_components


class DockerSSIImageBuilder:
    """ Manages the docker image building for the SSI scenario """

    def __init__(self, weblog, base_image, library, arch, runtime, push_base_images, force_build) -> None:
        self._weblog = weblog
        self._base_image = base_image
        self._library = library
        self._arch = arch
        self._runtime = runtime
        self._push_base_images = push_base_images
        self._force_build = force_build
        self.docker_client = self._get_docker_client()
        self.should_push_base_images = False
        self._weblog_docker_image = None

    def configure(self):
        self.docker_tag = self.get_base_docker_tag()
        self._docker_registry_tag = f"ghcr.io/datadog/system-tests/ssi_installer_{self.docker_tag}:latest"
        self.ssi_installer_docker_tag = f"ssi_installer_{self.docker_tag}"
        self.ssi_all_docker_tag = f"ssi_all_{self.docker_tag}"

    def build_weblog(self):
        if not self.exist_base_image() or self._push_base_images or self._force_build:
            # Build the base image
            self.build_lang_deps_image()
            self.build_ssi_installer_image()
            self.should_push_base_images = True if not self.exist_base_image() or self._push_base_images else False
        self.build_weblog_image(
            self.ssi_installer_docker_tag if self.should_push_base_images else self._docker_registry_tag
        )

    def exist_base_image(self):
        """ Check if the base image is available in the docker registry """
        try:
            self.docker_client.images.pull(self._docker_registry_tag)
            logger.info("Base image found on the registry")
            return True
        except Exception as e:
            logger.info(f"Base image not found on the registry: ssi_{self.docker_tag}")
            return False

    def push_base_image(self):
        """ Push the base image to the docker registry. Base image contains: lang (if it's needed) and ssi installer (only with the installer, without ssi autoinject )"""
        if self.should_push_base_images:
            logger.stdout(f"Pushing base image to the registry: {self._docker_registry_tag}")
            docker.APIClient().tag(self.ssi_installer_docker_tag, self._docker_registry_tag)
            push_logs = self.docker_client.images.push(self._docker_registry_tag)
            self.print_docker_push_logs(self._docker_registry_tag, push_logs)

    def get_base_docker_tag(self):
        """ Resolves and format the docker tag for the base image """
        runtime = resolve_runtime_version(self._library, self._runtime) if self._runtime else ""
        return (
            f"{self._base_image}_{runtime}_{self._arch}".replace(".", "_")
            .replace("-", "_")
            .replace(":", "_")
            .replace("/", "_")
            .lower()
        )

    def build_lang_deps_image(self):
        """ Build the lang image. Install the language runtime on the base image. 
        We also install some linux deps for the ssi installer """

        # If there is not runtime installation requirement, we install only the linux deps
        # Base lang contains the scrit to install the runtime and the script to install dependencies
        dockerfile_template = "base/base_lang.Dockerfile" if self._runtime else "base/base_deps.Dockerfile"
        try:
            logger.stdout(
                f"Building docker lang and/or deps image from base image [{self._base_image}]. Tag: [{self.docker_tag}]"
            )

            _, build_logs = self.docker_client.images.build(
                path="utils/build/ssi/",
                dockerfile=dockerfile_template,
                tag=self.docker_tag,
                platform=self._arch,
                buildargs={
                    "ARCH": self._arch,
                    "DD_LANG": self._library,
                    "RUNTIME_VERSIONS": self._runtime,
                    "BASE_IMAGE": self._base_image,
                },
            )
            self.print_docker_build_logs(self.docker_tag, build_logs)
        except Exception as e:
            logger.exception(f"Failed to build docker image: {e}")
            raise e

    def build_ssi_installer_image(self):
        """ Build the ssi installer image. Install only the ssi installer on the image """
        try:
            logger.stdout(
                f"Building docker ssi installer image from base image [{self.docker_tag}]. Tag: [{self.ssi_installer_docker_tag}]"
            )
            _, build_logs = self.docker_client.images.build(
                path="utils/build/ssi/",
                dockerfile="base/base_ssi_installer.Dockerfile",
                platform=self._arch,
                tag=self.ssi_installer_docker_tag,
                buildargs={"BASE_IMAGE": self.docker_tag},
            )
            self.print_docker_build_logs(self.ssi_installer_docker_tag, build_logs)

        except Exception as e:
            logger.exception(f"Failed to build docker image: {e}")
            raise e

    def build_weblog_image(self, ssi_installer_docker_tag):
        """ Build the final weblog image. Uses base ssi installer image, install 
        the full ssi (to perform the auto inject) and build the weblog image """

        weblog_docker_tag = "weblog-injection:latest"
        logger.stdout(f"Building docker final weblog image with tag: {weblog_docker_tag}")

        logger.stdout(
            f"Installing ssi for autoinjection on [{ssi_installer_docker_tag}]. Tag: [{self.ssi_all_docker_tag}]"
        )
        try:
            # Install the ssi to run the auto instrumentation
            _, build_logs = self.docker_client.images.build(
                path="utils/build/ssi/",
                dockerfile=f"base/base_ssi.Dockerfile",
                platform=self._arch,
                tag=self.ssi_all_docker_tag,
                buildargs={"DD_LANG": self._library, "BASE_IMAGE": ssi_installer_docker_tag},
            )
            self.print_docker_build_logs(self.ssi_all_docker_tag, build_logs)
            logger.stdout(
                f"Building docker final weblog image from base [{self.ssi_all_docker_tag}]. Tag: {weblog_docker_tag}"
            )
            # Build the weblog image
            self._weblog_docker_image, build_logs = self.docker_client.images.build(
                path=".",
                dockerfile=f"utils/build/ssi/{self._library}/{self._weblog}.Dockerfile",
                platform=self._arch,
                tag=weblog_docker_tag,
                buildargs={"BASE_IMAGE": self.ssi_all_docker_tag},
            )
            self.print_docker_build_logs(weblog_docker_tag, build_logs)
            logger.info(f"Weblog build done!")
        except BuildError as e:
            logger.exception(f"Failed to build docker image: {e}")
            self.print_docker_build_logs("Error building weblog", e.build_log)
            raise e

    def tested_components(self):
        """ Extract weblog versions of lang runtime, agent, installer, tracer. 
        Also extracts the weblog url env variable
        Return json with the data"""
        logger.info(f"Weblog extract tested components")
        result = self.docker_client.containers.run(
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

    @lru_cache
    def _get_docker_client(self):
        """ Get the docker client and print exceptions if it fails """
        try:
            return docker.DockerClient.from_env()
        except DockerException as e:
            # Failed to start the default Docker client... Let's see if we have
            # better luck with docker contexts...
            try:
                ctx_name = subprocess.run(
                    ["docker", "context", "show"], capture_output=True, check=True, text=True
                ).stdout.strip()
                endpoint = subprocess.run(
                    ["docker", "context", "inspect", ctx_name, "-f", "{{ .Endpoints.docker.Host }}"],
                    capture_output=True,
                    check=True,
                    text=True,
                ).stdout.strip()
                return docker.DockerClient(base_url=endpoint)
            except:
                pass

            raise e
