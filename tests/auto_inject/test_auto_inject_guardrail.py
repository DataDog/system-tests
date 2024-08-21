from utils import scenarios, features
from utils.tools import logger
from utils.onboarding.weblog_interface import make_get_request, warmup_weblog
from utils.onboarding.wait_for_tcp_port import wait_for_port
from utils import scenarios, features


class _AutoInjectNotSupportedBaseTest:
    """ Test for not supported auto injection. We only check the app is working, although the auto injection is not performed."""

    def test_app_working(self, virtual_machine):
        """ Test app is working."""
        vm_ip = virtual_machine.ssh_config.hostname
        vm_port = virtual_machine.deffault_open_port
        vm_name = virtual_machine.name

        logger.info(f"Waiting for weblog available [{vm_ip}:{vm_port}]")
        wait_for_port(vm_port, vm_ip, 80.0)
        logger.info(f"[{vm_ip}]: Weblog app is ready!")
        warmup_weblog(f"http://{vm_ip}:{vm_port}/")
        logger.info(f"Making a request to weblog [{vm_ip}:{vm_port}]")
        request_uuid = make_get_request(f"http://{vm_ip}:{vm_port}/")
        logger.info(f"Http request done for ip [{vm_ip}]")


@features.host_guardrail
@scenarios.installer_not_supported_auto_injection
class TestLanguageVersionNotSupported(_AutoInjectNotSupportedBaseTest):
    pass
