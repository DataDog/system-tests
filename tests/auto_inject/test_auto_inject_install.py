from utils import scenarios, features
from utils.tools import logger
from utils.onboarding.weblog_interface import make_get_request
from utils.onboarding.backend_interface import wait_backend_trace_id
from utils.onboarding.wait_for_tcp_port import wait_for_port
from utils import irrelevant
from utils import scenarios, context, features


class _AutoInjectInstallBaseTest:
    @irrelevant(
        condition=getattr(context.scenario, "required_vms", []) == [], reason="No VMs to test",
    )
    def test_install(self, virtual_machine):
        """ We can easily install agent and lib injection software from agent installation script. Given a  sample application we can enable tracing using local environment variables.  
            After starting application we can see application HTTP requests traces in the backend.
            Using the agent installation script we can install different versions of the software (release or beta) in different OS."""
        vm_ip = virtual_machine.ssh_config.hostname
        logger.info(f"Launching test for : [{virtual_machine.name}]")
        logger.info(f"Waiting for weblog available [{vm_ip}]")
        # TODO move this wait command to the scenario warmup. How to do this? Pulumi is working in parallel and async, in the scenario warmup we don't have the server IP
        wait_for_port(5985, vm_ip, 80.0)
        logger.info(f"[{vm_ip}]: Weblog app is ready!")
        logger.info(f"Making a request to weblog [{vm_ip}]")
        request_uuid = make_get_request("http://" + vm_ip + ":5985/")
        logger.info(f"Http request done with uuid: [{request_uuid}] for ip [{vm_ip}]")
        wait_backend_trace_id(request_uuid, 60.0)


# @features.host_auto_instrumentation
@scenarios.vm_scenario
class TestHostAutoInjectInstallManual(_AutoInjectInstallBaseTest):
    pass
