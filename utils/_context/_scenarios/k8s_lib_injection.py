import os

from docker.models.networks import Network

from utils._context.library_version import LibraryVersion, Version

from utils.k8s_lib_injection.k8s_datadog_kubernetes import K8sDatadog
from utils.k8s_lib_injection.k8s_weblog import K8sWeblog
from utils.k8s_lib_injection.k8s_cluster_provider import K8sProviderFactory
from utils._context.containers import (
    create_network,
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
        weblog_env={},
        dd_cluster_feature={},
        with_datadog_operator=False,
    ) -> None:
        super().__init__(
            name,
            doc=doc,
            github_workflow="libinjection",
            scenario_groups=[ScenarioGroup.ALL, ScenarioGroup.LIB_INJECTION],
        )
        self.use_uds = use_uds
        self.with_datadog_operator = with_datadog_operator
        self.weblog_env = weblog_env
        self.dd_cluster_feature = dd_cluster_feature

    def configure(self, config):
        # If we are using the datadog operator, we don't need to deploy the test agent
        # But we'll use the real agent deployed automatically by the operator
        # We'll use the real backend, we need the real api key and app key
        if self.with_datadog_operator:
            assert os.getenv("DD_API_KEY_ONBOARDING") is not None, "DD_API_KEY_ONBOARDING is not set"
            assert os.getenv("DD_APP_KEY_ONBOARDING") is not None, "DD_APP_KEY_ONBOARDING is not set"
            self._api_key = os.getenv("DD_API_KEY_ONBOARDING")
            self._app_key = os.getenv("DD_APP_KEY_ONBOARDING")
        # These are the tested components: dd_cluser_agent_version, weblog image, library_init_version, injector version
        self.k8s_weblog = config.option.k8s_weblog
        self.k8s_weblog_img = config.option.k8s_weblog_img
        # By default we are going to use kind cluster provider
        self.k8s_provider_name = config.option.k8s_provider if config.option.k8s_provider else "kind"

        # Get Lib init version
        self._library = LibraryVersion(
            config.option.k8s_library, extract_library_version(config.option.k8s_lib_init_img)
        )
        self.k8s_lib_init_img = config.option.k8s_lib_init_img
        self.components["library"] = self._library.version

        # Cluster agent version
        if config.option.k8s_cluster_version is not None and config.option.k8s_cluster_img is not None:
            raise ValueError("You mustn't set both k8s_cluster_version and k8s_cluster_img")
        if config.option.k8s_cluster_version is None and config.option.k8s_cluster_img is None:
            raise ValueError("You must set either k8s_cluster_version or k8s_cluster_img")
        if config.option.k8s_cluster_version is not None:
            logger.stdout("WARNING: The k8s_cluster_version is going to be deprecated, use k8s_cluster_img instead")
            self.k8s_cluster_img = None
            self.k8s_cluster_version = config.option.k8s_cluster_version
            self.components["cluster_agent"] = self.k8s_cluster_version
        else:
            self.k8s_cluster_img = config.option.k8s_cluster_img
            self.k8s_cluster_version = extract_cluster_agent_version(self.k8s_cluster_img)
            self.components["cluster_agent"] = self.k8s_cluster_version

        # Injector image version
        self.k8s_injector_img = (
            config.option.k8s_injector_img if config.option.k8s_injector_img else "gcr.io/datadoghq/apm-inject:latest"
        )
        self._datadog_apm_inject_version = f"v{extract_injector_version(self.k8s_injector_img)}"
        self.components["datadog-apm-inject"] = self._datadog_apm_inject_version

        # Configure the K8s cluster provider
        self.k8s_cluster_provider = K8sProviderFactory().get_provider(self.k8s_provider_name)
        self.k8s_cluster_provider.configure()
        self.print_context()

        # is it on sleep mode?
        self._sleep_mode = config.option.sleep

        # Prepare kubernetes datadog (manages the dd_cluster_agent and test_agent or the operator)
        self.k8s_datadog = K8sDatadog(self.host_log_folder)
        self.k8s_datadog.configure(
            self.k8s_cluster_provider.get_cluster_info(),
            dd_cluster_feature=self.dd_cluster_feature,
            dd_cluster_uds=self.use_uds,
            dd_cluster_version=self.k8s_cluster_version,
            dd_cluster_img=self.k8s_cluster_img,
            api_key=self._api_key if self.with_datadog_operator else None,
            app_key=self._app_key if self.with_datadog_operator else None,
        )
        # Weblog handler (the lib init and injector imgs are set in weblog/pod as annotations)
        self.test_weblog = K8sWeblog(
            self.k8s_weblog_img,
            self.library.library,
            self.k8s_lib_init_img,
            self.k8s_injector_img,
            self.host_log_folder,
        )
        self.test_weblog.configure(
            self.k8s_cluster_provider.get_cluster_info(), weblog_env=self.weblog_env, dd_cluster_uds=self.use_uds
        )

    def print_context(self):
        logger.stdout(f".:: K8s Lib injection test components ::.")
        logger.stdout(f"Weblog: {self.k8s_weblog}")
        logger.stdout(f"Weblog image: {self.k8s_weblog_img}")
        logger.stdout(f"Library: {self._library}")
        logger.stdout(f"Lib init image: {self.k8s_lib_init_img}")
        logger.stdout(f"Cluster agent version: {self.k8s_cluster_version}")
        logger.stdout(f"Cluster agent image: {self.k8s_cluster_img}")
        logger.stdout(f"Injector version: {self._datadog_apm_inject_version}")
        logger.stdout(f"Injector image: {self.k8s_injector_img}")

    def get_warmups(self):
        warmups = super().get_warmups()
        warmups.append(lambda: logger.terminal.write_sep("=", "Starting Kubernetes Kind Cluster", bold=True))
        warmups.append(self.k8s_cluster_provider.ensure_cluster)

        if not self.with_datadog_operator:
            warmups.append(self.k8s_datadog.deploy_test_agent)
            warmups.append(self.k8s_datadog.deploy_datadog_cluster_agent)
            warmups.append(self.test_weblog.install_weblog_pod)
        else:
            warmups.append(self.k8s_datadog.deploy_datadog_operator)
            warmups.append(self.test_weblog.install_weblog_pod)

        return warmups

    def pytest_sessionfinish(self, session, exitstatus):  # noqa: ARG002
        self.close_targets()

    def close_targets(self):
        if self._sleep_mode:
            logger.info("Sleep mode enabled, not extracting debug cluster")
            self.k8s_cluster_provider.destroy_cluster()
            return
        logger.info("K8sInstance Exporting debug info")
        self.k8s_datadog.export_debug_info(namespace="default")
        self.test_weblog.export_debug_info(namespace="default")
        logger.info("Destroying cluster")
        self.k8s_cluster_provider.destroy_cluster()

    @property
    def library(self):
        return self._library

    @property
    def weblog_variant(self):
        return self.k8s_weblog

    @property
    def k8s_cluster_agent_version(self):
        return Version(self.k8s_cluster_version)

    @property
    def dd_apm_inject_version(self):
        return self._datadog_apm_inject_version


