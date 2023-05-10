import pytest

from utils import missing_feature, context, scenarios
from utils.tools import logger
from tests.onboarding.utils.weblog_interface import *
from tests.onboarding.utils.backend_interface import *
from tests.onboarding.utils.wait_for_tcp_port import *

# @scenarios.onboarding_host_container
@scenarios.onboarding_host
class TestOnboardingInstall:
    def test_forTraces(self, onboardig_vm):
        """ We can easily install agent and lib injection software from agent installation script. Given a  sample application we can enable tracing using local environment variables.  
            After starting application we can see application HTTP requests traces in the backend.
            Using the agent installation script we can install different versions of the software (release or beta) in different OS."""
        logger.info(f"Launching test for : [{onboardig_vm.ip}]")
        logger.info(f"Waiting for weblog available [{onboardig_vm.ip}]")
        wait_for_port(5985, onboardig_vm.ip, 60.0)
        logger.info(f"[{onboardig_vm.ip}]: Weblog app is ready!")
        logger.info(f"Making a request to weblog [{onboardig_vm.ip}]")
        request_uuid = make_get_request("http://" + onboardig_vm.ip + ":5985/")
        logger.info(f"Http request done with uuid: [{request_uuid}] for ip [{onboardig_vm.ip}]")
        wait_backend_trace_id(request_uuid, 60.0)
