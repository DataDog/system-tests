from utils import scenarios, features, context, logger
from utils.onboarding.weblog_interface import make_get_request, warmup_weblog
from utils.onboarding.wait_for_tcp_port import wait_for_port


@features.host_guardrail
@scenarios.installer_not_supported_auto_injection
class TestLanguageVersionNotSupported:
    """Test for not supported auto injection. We only check the app is working, although the auto injection is not performed."""

    def test_app_working(self):
        """Test app is working."""
        virtual_machine = context.virtual_machine
        vm_ip = virtual_machine.get_ip()
        vm_port = virtual_machine.deffault_open_port
        vm_name = virtual_machine.name
        logger.info(f"[{vm_name}] Waiting for weblog available [{vm_ip}:{vm_port}]")
        assert wait_for_port(vm_port, vm_ip, 80.0), "Weblog port not reachable. Is the weblog running?"
        logger.info(f"[{vm_ip}]: Weblog app is ready!")
        warmup_weblog(f"http://{vm_ip}:{vm_port}/")
        logger.info(f"Making a request to weblog [{vm_ip}:{vm_port}]")
        make_get_request(f"http://{vm_ip}:{vm_port}/")
        logger.info(f"Http request done for ip [{vm_ip}]")
