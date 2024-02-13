from utils import scenarios, features
from utils.tools import logger
from utils.onboarding.weblog_interface import make_get_request, warmup_weblog
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
        vm_port = virtual_machine.deffault_open_port
        vm_name = virtual_machine.name
        logger.info(f"Launching test for : [{vm_name}]")
        logger.info(f"Waiting for weblog available [{vm_ip}:{vm_port}]")
        wait_for_port(vm_port, vm_ip, 80.0)
        logger.info(f"[{vm_ip}]: Weblog app is ready!")
        warmup_weblog(f"http://{vm_ip}:{vm_port}/")
        logger.info(f"Making a request to weblog [{vm_ip}:{vm_port}]")
        request_uuid = make_get_request(f"http://{vm_ip}:{vm_port}/")
        logger.info(f"Http request done with uuid: [{request_uuid}] for ip [{vm_ip}]")
        wait_backend_trace_id(request_uuid, 60.0)


@features.host_auto_instrumentation
@scenarios.host_auto_injection
class TestHostAutoInjectInstallManual(_AutoInjectInstallBaseTest):
    pass
