import requests
from utils import scenarios, features, context, bug, irrelevant, missing_feature, logger
from utils.onboarding.weblog_interface import warmup_weblog
from utils.onboarding.wait_for_tcp_port import wait_for_port
import tests.auto_inject.utils as base
from utils.virtual_machine.virtual_machines import _VirtualMachine


class BaseAutoInjectChaos(base.AutoInjectBaseTest):
    def _test_removing_things(self, virtual_machine: _VirtualMachine, evil_command):
        """Test break the installation and restore it.
        After breaking the installation, the app should be still working (but no sending traces to the backend).
        After breaking the installation, we can restart the app
        After restores the installation, the app should be working and sending traces to the backend.
        """

        vm_ip = virtual_machine.get_ip()
        vm_port = virtual_machine.deffault_open_port
        weblog_url = f"http://{vm_ip}:{vm_port}/"
        # Weblog start command. If it's a ruby tracer, we must to rebuild the app before restart it
        weblog_start_command = "sudo systemctl start test-app.service"
        if context.library.name in ["ruby", "python", "dotnet"]:
            weblog_start_command = virtual_machine._vm_provision.weblog_installation.remote_command

        # Ok the installation is done, now we can do some chaos
        self._test_install(virtual_machine)
        logger.info(f"[{virtual_machine.name}]Ok the installation is done, now we can do some chaos")
        # Remove installation folder
        self.execute_command(virtual_machine, evil_command)
        logger.info(f"[{virtual_machine.name}]Ok evil command launched!")
        # Assert the app is still working
        assert wait_for_port(vm_port, vm_ip, 40.0), "Weblog port not reachable. Is the weblog running?"
        r = requests.get(weblog_url, timeout=10)
        assert r.status_code == 200, "The weblog app it's not working after remove the installation folder"
        logger.info(f"[{virtual_machine.name}]Ok the weblog app it's working after remove wrong things")
        # Kill the app
        self.execute_command(
            virtual_machine,
            "sudo systemctl kill -s SIGKILL test-app.service || sudo systemctl kill -s KILL test-app.service ",
        )
        logger.info(f"[{virtual_machine.name}]Ok the weblog app stopped")
        # Start the app again
        self.execute_command(virtual_machine, weblog_start_command)
        # App shpuld be working again, although the installation folder was removed
        assert wait_for_port(vm_port, vm_ip, 40.0), "Weblog port not reachable. Is the weblog running?"
        warmup_weblog(weblog_url)
        r = requests.get(weblog_url, timeout=10)
        assert (
            r.status_code == 200
        ), "The weblog app it's not working after remove the installation folder  and restart the app"
        # Kill the app before restore the installation
        self.execute_command(
            virtual_machine,
            "sudo systemctl kill -s SIGKILL test-app.service || sudo systemctl kill -s KILL test-app.service",
        )
        # Restore the installation
        apm_inject_restore = "sudo datadog-installer apm instrument"

        # Env for installation command
        prefix_env = f"DD_LANG={context.library.name}"
        for key, value in virtual_machine._vm_provision.env.items():
            prefix_env += f" DD_{key}={value}"

        logger.info("Restoring installation using the command:: ")
        apm_inject_restore = f"{prefix_env} {apm_inject_restore}"
        logger.info(apm_inject_restore)
        _, stdout, stderr = virtual_machine.get_ssh_connection().exec_command(apm_inject_restore)
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


@features.installer_auto_instrumentation
@scenarios.chaos_installer_auto_injection
class TestAutoInjectChaos(BaseAutoInjectChaos):
    @bug(
        context.vm_os_branch in ["redhat", "amazon_linux2"]
        and context.vm_os_cpu == "arm64"
        and context.weblog_variant == "test-app-ruby",
        reason="INPLAT-103",
    )
    @irrelevant(
        context.vm_name in ["Amazon_Linux_2023_amd64", "Amazon_Linux_2023_arm64"],
        reason="LD library failures impact on the docker engine, causes flakiness",
    )
    @missing_feature(context.vm_os_branch == "windows", reason="Not implemented on Windows")
    @irrelevant(
        context.vm_name in ["AlmaLinux_8_amd64", "AlmaLinux_8_arm64", "OracleLinux_8_8_amd64", "OracleLinux_8_8_arm64"]
        and context.weblog_variant == "test-app-python",
        reason="Flaky machine with python and the ld preload changes",
    )
    def test_install_after_ld_preload(self):
        """We added entries to the ld.so.preload. After that, we can install the dd software and the app should be instrumented."""
        virtual_machine = context.virtual_machine
        logger.info(f"Launching test_install for : [{virtual_machine.name}]...")
        self._test_install(virtual_machine)
        logger.info(f"Done test_install for : [{virtual_machine.name}]")

    @bug(
        context.vm_os_branch in ["redhat", "amazon_linux2"]
        and context.vm_os_cpu == "arm64"
        and context.weblog_variant == "test-app-ruby",
        reason="INPLAT-103",
    )
    @missing_feature(context.vm_os_branch == "windows", reason="Not implemented on Windows")
    @irrelevant(
        context.vm_name in ["AlmaLinux_8_amd64", "AlmaLinux_8_arm64", "OracleLinux_8_8_amd64", "OracleLinux_8_8_arm64"]
        and context.weblog_variant == "test-app-python",
        reason="Flaky machine with python and the ld preload changes",
    )
    def test_remove_ld_preload(self):
        """We added entries to the ld.so.preload. After that, we can remove the entries and the app should be instrumented."""
        logger.info(f"Launching test_remove_ld_preload for : [{context.vm_name}]...")
        self._test_removing_things(context.virtual_machine, "sudo rm /etc/ld.so.preload")
        logger.info(f"Success test_remove_ld_preload for : [{context.vm_name}]")
