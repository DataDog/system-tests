import requests
import pytest
import os

from utils import context
from utils.tools import logger
import json
from utils.k8s_lib_injection.k8s_kind_cluster import ensure_cluster, destroy_cluster
from utils.k8s_lib_injection.k8s_datadog_cluster_agent import K8sDatadogClusterTestAgent
from utils.k8s_lib_injection.k8s_weblog import K8sWeblog
from kubernetes import config


@pytest.fixture
def test_k8s_instance(request):
    test_name = request.node.name
    library = "js" if context.scenario.library.library == "nodejs" else context.scenario.library.library
    k8s_instance = K8sInstance(
        library,
        context.scenario.weblog_variant,
        context.scenario._weblog_variant_image,
        context.scenario._library_init_image,
        context.scenario._library_init_image_tag,
        context.scenario._prefix_library_init_image,
    )
    logger.info(f"K8sInstance creating -- {test_name}")
    k8s_instance.start_instance()
    logger.info("K8sInstance created")
    yield k8s_instance
    logger.info("K8sInstance Exporting debug info")
    k8s_instance.export_debug_info(test_name)
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
        library_init_image_tag,
        prefix_library_init_image,
    ):
        self.library = library
        self.weblog_variant = weblog_variant
        self.weblog_variant_image = weblog_variant_image
        self.library_init_image = library_init_image
        self.library_init_image_tag = library_init_image_tag
        # If we inject the library using configmap and cluster agent, we need to use the prefix_library_init_image
        # only for snapshot images. The agent builds image names like “gcr.io/datadoghq/dd-lib-python-init:latest_snapshot”
        # but we need gcr.io/datadoghq/dd-trace-py/dd-lib-python-init:latest_snapshot
        # We use this prefix with the env prop "DD_ADMISSION_CONTROLLER_AUTO_INSTRUMENTATION_CONTAINER_REGISTRY"
        self.prefix_library_init_image = prefix_library_init_image

        self.test_agent = K8sDatadogClusterTestAgent(prefix_library_init_image)
        self.test_weblog = K8sWeblog(weblog_variant_image, library, library_init_image)
        self.k8s_kind_cluster = None

    def start_instance(self):
        self.k8s_kind_cluster = ensure_cluster()
        config.load_kube_config()
        self.test_agent.configure(self.k8s_kind_cluster)
        self.test_weblog.configure(self.k8s_kind_cluster)

    def destroy_instance(self):
        destroy_cluster(self.k8s_kind_cluster)

    def deploy_test_agent(self):
        self.test_agent.desploy_test_agent()
        return self.test_agent

    def deploy_weblog_as_pod(self, with_admission_controller=True, use_uds=False):
        if with_admission_controller:
            self.test_weblog.install_weblog_pod_with_admission_controller()
        else:
            self.test_weblog.install_weblog_pod_without_admission_controller(use_uds)

        return self.test_weblog

    def deploy_weblog_as_deployment(self):
        self.test_weblog.deploy_app_auto()
        return self.test_weblog

    def apply_config_auto_inject(self, config_data, timeout=200):
        self.test_agent.apply_config_auto_inject(config_data)
        self.test_weblog.wait_for_weblog_after_apply_configmap(f"{self.library}-app", timeout=timeout)
        return self.test_agent

    def export_debug_info(self, test_name):
        # Create a folder with the test name
        output_folder = f"{context.scenario.host_log_folder}/{test_name}"
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        self.test_agent.export_debug_info(output_folder, test_name)
        self.test_weblog.export_debug_info(output_folder, test_name)
