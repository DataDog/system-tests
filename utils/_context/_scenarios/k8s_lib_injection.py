import os

from docker.models.networks import Network

from utils._context.library_version import LibraryVersion, Version
from utils.k8s_lib_injection.k8s_kind_cluster import (
    create_cluster,
    delete_cluster,
    default_kind_cluster,
    create_spak_service_account,
)
from utils.k8s_lib_injection.k8s_datadog_kubernetes import K8sDatadog
from utils.k8s_lib_injection.k8s_weblog import K8sWeblog
from utils.k8s_lib_injection.k8s_wrapper import K8sWrapper
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
from .core import Scenario, ScenarioGroup


class K8sScenario(Scenario):
    """Scenario that tests kubernetes lib injection"""

    def __init__(
        self,
        name,
        doc,
        use_uds=False,
        with_admission_controller=True,
        weblog_env={},
        dd_cluster_feature={},
    ) -> None:
        super().__init__(
            name,
            doc=doc,
            github_workflow="libinjection",
            scenario_groups=[ScenarioGroup.ALL, ScenarioGroup.LIB_INJECTION],
        )
        self.use_uds = use_uds
        self.with_admission_controller = with_admission_controller
        self.weblog_env = weblog_env
        self.dd_cluster_feature = dd_cluster_feature
        self._tested_components = {}

    def configure(self, config):
        self.k8s_weblog = config.option.k8s_weblog
        self.k8s_weblog_img = config.option.k8s_weblog_img
        self._library = LibraryVersion(
            config.option.k8s_library, self.extract_library_version(config.option.k8s_lib_init_img)
        )
        self.k8s_cluster_version = config.option.k8s_cluster_version
        self.k8s_lib_init_img = config.option.k8s_lib_init_img
        self._tested_components["cluster_agent"] = self.k8s_cluster_version

        self.print_context()

        # Prepare kubernetes datadog and the weblog handler
        self.test_agent = K8sDatadog(self.host_log_folder, "")
        self.test_agent.configure(
            default_kind_cluster,
            K8sWrapper(default_kind_cluster),
            dd_cluster_feature=self.dd_cluster_feature,
            dd_cluster_uds=self.use_uds,
            k8s_cluster_version=self.k8s_cluster_version,
        )
        self.test_weblog = K8sWeblog(
            self.k8s_weblog_img, self.library.library, self.k8s_lib_init_img, self.host_log_folder, ""
        )
        self.test_weblog.configure(
            default_kind_cluster,
            K8sWrapper(default_kind_cluster),
            weblog_env=self.weblog_env,
            dd_cluster_uds=self.use_uds,
        )

    def print_context(self):
        logger.stdout(f"K8s Weblog: {self.k8s_weblog}")
        logger.stdout(f"K8s Weblog image: {self.k8s_weblog_img}")
        logger.stdout(f"Library: {self._library}")
        logger.stdout(f"K8s Cluster version: {self.k8s_cluster_version}")
        logger.stdout(f"K8s Lib init image: {self.k8s_lib_init_img}")

    def extract_library_version(self, library_init_image):
        """Pull the library init image and extract the version of the library"""
        logger.info("Get lib init tracer version")
        lib_init_docker_image = get_docker_client().images.pull(library_init_image)
        result = get_docker_client().containers.run(
            image=lib_init_docker_image, command=f"cat /datadog-init/package/version", remove=True
        )
        version = result.decode("utf-8")
        logger.info(f"Library version: {version}")
        return version

    def get_warmups(self):
        warmups = super().get_warmups()
        warmups.append(lambda: logger.terminal.write_sep("=", "Starting Kubernetes Kind Cluster", bold=True))
        warmups.append(create_cluster)
        warmups.append(self.test_agent.deploy_test_agent)
        if self.with_admission_controller:
            warmups.append(self.test_agent.deploy_datadog_cluster_agent)
            warmups.append(self.test_weblog.install_weblog_pod_with_admission_controller)
        else:
            warmups.append(self.test_weblog.install_weblog_pod_without_admission_controller)
        return warmups

    def pytest_sessionfinish(self, session, exitstatus):  # noqa: ARG002
        self.close_targets()

    def close_targets(self):
        logger.info("K8sInstance Exporting debug info")
        self.test_agent.export_debug_info()
        self.test_weblog.export_debug_info()
        logger.info("Destroying cluster")
        delete_cluster()

    @property
    def library(self):
        return self._library

    @property
    def weblog_variant(self):
        return self.k8s_weblog

    @property
    def k8s_cluster_agent_version(self):
        # return (
        #    self.k8s_cluster_version
        #    if self.k8s_cluster_version and self.k8s_cluster_agent_version.startswith("v")
        #    else ("v" + self.k8s_cluster_version)
        # )
        return Version(self.k8s_cluster_version)

    @property
    def components(self):
        return self._tested_components


class K8sSparkScenario(K8sScenario):
    """Scenario that tests kubernetes lib injection for Spark applications"""

    def __init__(
        self,
        name,
        doc,
        use_uds=False,
        with_admission_controller=True,
        weblog_env={},
        dd_cluster_feature={},
    ) -> None:
        super().__init__(
            name,
            doc=doc,
            use_uds=use_uds,
            with_admission_controller=with_admission_controller,
            weblog_env=weblog_env,
            dd_cluster_feature=dd_cluster_feature,
        )

    def configure(self, config):
        super().configure(config)
        self.weblog_env["LIB_INIT_IMAGE"] = self.k8s_lib_init_img
        self.test_agent = K8sDatadog(self.host_log_folder, "")
        self.test_agent.configure(
            default_kind_cluster,
            K8sWrapper(default_kind_cluster),
            dd_cluster_feature=self.dd_cluster_feature,
            dd_cluster_uds=self.use_uds,
            k8s_cluster_version=self.k8s_cluster_version,
        )
        self.test_weblog = K8sWeblog(
            self.k8s_weblog_img, self.library.library, self.k8s_lib_init_img, self.host_log_folder, ""
        )
        self.test_weblog.configure(
            default_kind_cluster,
            K8sWrapper(default_kind_cluster),
            weblog_env=self.weblog_env,
            dd_cluster_uds=self.use_uds,
            service_account="spark",
        )

    def get_warmups(self):
        warmups = []
        warmups.append(lambda: logger.terminal.write_sep("=", "Starting Kubernetes Kind Cluster", bold=True))
        warmups.append(create_cluster)
        warmups.append(create_spak_service_account)
        warmups.append(self.test_agent.deploy_test_agent)
        warmups.append(self.test_agent.deploy_datadog_cluster_agent)
        warmups.append(self.test_weblog.install_weblog_pod_with_admission_controller)

        return warmups


class KubernetesScenario(Scenario):
    """Scenario that tests kubernetes lib injection"""

    def __init__(self, name, doc, github_workflow=None, scenario_groups=None, api_key=None, app_key=None) -> None:
        super().__init__(name, doc=doc, github_workflow=github_workflow, scenario_groups=scenario_groups)
        self.api_key = api_key
        self.app_key = app_key

    def configure(self, config):  # noqa: ARG002
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

    def configure(self, config):  # noqa: ARG002
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

    def _start_containers(self):
        for container in self._required_containers:
            container.start(self._network)

    def get_warmups(self):
        warmups = super().get_warmups()

        warmups.append(self._create_network)
        warmups.append(create_inject_volume)
        warmups.append(self._start_containers)

        return warmups

    def pytest_sessionfinish(self, session, exitstatus):  # noqa: ARG002
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

    @property
    def weblog_variant(self):
        return self._weblog_variant
