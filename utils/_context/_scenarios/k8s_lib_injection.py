import os
from utils._context.library_version import LibraryVersion

from utils._context.containers import (
    create_network,
    # SqlDbTestedContainer,
    APMTestAgentContainer,
    WeblogInjectionInitContainer,
    MountInjectionVolume,
    create_inject_volume,
    TestedContainer,
)
from utils.tools import logger

from .core import Scenario


class KubernetesScenario(Scenario):
    """ Scenario that tests kubernetes lib injection """

    def __init__(self, name, doc, github_workflow=None, scenario_groups=None, api_key=None, app_key=None) -> None:
        super().__init__(name, doc=doc, github_workflow=github_workflow, scenario_groups=scenario_groups)
        self.api_key = api_key
        self.app_key = app_key

    def configure(self, config):
        super().configure(config)

        assert "TEST_LIBRARY" in os.environ, "TEST_LIBRARY is not set"
        assert "WEBLOG_VARIANT" in os.environ, "WEBLOG_VARIANT is not set"
        assert "LIB_INIT_IMAGE" in os.environ, "LIB_INIT_IMAGE is not set. The init image to be tested is not set"
        assert (
            "LIBRARY_INJECTION_TEST_APP_IMAGE" in os.environ
        ), "LIBRARY_INJECTION_TEST_APP_IMAGE is not set. The test app image to be tested is not set"

        self._library = LibraryVersion(os.getenv("TEST_LIBRARY"), "0.0")
        self._weblog_variant = os.getenv("WEBLOG_VARIANT")
        self._weblog_variant_image = os.getenv("LIBRARY_INJECTION_TEST_APP_IMAGE")
        self._library_init_image = os.getenv("LIB_INIT_IMAGE")
        if self.api_key is None or self.app_key is None:
            self.api_key = os.getenv("DD_API_KEY")
            self.app_key = os.getenv("DD_APP_KEY")
        logger.stdout("K8s Lib Injection environment:")
        logger.stdout(f"Library: {self._library}")
        logger.stdout(f"Weblog variant: {self._weblog_variant}")
        logger.stdout(f"Weblog variant image: {self._weblog_variant_image}")
        logger.stdout(f"Library init image: {self._library_init_image}")

        logger.info("K8s Lib Injection environment configured")

    @property
    def library(self):
        return self._library

    @property
    def weblog_variant(self):
        return self._weblog_variant


class WeblogInjectionScenario(Scenario):
    """Scenario that runs APM test agent """

    def __init__(self, name, doc, github_workflow=None, scenario_groups=None) -> None:
        super().__init__(name, doc=doc, github_workflow=github_workflow, scenario_groups=scenario_groups)

        self._mount_injection_volume = MountInjectionVolume(
            host_log_folder=self.host_log_folder, name="volume-injector"
        )
        self._weblog_injection = WeblogInjectionInitContainer(host_log_folder=self.host_log_folder)

        self._required_containers: list(TestedContainer) = []
        self._required_containers.append(self._mount_injection_volume)
        self._required_containers.append(APMTestAgentContainer(host_log_folder=self.host_log_folder))
        self._required_containers.append(self._weblog_injection)

    def configure(self, config):
        assert "TEST_LIBRARY" in os.environ, "TEST_LIBRARY must be set: java,python,nodejs,dotnet,ruby"
        self._library = LibraryVersion(os.getenv("TEST_LIBRARY"), "0.0")

        assert "LIB_INIT_IMAGE" in os.environ, "LIB_INIT_IMAGE must be set"
        self._lib_init_image = os.getenv("LIB_INIT_IMAGE")

        self._mount_injection_volume._lib_init_image(self._lib_init_image)
        self._weblog_injection.set_environment_for_library(self.library)

        super().configure(config)

        for container in self._required_containers:
            container.configure(self.replay)

    def _get_warmups(self):
        warmups = super()._get_warmups()

        warmups.append(create_network)
        warmups.append(create_inject_volume)
        for container in self._required_containers:
            warmups.append(container.start)

        return warmups

    def pytest_sessionfinish(self, session):
        self.close_targets()

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
