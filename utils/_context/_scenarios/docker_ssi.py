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

        logger.stdout(
            f"Configuring scenario with: Weblog: [{self._weblog}] Library: [{self._library}] Base Image: [{self._base_image}] Arch: [{self._arch}] Runtime: [{self._runtime}]"
        )
        ssi_image_builder = DockerSSIImageBuilder(
            self._weblog, self._base_image, self._library, self._arch, self._runtime
        )
        docker_tag = ssi_image_builder.build_lang_image()
        ssi_docker_tag = ssi_image_builder.build_ssi_image(docker_tag)
        ssi_image_builder.build_weblog_image(ssi_docker_tag)
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

    @property
    def library(self):
        return LibraryVersion("java", "0.0")


class DockerSSIImageBuilder:
    """ Manages the docker image building for the SSI scenario """

    def __init__(self, weblog, base_image, library, arch, runtime):
        self._weblog = weblog
        self._base_image = base_image
        self._library = library
        self._arch = arch
        self._runtime = runtime
        self.docker_client = self._get_docker_client()

    def build_lang_image(self):

        docker_tag = (
            f"{self._weblog}_{self._runtime}_{self._arch}".replace(".", "_")
            .replace("-", "_")
            .replace(":", "_")
            .replace("/", "_")
        )
        try:
            logger.stdout(f"Building docker lang image with tag (install lang into base image): {docker_tag}")

            _, build_logs = self.docker_client.images.build(
                path="utils/build/ssi/",
                dockerfile="base/base_lang.Dockerfile",
                tag=docker_tag,
                platform=self._arch,
                buildargs={
                    "ARCH": self._arch,
                    "LANG": self._library,
                    "RUNTIME_VERSIONS": self._runtime,
                    "BASE_IMAGE": self._base_image,
                },
            )
            self.print_docker_build_logs(docker_tag, build_logs)
        except Exception as e:
            logger.exception(f"Failed to build docker image: {e}")
            raise e
        return docker_tag

    def build_ssi_image(self, docker_tag):
        logger.stdout(f"Building docker ssi image with tag (install ssi into lang image): ssi_{docker_tag}")
        ssi_docker_tag = f"ssi_{docker_tag}"
        _, build_logs = self.docker_client.images.build(
            path="utils/build/ssi/",
            dockerfile="base/base_ssi.Dockerfile",
            platform=self._arch,
            tag=ssi_docker_tag,
            buildargs={"LANG": self._library, "BASE_IMAGE": docker_tag},
        )
        self.print_docker_build_logs(ssi_docker_tag, build_logs)
        return ssi_docker_tag

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

    def build_weblog_image2(self, ssi_docker_tag):
        """ Build the final weblog image. We use the command line because we need the --build-context option """
        weblog_docker_tag = "weblog-injection:latest"
        logger.stdout(f"Building docker final weblog image with tag: {weblog_docker_tag}")

        build_weblog_cmd = f"docker buildx build -f utils/build/ssi/{self._library}/{self._weblog}.Dockerfile --build-context lib_injection=lib-injection/build/docker --platform {self._arch} --build-arg BASE_IMAGE={ssi_docker_tag} -t {weblog_docker_tag} --load utils/build/ssi/"

        try:
            output = subprocess.check_output(
                build_weblog_cmd, stderr=subprocess.STDOUT, shell=True, timeout=120, universal_newlines=True
            )
        except subprocess.CalledProcessError as exc:
            logger.info("Status : FAIL", exc.returncode, exc.output)
            self.print_docker_build_logs(weblog_docker_tag, exc.output, shell_logs=True)
        else:
            self.print_docker_build_logs(weblog_docker_tag, output, shell_logs=True)

    def print_docker_build_logs(self, image_tag, build_logs, shell_logs=False):
        scenario_name = context.scenario.name
        vm_logger(scenario_name, "docker_build").info("***************************************************************")
        vm_logger(scenario_name, "docker_build").info(f"    Building docker image with tag: {image_tag}   ")
        vm_logger(scenario_name, "docker_build").info("***************************************************************")
        if shell_logs:
            vm_logger(scenario_name, "docker_build").info(build_logs)
        else:
            for chunk in build_logs:
                if "stream" in chunk:
                    for line in chunk["stream"].splitlines():
                        vm_logger(scenario_name, "docker_build").info(line)

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
