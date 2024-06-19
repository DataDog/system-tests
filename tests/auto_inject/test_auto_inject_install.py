import requests
import os
from utils import scenarios, features
from utils.tools import logger
from utils.onboarding.weblog_interface import make_get_request, warmup_weblog, make_internal_get_request
from utils.onboarding.backend_interface import wait_backend_trace_id
from utils.onboarding.wait_for_tcp_port import wait_for_port
from utils import bug
from utils import scenarios, context, features
from utils.virtual_machine.vm_logger import vm_logger
import pytest


class _AutoInjectBaseTest:
    def _test_install(self, virtual_machine):
        """ We can easily install agent and lib injection software from agent installation script. Given a  sample application we can enable tracing using local environment variables.  
            After starting application we can see application HTTP requests traces in the backend.
            Using the agent installation script we can install different versions of the software (release or beta) in different OS."""
        vm_ip = virtual_machine.ssh_config.hostname
        vm_port = virtual_machine.deffault_open_port
        vm_name = virtual_machine.name
        request_uuid = None
        if virtual_machine.krunvm_config is not None and virtual_machine.krunvm_config.stdin is not None:
            logger.info(
                f"We are testing on krunvm. The request to the weblog will be done using the stdin (inside the microvm)"
            )
            request_uuid = make_internal_get_request(virtual_machine.krunvm_config.stdin, vm_port)
        else:
            logger.info(f"Waiting for weblog available [{vm_ip}:{vm_port}]")
            wait_for_port(vm_port, vm_ip, 80.0)
            logger.info(f"[{vm_ip}]: Weblog app is ready!")
            warmup_weblog(f"http://{vm_ip}:{vm_port}/")
            logger.info(f"Making a request to weblog [{vm_ip}:{vm_port}]")
            request_uuid = make_get_request(f"http://{vm_ip}:{vm_port}/")

        logger.info(f"Http request done with uuid: [{request_uuid}] for ip [{vm_ip}]")
        wait_backend_trace_id(request_uuid, 120.0)

    def execute_command(self, virtual_machine, command):
        # Env for the command
        prefix_env = ""
        for key, value in virtual_machine.get_command_environment().items():
            prefix_env += f" {key}={value}"

        command_with_env = f"{prefix_env} {command}"

        with virtual_machine.ssh_config.get_ssh_connection() as ssh:
            _, stdout, stderr = ssh.exec_command(command_with_env, timeout=120)
            stdout.channel.set_combine_stderr(True)
            # Read the output line by line
            command_output = ""
            for line in stdout.readlines():
                if not line.startswith("export"):
                    command_output += line
            header = "*****************************************************************"
            vm_logger(context.scenario.name, virtual_machine.name).info(
                f"{header} \n  - COMMAND:  \n {header} \n {command} \n\n {header} \n COMMAND OUTPUT \n\n {header} \n {command_output}"
            )

    def _test_uninstall(
        self, virtual_machine, stop_weblog_command, start_weblog_command, uninstall_command, install_command
    ):
        """ We can unistall the auto injection software. We can start the app again 
        The weblog app should work but no sending traces to the backend.
        We can reinstall the auto inject software. The weblog app should be instrumented 
        and reporting traces to the backend."""
        logger.info(f"Launching _test_uninstall for : [{virtual_machine.name}]")

        vm_ip = virtual_machine.ssh_config.hostname
        vm_port = virtual_machine.deffault_open_port
        weblog_url = f"http://{vm_ip}:{vm_port}/"

        # Kill the app before the uninstallation
        self.execute_command(virtual_machine, stop_weblog_command)
        # Uninstall the auto inject
        self.execute_command(virtual_machine, uninstall_command)
        # Start the app again
        self.execute_command(virtual_machine, start_weblog_command)

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
        self.execute_command(virtual_machine, stop_weblog_command)
        # reinstall the auto inject
        self.execute_command(virtual_machine, install_command)
        # Start the app again
        self.execute_command(virtual_machine, start_weblog_command)
        # The app should be instrumented and reporting traces to the backend
        self._test_install(virtual_machine)
        logger.info(f"Success _test_uninstall for : [{virtual_machine.name}]")

    @pytest.fixture(autouse=True)
    def do_before_test(self, virtual_machine):
        if virtual_machine:
            current_test = os.environ.get("PYTEST_CURRENT_TEST").split(":")[-1].split(" ")[0]
            start = current_test.find("[")
            if start != -1:
                current_test = current_test[: start + 1]
            header = "----------------------------------------------------------------------"
            vm_logger(context.scenario.name, virtual_machine.name).info(
                f"{header} \n {header}  \n  Launching the test {current_test} for VM: {virtual_machine.name}  \n {header} \n {header}"
            )
        yield


@features.host_auto_instrumentation
@scenarios.host_auto_injection
class TestHostAutoInjectManual(_AutoInjectBaseTest):
    def test_install(self, virtual_machine):
        logger.info(f"Launching test_install for : [{virtual_machine.name}]...")
        self._test_install(virtual_machine)
        logger.info(f"Done test_install for : [{virtual_machine.name}]")

    def test_uninstall(self, virtual_machine):
        logger.info(f"Launching test_uninstall for : [{virtual_machine.name}]...")
        stop_weblog_command = "sudo systemctl kill -s SIGKILL test-app.service"
        # Weblog start command. If it's a ruby tracer, we must to rebuild the app before restart it
        start_weblog_command = "sudo systemctl start test-app.service"

        if context.scenario.library.library in ["ruby", "python", "dotnet"]:
            start_weblog_command = virtual_machine._vm_provision.weblog_installation.remote_command

        install_command = "dd-host-install"
        uninstall_command = "dd-host-install --uninstall"
        self._test_uninstall(
            virtual_machine, stop_weblog_command, start_weblog_command, uninstall_command, install_command
        )
        logger.info(f"Done test_uninstall for : [{virtual_machine.name}]...")


