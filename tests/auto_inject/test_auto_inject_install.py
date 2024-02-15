import requests

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


@features.host_auto_instrumentation
@scenarios.host_auto_injection
class TestHostAutoInjectChaos(_AutoInjectInstallBaseTest):
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


@features.host_auto_instrumentation
@scenarios.host_auto_injection
class TestHostAutoInjectUninstallManual(_AutoInjectInstallBaseTest):
    def test_uninstall(self, virtual_machine):

        vm_ip = virtual_machine.ssh_config.hostname
        vm_port = virtual_machine.deffault_open_port
        weblog_url = f"http://{vm_ip}:{vm_port}/"

        # Kill the app before the uninstallation
        virtual_machine.ssh_config.get_ssh_connection().exec_command("sudo systemctl kill -s SIGKILL test-app.service")
        # Uninstall the auto inject
        virtual_machine.ssh_config.get_ssh_connection().exec_command("dd-host-install --uninstall")
        # Start the app again
        virtual_machine.ssh_config.get_ssh_connection().exec_command("sudo systemctl start test-app.service")
        wait_for_port(vm_port, vm_ip, 40.0)
        warmup_weblog(weblog_url)
        request_uuid = make_get_request(weblog_url)
        logger.info(f"Http request done with uuid: [{request_uuid}] for ip [{virtual_machine.name}]")
        try:
            wait_backend_trace_id(request_uuid, 10.0)
            raise AssertionError("The weblog application is instrumented after uninstall DD software")
        except TimeoutError:
            # OK there are no traces, the weblog app is not instrumented
            pass
        # Kill the app before restore the installation
        virtual_machine.ssh_config.get_ssh_connection().exec_command("sudo systemctl kill -s SIGKILL test-app.service")
        # reinstall the auto inject
        virtual_machine.ssh_config.get_ssh_connection().exec_command("dd-host-install")
        # Start the app again
        virtual_machine.ssh_config.get_ssh_connection().exec_command("sudo systemctl start test-app.service")
        # The app should be instrumented and reporting traces to the backend
        self.test_install(virtual_machine)