class K8sManualInstrumentationScenario(Scenario):
    """Scenario that applied the auto instrumentation manually
    Without using the cluster agent or the operator. We simply add volume mounts to the pods
    with the context of the lib init image, then we inject the env variables to the weblog to
    perform the auto injection
    """

    def __init__(self, name, doc, use_uds=False, weblog_env={}) -> None:
        super().__init__(
            name,
            doc=doc,
            github_workflow="libinjection",
            scenario_groups=[ScenarioGroup.ALL, ScenarioGroup.LIB_INJECTION],
        )
        self.use_uds = use_uds
        self.weblog_env = weblog_env

    def configure(self, config):
        self.k8s_weblog = config.option.k8s_weblog
        self.k8s_weblog_img = config.option.k8s_weblog_img
        # By default we are going to use kind cluster provider
        self.k8s_provider_name = config.option.k8s_provider if config.option.k8s_provider else "kind"

        # Get Lib init version
        self._library = LibraryVersion(
            config.option.k8s_library, extract_library_version(config.option.k8s_lib_init_img)
        )
        self.k8s_lib_init_img = config.option.k8s_lib_init_img
        self.components["library"] = self._library

        # Configure the K8s cluster provider
        self.k8s_cluster_provider = K8sProviderFactory().get_provider(self.k8s_provider_name)
        self.k8s_cluster_provider.configure()
        self.print_context()

        # is it on sleep mode?
        self._sleep_mode = config.option.sleep

        # Prepare kubernetes datadog (manages the dd_cluster_agent and test_agent or the operator)
        self.k8s_datadog = K8sDatadog(self.host_log_folder)
        self.k8s_datadog.configure(self.k8s_cluster_provider.get_cluster_info())
        # Weblog handler
        self.test_weblog = K8sWeblog(
            self.k8s_weblog_img,
            self.library.library,
            self.k8s_lib_init_img,
            None,
            self.host_log_folder,
        )
        self.test_weblog.configure(
            self.k8s_cluster_provider.get_cluster_info(), weblog_env=self.weblog_env, dd_cluster_uds=self.use_uds
        )

    def print_context(self):
        logger.stdout(f"K8s Weblog: {self.k8s_weblog}")
        logger.stdout(f"K8s Weblog image: {self.k8s_weblog_img}")
        logger.stdout(f"Library: {self._library}")
        logger.stdout(f"K8s Lib init image: {self.k8s_lib_init_img}")

    def get_warmups(self):
        warmups = []
        warmups.append(lambda: logger.terminal.write_sep("=", "Starting Kubernetes Kind Cluster", bold=True))
        warmups.append(self.k8s_cluster_provider.ensure_cluster)
        warmups.append(self.k8s_datadog.deploy_test_agent)
        warmups.append(self.test_weblog.install_weblog_pod_with_manual_inject)
        return warmups

    def pytest_sessionfinish(self, session, exitstatus):  # noqa: ARG002
        self.close_targets()

    def close_targets(self):
        if not self._sleep_mode:
            self.test_weblog.export_debug_info(namespace="default")
        self.k8s_cluster_provider.destroy_cluster()

    @property
    def library(self):
        return self._library

    @property
    def weblog_variant(self):
        return self.k8s_weblog


