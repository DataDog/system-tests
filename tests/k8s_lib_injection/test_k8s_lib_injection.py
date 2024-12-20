import os
import time

import requests
from utils import scenarios, features, bug, context
from utils.tools import logger
from utils.onboarding.weblog_interface import make_get_request, warmup_weblog
from utils.onboarding.backend_interface import wait_backend_trace_id
from utils.onboarding.wait_for_tcp_port import wait_for_port
from utils import scenarios, features, irrelevant
from utils.k8s_lib_injection.k8s_kind_cluster import default_kind_cluster

from tests.k8s_lib_injection.utils import get_dev_agent_traces


class _TestK8sLibInjection:
    """Test K8s lib injection"""

    def test_k8s_lib_injection(self):
        traces_json = get_dev_agent_traces(default_kind_cluster)
        assert len(traces_json) > 0, "No traces found"


@features.k8s_admission_controller
@scenarios.k8s_lib_injection
class TestK8sLibInjection(_TestK8sLibInjection):
    """Test K8s lib injection with admission controller"""

    pass


@features.k8s_admission_controller
@scenarios.k8s_lib_injection_uds
class TestK8sLibInjectionUDS(_TestK8sLibInjection):
    """Test K8s lib injection with admission controller and UDS"""

    pass


@features.k8s_admission_controller
@scenarios.k8s_lib_injection_no_ac
class TestK8sLibInjectionNoAC(_TestK8sLibInjection):
    """Test K8s lib injection without admission controller"""

    pass


@features.k8s_admission_controller
@scenarios.k8s_lib_injection_no_ac_uds
class TestK8sLibInjectionNoAC_UDS(_TestK8sLibInjection):
    """Test K8s lib injection without admission controller and UDS"""

    pass
