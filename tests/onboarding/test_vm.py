from utils import scenarios, features
from utils.tools import logger
from utils.onboarding.weblog_interface import make_get_request
from utils.onboarding.backend_interface import wait_backend_trace_id
from utils.onboarding.wait_for_tcp_port import wait_for_port


@features.container_auto_instrumentation
@scenarios.vm_scenario
class TestVMScenario:
    def test_vm(self, virtual_machine):
        logger.info(f"VM scenario test for : [{virtual_machine.name}]")
        pass
