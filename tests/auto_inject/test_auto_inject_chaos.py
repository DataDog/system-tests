import requests
from utils import scenarios, features
from utils.tools import logger
from utils.onboarding.weblog_interface import make_get_request, warmup_weblog
from utils.onboarding.backend_interface import wait_backend_trace_id
from utils.onboarding.wait_for_tcp_port import wait_for_port
from utils import irrelevant
from utils import scenarios, context, features
from tests.auto_inject.test_auto_inject_install import _AutoInjectInstallBaseTest


@features.host_auto_instrumentation
@scenarios.host_auto_injection_chaos
class TestHostAutoInjectInstallManual(_AutoInjectInstallBaseTest):
    def _test_removing_things(self, virtual_machine, evil_command):
        """ Test break the installation and restore it.
        After breaking the installation, the app should be still working (but no sending traces to the backend).
        After breaking the installation, we can restart the app
        After restores the installation, the app should be working and sending traces to the backend."""

        vm_ip = virtual_machine.ssh_config.hostname
        vm_port = virtual_machine.deffault_open_port
        weblog_url = f"http://{vm_ip}:{vm_port}/"

        # Ok the installation is done, now we can do some chaos
        self.test_install(virtual_machine)

        # Remove installation folder
        virtual_machine.ssh_config.get_ssh_connection().exec_command(evil_command)

        # Assert the app is still working
        wait_for_port(vm_port, vm_ip, 40.0)
        r = requests.get(weblog_url, timeout=10)
        assert r.status_code == 200, "The weblog app it's not working after remove the installation folder"

        # Kill the app
        virtual_machine.ssh_config.get_ssh_connection().exec_command("sudo systemctl kill -s SIGKILL test-app.service")

        # Start the app again
        virtual_machine.ssh_config.get_ssh_connection().exec_command("sudo systemctl start test-app.service")

        # App shpuld be working again, although the installation folder was removed
        wait_for_port(vm_port, vm_ip, 40.0)
        warmup_weblog(weblog_url)
        r = requests.get(weblog_url, timeout=10)
        assert (
            r.status_code == 200
        ), "The weblog app it's not working after remove the installation folder  and restart the app"

        # Kill the app before restore the installation
        virtual_machine.ssh_config.get_ssh_connection().exec_command("sudo systemctl kill -s SIGKILL test-app.service")

        # Restore the installation
        apm_inject_restore = ""
        for installation in virtual_machine._vm_provision.installations:
            if installation.id == "autoinjection_install_manual":
                apm_inject_restore = installation.remote_command
                break
        # Env for installation command
        prefix_env = f"DD_LANG={context.scenario.library.library}"
        for key, value in virtual_machine._vm_provision.env.items():
            prefix_env += f" DD_{key}={value}"

        logger.info("Restoring installation using the command: ")
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
        virtual_machine.ssh_config.get_ssh_connection().exec_command("sudo systemctl start test-app.service")

        # The app should be instrumented and reporting traces to the backend
        self.test_install(virtual_machine)

    def test_remove_apm_inject_folder(self, virtual_machine):
        self._test_removing_things(virtual_machine, "sudo rm -rf /opt/datadog/apm/inject")

    def test_remove_ld_preload(self, virtual_machine):
        self._test_removing_things(virtual_machine, "sudo rm /etc/ld.so.preload")
