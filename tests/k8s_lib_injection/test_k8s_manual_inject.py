import os
from utils import scenarios, features
from utils.tools import logger
from utils import scenarios, context, features


@features.host_auto_instrumentation
@scenarios.k8s_lib_injection
class TestKubernetes:
    def test_kubernetes(self):
        logger.info(f"Launching test for kubernetes")
