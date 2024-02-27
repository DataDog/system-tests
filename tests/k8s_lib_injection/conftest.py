import requests
import pytest


from utils import context
from utils.tools import logger
import json
from utils.k8s_lib_injection.k8s_command_utils import ensure_cluster, destroy_cluster
from utils.k8s_lib_injection.k8s_datadog_cluster_agent import K8sDatadogClusterTestAgent
from utils.k8s_lib_injection.k8s_weblog import K8sWeblog
from kubernetes import config
from utils import scenarios


@pytest.fixture
def test_k8s_instance():

    k8s_instance = K8sInstance(
        context.scenario.library.library,
        context.scenario.weblog_variant,
        context.scenario._weblog_variant_image,
        context.scenario._library_init_image,
    )
    logger.info("K8sInstance creating")
    k8s_instance.start_instance()
    logger.info("K8sInstance created")
    yield k8s_instance
    logger.info("K8sInstance destroying")
    k8s_instance.destroy_instance()
    logger.info("K8sInstance destroyed")


class K8sInstance:
    def __init__(self, library, weblog_variant, weblog_variant_image, library_init_image):
        self.library = library
        self.weblog_variant = weblog_variant
        self.weblog_variant_image = weblog_variant_image
        self.library_init_image = library_init_image

        self.test_agent = K8sDatadogClusterTestAgent()
        self.test_weblog = K8sWeblog()

    def start_instance(self):
        ensure_cluster()
        config.load_kube_config()

    def destroy_instance(self):
        destroy_cluster()

    def deploy_test_agent(self):
        self.test_agent.desploy_test_agent()
        return self.test_agent

    def deploy_weblog_as_pod(self):
        self.test_weblog.deploy_app_manual(self.weblog_variant_image, self.library, self.library_init_image)
        return self.test_weblog

    def say_hello(self):
        logger.info("Hello, World!")
