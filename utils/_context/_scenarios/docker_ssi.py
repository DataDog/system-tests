import os
import subprocess

import docker
from docker.errors import DockerException
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

    def configure(self, config):
        assert "TEST_LIBRARY" in os.environ, "TEST_LIBRARY must be set: java,python,nodejs,dotnet,ruby"

        self._weblog = config.option.ssi_weblog
        self._library = config.option.ssi_library
        self._base_image = config.option.ssi_base_image
        self._arch = config.option.ssi_arch
        self._runtime = config.option.ssi_runtime
        self.push_base_images = config.option.ssi_push_base_images

        logger.stdout(
            f"Configuring scenario with: Weblog: [{self._weblog}] Library: [{self._library}] Base Image: [{self._base_image}] Arch: [{self._arch}] Runtime: [{self._runtime}]"
        )
        self.ssi_image_builder = DockerSSIImageBuilder(
            self._weblog, self._base_image, self._library, self._arch, self._runtime, self.push_base_images
        )
        self.ssi_image_builder.configure()
        self.ssi_image_builder.build_weblog()
        logger.info(f"Weblog build done!")

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

    @property
    def library(self):
        return LibraryVersion("java", "0.0")


class DockerSSIImageBuilder:
    """ Manages the docker image building for the SSI scenario """

    def __init__(self, weblog, base_image, library, arch, runtime, push_base_images) -> None:
        self._weblog = weblog
        self._base_image = base_image
        self._library = library
        self._arch = arch
        self._runtime = runtime
        self._push_base_images = push_base_images
        self.docker_client = self._get_docker_client()
        self.should_push_base_images = False

    def configure(self):
        self.docker_tag = self.get_base_docker_tag()
        self._docker_registry_tag = f"ghcr.io/datadog/system-tests/ssi_{self.docker_tag}:latest"
        self.ssi_docker_tag = f"ssi_{self.docker_tag}"

    def build_weblog(self):
        if not self.exist_base_image() or self._push_base_images:
            # Build the base image
            self.build_lang_image()
            self.build_ssi_image()
            self.should_push_base_images = True
        self.build_weblog_image(self.ssi_docker_tag if self.should_push_base_images else self._docker_registry_tag)

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
        if self.should_push_base_images:
            logger.stdout(f"Pushing base image to the registry: {self._docker_registry_tag}")
            docker.APIClient().tag(self.ssi_docker_tag, self._docker_registry_tag)
            push_logs = self.docker_client.images.push(self._docker_registry_tag)
            self.print_docker_build_logs(self._docker_registry_tag, push_logs)

    def get_base_docker_tag(self):
        """ Resolves and format the docker tag for the base image """
        return (
            f"{self._base_image}_{resolve_runtime_version(self._library,self._runtime)}_{self._arch}".replace(".", "_")
            .replace("-", "_")
            .replace(":", "_")
            .replace("/", "_")
            .lower()
        )

    def build_lang_image(self):

        try:
            logger.stdout(f"Building docker lang image with tag (install lang into base image): {self.docker_tag}")

            _, build_logs = self.docker_client.images.build(
                path="utils/build/ssi/",
                dockerfile="base/base_lang.Dockerfile",
                tag=self.docker_tag,
                platform=self._arch,
                buildargs={
                    "ARCH": self._arch,
                    "LANG": self._library,
                    "RUNTIME_VERSIONS": self._runtime,
                    "BASE_IMAGE": self._base_image,
                },
            )
            self.print_docker_build_logs(self.docker_tag, build_logs)
        except Exception as e:
            logger.exception(f"Failed to build docker image: {e}")
            raise e

    def build_ssi_image(self):
        try:
            logger.stdout(f"Building docker ssi image with tag (install ssi into lang image): ssi_{self.docker_tag}")
            ssi_docker_tag = f"ssi_{self.docker_tag}"
            _, build_logs = self.docker_client.images.build(
                path="utils/build/ssi/",
                dockerfile="base/base_ssi.Dockerfile",
                platform=self._arch,
                tag=ssi_docker_tag,
                buildargs={"LANG": self._library, "BASE_IMAGE": self.docker_tag},
            )
            self.print_docker_build_logs(ssi_docker_tag, build_logs)

        except Exception as e:
            logger.exception(f"Failed to build docker image: {e}")
            raise e

    def build_weblog_image(self, ssi_docker_tag):
        """ Build the final weblog image. We use the command line because we need the --build-context option """
        weblog_docker_tag = "weblog-injection:latest"
        logger.stdout(f"Building docker final weblog image with tag: {weblog_docker_tag}")

        _, build_logs = self.docker_client.images.build(
            path=".",
            dockerfile=f"utils/build/ssi/{self._library}/{self._weblog}.Dockerfile",
            platform=self._arch,
            tag=weblog_docker_tag,
            buildargs={"BASE_IMAGE": ssi_docker_tag},
        )
        self.print_docker_build_logs(ssi_docker_tag, build_logs)

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
