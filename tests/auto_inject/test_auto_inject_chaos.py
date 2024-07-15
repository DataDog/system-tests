import requests
from utils import scenarios, features
from utils.tools import logger
from utils.onboarding.weblog_interface import warmup_weblog
from utils.onboarding.wait_for_tcp_port import wait_for_port
from utils import scenarios, context, features
import tests.auto_inject.utils as base
from utils import bug


@features.host_auto_instrumentation
@scenarios.installer_host_auto_injection_chaos
class TestAutoInjectChaos(base.AutoInjectBaseTest):
    def _test_removing_things(self, virtual_machine, evil_command):
        """ Test break the installation and restore it.
        After breaking the installation, the app should be still working (but no sending traces to the backend).
        After breaking the installation, we can restart the app
        After restores the installation, the app should be working and sending traces to the backend."""

        vm_ip = virtual_machine.ssh_config.hostname
        vm_port = virtual_machine.deffault_open_port
        weblog_url = f"http://{vm_ip}:{vm_port}/"

        # Weblog start command. If it's a ruby tracer, we must to rebuild the app before restart it
        weblog_start_command = "sudo systemctl start test-app.service"
        if context.scenario.library.library in ["ruby", "python", "dotnet"]:
            weblog_start_command = virtual_machine._vm_provision.weblog_installation.remote_command

        # Ok the installation is done, now we can do some chaos
        self._test_install(virtual_machine)

        # Remove installation folder
        self.execute_command(virtual_machine, evil_command)

        # Assert the app is still working
        wait_for_port(vm_port, vm_ip, 40.0)
        r = requests.get(weblog_url, timeout=10)
        assert r.status_code == 200, "The weblog app it's not working after remove the installation folder"

        # Kill the app
        self.execute_command(virtual_machine, "sudo systemctl kill -s SIGKILL test-app.service")

        # Start the app again
        self.execute_command(virtual_machine, weblog_start_command)
        # App shpuld be working again, although the installation folder was removed
        wait_for_port(vm_port, vm_ip, 40.0)
        warmup_weblog(weblog_url)
        r = requests.get(weblog_url, timeout=10)
        assert (
            r.status_code == 200
        ), "The weblog app it's not working after remove the installation folder  and restart the app"
        # Kill the app before restore the installation
        self.execute_command(virtual_machine, "sudo systemctl kill -s SIGKILL test-app.service")
        # Restore the installation
        apm_inject_restore = "sudo datadog-installer apm instrument"

        # Env for installation command
        prefix_env = f"DD_LANG={context.scenario.library.library}"
        for key, value in virtual_machine._vm_provision.env.items():
            prefix_env += f" DD_{key}={value}"

        logger.info("Restoring installation using the command:: ")
        apm_inject_restore = f"{prefix_env} {apm_inject_restore}"
        logger.info(apm_inject_restore)
        _, stdout, stderr = virtual_machine.ssh_config.get_ssh_connection().exec_command(apm_inject_restore)
        stdout.channel.set_combine_stderr(True)

        # Read the output line by line
        command_output = ""
        for line in stdout.readlines():
            if not line.startswith("export"):
                command_output += line

        logger.info("Restoring installation output:")
        logger.info(command_output)

        # Start the app again
        self.execute_command(virtual_machine, weblog_start_command)

        # The app should be instrumented and reporting traces to the backend
        self._test_install(virtual_machine)

    @bug(library="dotnet", reason="AIT-8620")
    def test_remove_ld_preload(self, virtual_machine):
        logger.info(f"Launching test_remove_ld_preload for : [{virtual_machine.name}]...")
        self._test_removing_things(virtual_machine, "sudo rm /etc/ld.so.preload")
        logger.info(f"Success test_remove_ld_preload for : [{virtual_machine.name}]")
