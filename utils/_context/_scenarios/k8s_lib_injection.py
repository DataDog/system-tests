import os

import pytest

from utils._context.component_version import ComponentVersion, Version
from utils.k8s.k8s_components_parser import K8sComponentsParser
from utils.k8s_lib_injection.k8s_datadog_kubernetes import K8sDatadog
from utils.k8s_lib_injection.k8s_weblog import K8sWeblog
from utils.k8s_lib_injection.k8s_cluster_provider import K8sProviderFactory, K8sClusterProvider

from utils.k8s.k8s_component_image import (
    K8sComponentImage,
    extract_library_version,
    extract_injector_version,
    extract_cluster_agent_version,
)
from utils._logger import logger
from .core import Scenario, scenario_groups


class K8sScenarioWithClusterProvider:
    k8s_cluster_provider: K8sClusterProvider


class K8sScenario(Scenario, K8sScenarioWithClusterProvider):
    """Scenario that tests kubernetes lib injection"""

    def __init__(
        self,
        name,
        doc,
        use_uds=False,
        weblog_env={},
        dd_cluster_feature={},
        with_datadog_operator=False,
        with_cluster_agent=True,
        scenario_groups=(scenario_groups.all, scenario_groups.lib_injection),
    ) -> None:
        super().__init__(name, doc=doc, github_workflow="libinjection", scenario_groups=scenario_groups)
        self.use_uds = use_uds
        self.with_datadog_operator = with_datadog_operator
        self.weblog_env = weblog_env
        self.dd_cluster_feature = dd_cluster_feature
        self._configuration: dict[str, str] = {}
        self.with_cluster_agent = with_cluster_agent
        self.k8s_helm_chart_version: str | None = None
        self.k8s_helm_chart_operator_version: str | None = None
        self.k8s_cluster_img: K8sComponentImage | None = None
        self.k8s_injector_img: K8sComponentImage | None = None

    def configure(self, config: pytest.Config):
        k8s_components_parser = K8sComponentsParser()
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

        # Get component images: weblog, lib init, cluster agent, injector, helm chart, helm chart operator
        self.k8s_weblog_img = K8sComponentImage(config.option.k8s_weblog_img, lambda _: "weblog-version-1.0")

        self.k8s_lib_init_img = K8sComponentImage(
            config.option.k8s_lib_init_img
            or k8s_components_parser.get_default_component_version("lib_init", config.option.k8s_library),
            extract_library_version,
        )

        if self.with_cluster_agent:
            self.k8s_cluster_img = K8sComponentImage(
                config.option.k8s_cluster_img or k8s_components_parser.get_default_component_version("cluster_agent"),
                extract_cluster_agent_version,
            )

            self.k8s_injector_img = K8sComponentImage(
                config.option.k8s_injector_img or k8s_components_parser.get_default_component_version("injector"),
                extract_injector_version,
            )
            self.components["k8s_cluster_agent"] = ComponentVersion(
                "cluster_agent", self.k8s_cluster_img.version
            ).version
            self._configuration["cluster_agent"] = self.k8s_cluster_img.version
            self._datadog_apm_inject_version = f"v{self.k8s_injector_img.version}"
            self.components["datadog-apm-inject"] = ComponentVersion(
                "datadog-apm-inject", self._datadog_apm_inject_version
            ).version

        if self.with_datadog_operator:
            self.k8s_helm_chart_operator_version = os.getenv(
                "K8S_HELM_CHART_OPERATOR"
            ) or k8s_components_parser.get_default_component_version("helm_chart_operator")
            self.configuration["k8s_helm_chart_operator"] = self.k8s_helm_chart_operator_version

        if not self.with_datadog_operator and self.with_cluster_agent:
            self.k8s_helm_chart_version = os.getenv(
                "K8S_HELM_CHART"
            ) or k8s_components_parser.get_default_component_version("helm_chart")
            self.configuration["k8s_helm_chart"] = self.k8s_helm_chart_version

        # Get component versions: lib init, cluster agent, injector
        self._library = ComponentVersion(config.option.k8s_library, self.k8s_lib_init_img.version)
        self.components["library"] = self._library.version
        self.components[self._library.name] = self._library.version

        # Configure the K8s cluster provider
        # By default we are going to use kind cluster provider
        self.k8s_provider_name = config.option.k8s_provider if config.option.k8s_provider else "kind"
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
            dd_cluster_img=self.k8s_cluster_img.registry_url if self.k8s_cluster_img else None,
            api_key=self._api_key if self.with_datadog_operator else None,
            app_key=self._app_key if self.with_datadog_operator else None,
            helm_chart_version=self.k8s_helm_chart_version,
            helm_chart_operator_version=self.k8s_helm_chart_operator_version,
        )
        # Weblog handler (the lib init and injector imgs are set in weblog/pod as annotations)
        self.test_weblog = K8sWeblog(
            self.k8s_weblog_img.registry_url,
            self.library.name,
            self.k8s_lib_init_img.registry_url,
            self.k8s_injector_img.registry_url if self.k8s_injector_img else None,
            self.host_log_folder,
        )
        self.test_weblog.configure(
            self.k8s_cluster_provider.get_cluster_info(), weblog_env=self.weblog_env, dd_cluster_uds=self.use_uds
        )

        self.warmups.append(lambda: logger.terminal.write_sep("=", "Starting Kubernetes Cluster", bold=True))
        self.warmups.append(self.k8s_cluster_provider.ensure_cluster)

        if not self.with_datadog_operator and self.with_cluster_agent:
            self.warmups.append(self.k8s_datadog.deploy_test_agent)
            self.warmups.append(lambda: self.k8s_datadog.deploy_datadog_cluster_agent(self.host_log_folder))
            self.warmups.append(self.test_weblog.install_weblog_pod)
        elif self.with_datadog_operator:
            self.warmups.append(lambda: self.k8s_datadog.deploy_datadog_operator(self.host_log_folder))
            self.warmups.append(self.test_weblog.install_weblog_pod)
        elif not self.with_cluster_agent and not self.with_datadog_operator:
            # Scenario that applied the auto instrumentation manually
            # Without using the cluster agent or the operator. We simply add volume mounts to the pods
            # with the context of the lib init image, then we inject the env variables to the weblog to
            # perform the auto injection
            self.warmups.append(self.k8s_datadog.deploy_test_agent)
            self.warmups.append(self.test_weblog.install_weblog_pod_with_manual_inject)

    def print_context(self):
        logger.stdout(".:: K8s Lib injection test components ::.")
        logger.stdout(f"Weblog: {self.k8s_weblog}")
        logger.stdout(f"Weblog image: {self.k8s_weblog_img.registry_url}")
        logger.stdout(f"Library: {self._library}")
        logger.stdout(f"Lib init image: {self.k8s_lib_init_img.registry_url}")

        if self.with_cluster_agent and self.k8s_cluster_img and self.k8s_injector_img:
            logger.stdout(f"Cluster agent version: {self.k8s_cluster_img.version}")
            logger.stdout(f"Cluster agent image: {self.k8s_cluster_img.registry_url}")
            logger.stdout(f"Injector version: {self._datadog_apm_inject_version}")
            logger.stdout(f"Injector image: {self.k8s_injector_img.registry_url}")

        if self.with_datadog_operator and self.k8s_helm_chart_operator_version:
            logger.stdout(f"Helm chart operator version: {self.k8s_helm_chart_operator_version}")
        elif self.with_cluster_agent and self.k8s_helm_chart_version:
            logger.stdout(f"Helm chart version: {self.k8s_helm_chart_version}")

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
        if self.k8s_cluster_img:
            return Version(self.k8s_cluster_img.version)
        return None

    @property
    def dd_apm_inject_version(self):
        return self._datadog_apm_inject_version

    @property
    def configuration(self):
        return self._configuration


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

    def configure(self, config: pytest.Config):
        super().configure(config)
        self.weblog_env["LIB_INIT_IMAGE"] = self.k8s_lib_init_img.registry_url

        self.k8s_datadog = K8sDatadog(self.host_log_folder)
        self.k8s_datadog.configure(
            self.k8s_cluster_provider.get_cluster_info(),
            dd_cluster_feature=self.dd_cluster_feature,
            dd_cluster_uds=self.use_uds,
            dd_cluster_img=self.k8s_cluster_img.registry_url if self.k8s_cluster_img else None,
            helm_chart_version=self.k8s_helm_chart_version,
            helm_chart_operator_version=self.k8s_helm_chart_operator_version,
        )

        self.test_weblog = K8sWeblog(
            self.k8s_weblog_img.registry_url,
            self.library.name,
            self.k8s_lib_init_img.registry_url,
            self.k8s_injector_img.registry_url if self.k8s_injector_img else None,
            self.host_log_folder,
        )
        self.test_weblog.configure(
            self.k8s_cluster_provider.get_cluster_info(),
            weblog_env=self.weblog_env,
            dd_cluster_uds=self.use_uds,
            service_account="spark",
        )

        self.warmups = []  # re-write warmups
        self.warmups.append(lambda: logger.terminal.write_sep("=", "Starting Kubernetes Cluster", bold=True))
        self.warmups.append(self.k8s_cluster_provider.ensure_cluster)
        self.warmups.append(self.k8s_cluster_provider.create_spak_service_account)
        self.warmups.append(self.k8s_datadog.deploy_test_agent)
        self.warmups.append(lambda: self.k8s_datadog.deploy_datadog_cluster_agent(self.host_log_folder))
        self.warmups.append(self.test_weblog.install_weblog_pod)
