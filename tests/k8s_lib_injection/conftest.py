import requests
import pytest
import os
import time
from utils import context
from utils.tools import logger
import json
from utils.k8s_lib_injection.k8s_kind_cluster import ensure_cluster, destroy_cluster
from utils.k8s_lib_injection.k8s_datadog_kubernetes import K8sDatadog
from utils.k8s_lib_injection.k8s_weblog import K8sWeblog
from utils.k8s_lib_injection.k8s_wrapper import K8sWrapper
from kubernetes import config


@pytest.fixture
def test_k8s_instance(request):
    test_name = request.node.name
    library = "js" if context.scenario.library.library == "nodejs" else context.scenario.library.library

    # Create a folder with the test name
    output_folder = f"{context.scenario.host_log_folder}/{test_name}"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    k8s_instance = K8sInstance(
        library,
        context.scenario.weblog_variant,
        context.scenario._weblog_variant_image,
        context.scenario._library_init_image,
        context.scenario._cluster_agent_version,
        output_folder,
        test_name,
        api_key=context.scenario.api_key,
        app_key=context.scenario.app_key,
    )
    logger.info(f"K8sInstance creating -- {test_name}")
    k8s_instance.start_instance()
    logger.info("K8sInstance created")
    yield k8s_instance
    logger.info("K8sInstance Exporting debug info")
    k8s_instance.export_debug_info()
    logger.info("K8sInstance destroying")
    k8s_instance.destroy_instance()
    logger.info("K8sInstance destroyed")


class K8sInstance:
    def __init__(
        self,
        library,
        weblog_variant,
        weblog_variant_image,
        library_init_image,
        cluster_agent_tag,
        output_folder,
        test_name,
        api_key=None,
        app_key=None,
    ):
        self.library = library
        self.weblog_variant = weblog_variant
        self.weblog_variant_image = weblog_variant_image
        self.library_init_image = library_init_image
        self.cluster_agent_tag = cluster_agent_tag
        self.output_folder = output_folder
        self.test_name = test_name
        self.test_agent = K8sDatadog(output_folder, test_name, api_key=api_key, app_key=app_key)
        self.test_weblog = K8sWeblog(weblog_variant_image, library, library_init_image, output_folder, test_name)
        self.k8s_kind_cluster = None
        self.k8s_wrapper = None

    def start_instance(self):
        self.k8s_kind_cluster = ensure_cluster()
        self.k8s_wrapper = K8sWrapper(self.k8s_kind_cluster)
        self.test_agent.configure(self.k8s_kind_cluster, self.k8s_wrapper)
        self.test_weblog.configure(self.k8s_kind_cluster, self.k8s_wrapper)
        try:
            config.load_kube_config()
            logger.info(f"kube config loaded")
        except Exception as e:
            logger.error(f"Error loading kube config: {e}")

    def destroy_instance(self):
        try:
            destroy_cluster(self.k8s_kind_cluster)
        except Exception as e:
            logger.error(f"Error destroying cluster: {e}. Ignoring failure...")

    def deploy_datadog_cluster_agent(self, use_uds=False, features=None):
        """Deploys datadog cluster agent with admission controller and given features."""
        self.test_agent.deploy_datadog_cluster_agent(features=features, cluster_agent_tag=self.cluster_agent_tag)

    def deploy_test_agent(self):
        self.test_agent.deploy_test_agent()

    def deploy_weblog_as_pod(self, with_admission_controller=True, use_uds=False, env=None, service_account=None):
        if with_admission_controller:
            self.test_weblog.install_weblog_pod_with_admission_controller(env=env, service_account=service_account)
        else:
            self.test_weblog.install_weblog_pod_without_admission_controller(use_uds, env=env)

    def export_debug_info(self):
        self.test_agent.export_debug_info()
        self.test_weblog.export_debug_info()