@features.host_auto_installation_script
@scenarios.host_auto_injection_install_script
class TestHostAutoInjectInstallScript(_AutoInjectBaseTest):
    def test_install(self, virtual_machine):
        self._test_install(virtual_machine)


@features.host_auto_instrumentation
@scenarios.simple_host_auto_injection
class TestSimpleHostAutoInjectManual(_AutoInjectBaseTest):
    def test_install(self, virtual_machine):
        logger.info(f"Launching test_install for : [{virtual_machine.name}]...")
        self._test_install(virtual_machine)
        logger.info(f"Done test_install for : [{virtual_machine.name}]")


@features.host_auto_instrumentation
@scenarios.host_auto_injection_ld_preload
class TestHostAutoInjectManualLdPreload(_AutoInjectBaseTest):
    def test_install_after_ld_preload(self, virtual_machine):
        """ We added entries to the ld.so.preload. After that, we can install the dd software and the app should be instrumented."""
        logger.info(f"Launching test_install for : [{virtual_machine.name}]...")
        self._test_install(virtual_machine)
        logger.info(f"Done test_install for : [{virtual_machine.name}]")


@features.container_auto_instrumentation
@scenarios.container_auto_injection
class TestContainerAutoInjectManual(_AutoInjectBaseTest):
    def test_install(self, virtual_machine):
        self._test_install(virtual_machine)

    def test_uninstall(self, virtual_machine):
        stop_weblog_command = "sudo -E docker-compose -f docker-compose.yml down && sudo -E docker-compose -f docker-compose-agent-prod.yml down"
        start_weblog_command = virtual_machine._vm_provision.weblog_installation.remote_command
        install_command = "dd-container-install && sudo systemctl restart docker"
        uninstall_command = "dd-container-install --uninstall && sudo systemctl restart docker"
        self._test_uninstall(
            virtual_machine, stop_weblog_command, start_weblog_command, uninstall_command, install_command
        )


@features.container_auto_installation_script
@scenarios.container_auto_injection_install_script
class TestContainerAutoInjectInstallScript(_AutoInjectBaseTest):
    def test_install(self, virtual_machine):
        self._test_install(virtual_machine)


@features.container_auto_instrumentation
@scenarios.simple_container_auto_injection
class TestSimpleContainerAutoInjectManual(_AutoInjectBaseTest):
    def test_install(self, virtual_machine):
        self._test_install(virtual_machine)


@features.container_auto_instrumentation
@scenarios.container_not_supported_auto_injection
class TestContainerNotSupportedAutoInjectManual(_AutoInjectBaseTest):
    """ Test for container not supported auto injection. We only check the app is working, although the auto injection is not performed."""

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


@features.host_auto_instrumentation
@scenarios.host_auto_injection
class TestHostAutoInjectChaos(_AutoInjectBaseTest):
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
        self.execute_command(virtual_machine, weblog_start_command)

        # The app should be instrumented and reporting traces to the backend
        self._test_install(virtual_machine)

    def test_remove_apm_inject_folder(self, virtual_machine):
        logger.info(f"Launching test_remove_apm_inject_folder for : [{virtual_machine.name}]...")
        self._test_removing_things(virtual_machine, "sudo rm -rf /opt/datadog/apm/inject")
        logger.info(f"Success test_remove_apm_inject_folder for : [{virtual_machine.name}]")

    @bug(library="dotnet", reason="AIT-8620")
    def test_remove_ld_preload(self, virtual_machine):
        logger.info(f"Launching test_remove_ld_preload for : [{virtual_machine.name}]...")
        self._test_removing_things(virtual_machine, "sudo rm /etc/ld.so.preload")
        logger.info(f"Success test_remove_ld_preload for : [{virtual_machine.name}]")


@features.installer_auto_instrumentation
@scenarios.installer_auto_injection
class TestInstallerAutoInjectManual(_AutoInjectBaseTest):
    # Note: uninstallation of a single installer package is not available today
    #  on the installer. As we can't only uninstall the injector, we are skipping
    #  the uninstall test today
    def test_install(self, virtual_machine):
        logger.info(f"Launching test_install for : [{virtual_machine.name}]...")
        self._test_install(virtual_machine)
        logger.info(f"Done test_install for : [{virtual_machine.name}]")

    def test_uninstall(self, virtual_machine):
        logger.info(f"Launching test_uninstall for : [{virtual_machine.name}]...")

        if context.scenario.weblog_variant == "test-app-{}".format(context.scenario.library.library):
            # Host
            stop_weblog_command = "sudo systemctl kill -s SIGKILL test-app.service"
            start_weblog_command = "sudo systemctl start test-app.service"
            if context.scenario.library.library in ["ruby", "python", "dotnet"]:
                start_weblog_command = virtual_machine._vm_provision.weblog_installation.remote_command
        else:
            # Container
            stop_weblog_command = "sudo -E docker-compose -f docker-compose.yml down"
            start_weblog_command = virtual_machine._vm_provision.weblog_installation.remote_command

        install_command = "sudo datadog-installer apm instrument"
        uninstall_command = "sudo datadog-installer apm uninstrument"
        self._test_uninstall(
            virtual_machine, stop_weblog_command, start_weblog_command, uninstall_command, install_command
        )
        logger.info(f"Done test_uninstall for : [{virtual_machine.name}]...")
