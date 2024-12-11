from functools import partial
import os

from docker.models.networks import Network

from utils._context.library_version import LibraryVersion, Version

from utils._context.containers import (
    create_network,
    # SqlDbTestedContainer,
    APMTestAgentContainer,
    WeblogInjectionInitContainer,
    MountInjectionVolume,
    create_inject_volume,
    TestedContainer,
    _get_client as get_docker_client,
)

from utils.tools import logger

from .core import Scenario


class KubernetesScenario(Scenario):
    """Scenario that tests kubernetes lib injection"""

    def __init__(self, name, doc, github_workflow=None, scenario_groups=None, api_key=None, app_key=None) -> None:
        super().__init__(name, doc=doc, github_workflow=github_workflow, scenario_groups=scenario_groups)
        self.api_key = api_key
        self.app_key = app_key

    def configure(self, config):
        # TODO get variables from config like --k8s-lib-init-image (Warning! impacts on the tracers pipelines!)
        assert "TEST_LIBRARY" in os.environ, "TEST_LIBRARY is not set"
        assert "WEBLOG_VARIANT" in os.environ, "WEBLOG_VARIANT is not set"
        assert "LIB_INIT_IMAGE" in os.environ, "LIB_INIT_IMAGE is not set. The init image to be tested is not set"
        assert (
            "LIBRARY_INJECTION_TEST_APP_IMAGE" in os.environ
        ), "LIBRARY_INJECTION_TEST_APP_IMAGE is not set. The test app image to be tested is not set"
        self._cluster_agent_version = Version(os.getenv("CLUSTER_AGENT_VERSION", "7.56.2"))
        self._tested_components = {}
        self._weblog_variant = os.getenv("WEBLOG_VARIANT")
        self._weblog_variant_image = os.getenv("LIBRARY_INJECTION_TEST_APP_IMAGE")
        self._library_init_image = os.getenv("LIB_INIT_IMAGE")
        if self.api_key is None or self.app_key is None:
            self.api_key = os.getenv("DD_API_KEY")
            self.app_key = os.getenv("DD_APP_KEY")
        # Get library version from lib init image
        library_version = self.get_library_version()
        self._library = LibraryVersion(os.getenv("TEST_LIBRARY"), library_version)
        # Set testing dependencies
        self.fill_context()
        logger.stdout("K8s Lib Injection environment:")
        logger.stdout(f"Library: {self._library}")
        logger.stdout(f"Weblog variant: {self._weblog_variant}")
        logger.stdout(f"Weblog variant image: {self._weblog_variant_image}")
        logger.stdout(f"Library init image: {self._library_init_image}")
        logger.stdout(f"K8s DD Cluster Agent: {self._cluster_agent_version}")
        logger.info("K8s Lib Injection environment configured")

    def get_library_version(self):
        """Extract library version from the init image."""

        logger.info("Get lib init tracer version")
        lib_init_docker_image = get_docker_client().images.pull(self._library_init_image)
        result = get_docker_client().containers.run(
            image=lib_init_docker_image, command=f"cat /datadog-init/package/version", remove=True
        )
        version = result.decode("utf-8")
        logger.info(f"Library version: {version}")
        return version

    def fill_context(self):
        self._tested_components["cluster_agent"] = self._cluster_agent_version
        self._tested_components["library"] = self._library
        self._tested_components["lib_init_image"] = self._library_init_image

    @property
    def library(self):
        return self._library

    @property
    def weblog_variant(self):
        return self._weblog_variant

    @property
    def k8s_cluster_agent_version(self):
        return self._cluster_agent_version

    @property
    def components(self):
        return self._tested_components


class WeblogInjectionScenario(Scenario):
    """Scenario that runs APM test agent"""

    _network: Network = None

    def __init__(self, name, doc, github_workflow=None, scenario_groups=None) -> None:
        super().__init__(name, doc=doc, github_workflow=github_workflow, scenario_groups=scenario_groups)

        self._mount_injection_volume = MountInjectionVolume(
            host_log_folder=self.host_log_folder, name="volume-injector"
        )
        self._weblog_injection = WeblogInjectionInitContainer(host_log_folder=self.host_log_folder)

        self._required_containers: list[TestedContainer] = []
        self._required_containers.append(self._mount_injection_volume)
        self._required_containers.append(APMTestAgentContainer(host_log_folder=self.host_log_folder))
        self._required_containers.append(self._weblog_injection)

    def configure(self, config):
        assert "TEST_LIBRARY" in os.environ, "TEST_LIBRARY must be set: java,python,nodejs,dotnet,ruby"
        self._library = LibraryVersion(os.getenv("TEST_LIBRARY"), "0.0")

        assert "LIB_INIT_IMAGE" in os.environ, "LIB_INIT_IMAGE must be set"
        self._lib_init_image = os.getenv("LIB_INIT_IMAGE")
        self._weblog_variant = os.getenv("WEBLOG_VARIANT", "")
        self._mount_injection_volume._lib_init_image(self._lib_init_image)
        self._weblog_injection.set_environment_for_library(self.library)

        for container in self._required_containers:
            container.configure(self.replay)

    def _create_network(self):
        self._network = create_network()

    def get_warmups(self):
        warmups = super().get_warmups()

        warmups.append(create_network)
        warmups.append(create_inject_volume)
        for container in self._required_containers:
            warmups.append(partial(container.start, self._network))

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
        return self._library

    @property
    def lib_init_image(self):
        return self._lib_init_image

    @property
    def weblog_variant(self):
        return self._weblog_variant