class K8sSparkScenario(K8sScenario):
    """Scenario that tests kubernetes lib injection for Spark applications"""

    def __init__(
        self,
        name,
        doc,
        use_uds=False,
        weblog_env={},
        dd_cluster_feature={},
    ) -> None:
        super().__init__(
            name,
            doc=doc,
            use_uds=use_uds,
            weblog_env=weblog_env,
            dd_cluster_feature=dd_cluster_feature,
        )

    def configure(self, config):
        super().configure(config)
        self.weblog_env["LIB_INIT_IMAGE"] = self.k8s_lib_init_img

        self.k8s_datadog = K8sDatadog(self.host_log_folder)
        self.k8s_datadog.configure(
            self.k8s_cluster_provider.get_cluster_info(),
            dd_cluster_feature=self.dd_cluster_feature,
            dd_cluster_uds=self.use_uds,
            dd_cluster_version=self.k8s_cluster_version,
            dd_cluster_img=self.k8s_cluster_img,
        )

        self.test_weblog = K8sWeblog(
            self.k8s_weblog_img,
            self.library.library,
            self.k8s_lib_init_img,
            self.k8s_injector_img,
            self.host_log_folder,
        )
        self.test_weblog.configure(
            self.k8s_cluster_provider.get_cluster_info(),
            weblog_env=self.weblog_env,
            dd_cluster_uds=self.use_uds,
            service_account="spark",
        )

    def get_warmups(self):
        warmups = []
        warmups.append(lambda: logger.terminal.write_sep("=", "Starting Kubernetes Kind Cluster", bold=True))
        warmups.append(self.k8s_cluster_provider.ensure_cluster)
        warmups.append(self.k8s_cluster_provider.create_spak_service_account)
        warmups.append(self.k8s_datadog.deploy_test_agent)
        warmups.append(self.k8s_datadog.deploy_datadog_cluster_agent)
        warmups.append(self.test_weblog.install_weblog_pod)

        return warmups


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


def extract_library_version(library_init_image):
    """Pull the library init image and extract the version of the library"""
    logger.info("Get lib init tracer version")
    try:
        lib_init_docker_image = get_docker_client().images.pull(library_init_image)
        result = get_docker_client().containers.run(
            image=lib_init_docker_image, command=f"cat /datadog-init/package/version", remove=True
        )
        version = result.decode("utf-8")
        logger.info(f"Library version: {version}")
        return version
    except Exception as e:
        logger.error(f"The library init image failed to pull is: {library_init_image}")
        raise ValueError(f"Failed to pull and extract library version: {e}")


def extract_injector_version(injector_image):
    """Pull the injector image and extract the version of the injector"""
    logger.info("Get injector version")
    try:
        injector_docker_image = get_docker_client().images.pull(injector_image)
        # TODO review this. The version is a folder name under /opt/datadog-packages/datadog-apm-inject/
        result = get_docker_client().containers.run(
            image=injector_docker_image, command="ls /opt/datadog-packages/datadog-apm-inject/", remove=True
        )
        version = result.decode("utf-8").split("\n")[0]

        logger.info(f"Injector version: {version}")
        return version
    except Exception as e:
        logger.error(f"The failed injector image failed to pull is: {injector_image}")
        raise ValueError(f"Failed to pull and extract injector version: {e}")


def extract_cluster_agent_version(cluster_image):
    """Pull the datadog cluster image  and extract the version from labels"""
    logger.info("Get cluster agent version")
    try:
        cluster_docker_image = get_docker_client().images.pull(cluster_image)
        version = cluster_docker_image.labels["org.opencontainers.image.version"]
        logger.info(f"Cluster agent version: {version}")
        return version
    except Exception as e:
        logger.error(f"The cluster agent images tried to pull is: {cluster_image}")
        raise ValueError(f"Failed to pull and extract cluster agent version: {e}")
