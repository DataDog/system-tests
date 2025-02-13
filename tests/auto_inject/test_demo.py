from utils import scenarios, features, context
from utils.onboarding.weblog_interface import make_get_request
from utils.onboarding.wait_for_tcp_port import wait_for_port


@features.installer_auto_instrumentation
@scenarios.demo_aws
class TestDemoAws:
    """Demo test for AWS scenario"""

    def test_demo_provision_weblog(self):
        """Simple demo test"""
        virtual_machine = context.scenario.virtual_machine
        # http request configuration
        vm_ip = virtual_machine.get_ip()
        vm_port = virtual_machine.deffault_open_port
        weblog_request_timeout = 10
        weblog_url = f"http://{vm_ip}:{vm_port}/"

        # test assertion: the port is listenning and the request is successful
        assert wait_for_port(
            vm_port, vm_ip, weblog_request_timeout
        ), "Weblog port not reachable. Is the weblog running?"
        assert make_get_request(weblog_url) is not None, "Wrong response from weblog"
