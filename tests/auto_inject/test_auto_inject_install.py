from utils import scenarios, features, flaky
from utils.tools import logger
from utils import scenarios, features
import tests.auto_inject.utils as base
from utils.virtual_machine.utils import parametrize_virtual_machines


@features.host_auto_installation_script
@scenarios.host_auto_injection_install_script
class TestHostAutoInjectInstallScript(base.AutoInjectBaseTest):
    @parametrize_virtual_machines(
        bugs=[
            {"vm_branch": "amazon_linux2", "weblog_variant": "test-app-ruby", "reason": "INPLAT-103"},
            {"vm_branch": "centos_7_amd64", "weblog_variant": "test-app-ruby", "reason": "INPLAT-103"},
            {"vm_branch": "redhat_8_6", "vm_cpu": "arm64", "weblog_variant": "test-app-ruby", "reason": "INPLAT-103"},
        ]
    )
    def test_install(self, virtual_machine):
        self._test_install(virtual_machine)


@features.host_auto_installation_script
@scenarios.local_auto_injection_install_script
class TestLocalAutoInjectInstallScript(base.AutoInjectBaseTest):
    @parametrize_virtual_machines()
    def test_install(self, virtual_machine):
        self._test_install(virtual_machine)


@features.auto_instrumentation_profiling
@scenarios.simple_auto_injection_profiling
class TestSimpleInstallerAutoInjectManualProfiling(base.AutoInjectBaseTest):
    @parametrize_virtual_machines(
        bugs=[
            {"vm_cpu": "arm64", "weblog_variant": "test-app-dotnet", "reason": "PROF-10783"},
            {"vm_cpu": "arm64", "weblog_variant": "test-app-dotnet-container", "reason": "PROF-10783"},
        ]
    )
    def test_profiling(self, virtual_machine):
        logger.info(f"Launching test_install for : [{virtual_machine.name}]...")
        self._test_install(virtual_machine, profile=True)
        logger.info(f"Done test_install for : [{virtual_machine.name}]")


@features.host_auto_installation_script_profiling
@scenarios.host_auto_injection_install_script_profiling
class TestHostAutoInjectInstallScriptProfiling(base.AutoInjectBaseTest):
    @parametrize_virtual_machines(
        bugs=[{"vm_cpu": "arm64", "weblog_variant": "test-app-dotnet", "reason": "PROF-10783"}]
    )
    def test_profiling(self, virtual_machine):
        logger.info(f"Launching test_install for : [{virtual_machine.name}]...")
        self._test_install(virtual_machine, profile=True)
        logger.info(f"Done test_install for : [{virtual_machine.name}]")


@features.container_auto_installation_script
@scenarios.container_auto_injection_install_script
class TestContainerAutoInjectInstallScript(base.AutoInjectBaseTest):
    @flaky(weblog_variant="test-app-java-buildpack", reason="APMON-1595")
    @parametrize_virtual_machines(
        bugs=[{"vm_name": "AlmaLinux_8_arm64", "weblog_variant": "test-app-python-alpine", "reason": "APMON-1576"}]
    )
    def test_install(self, virtual_machine):
        self._test_install(virtual_machine)


@features.container_auto_installation_script_profiling
@scenarios.container_auto_injection_install_script_profiling
class TestContainerAutoInjectInstallScriptProfiling(base.AutoInjectBaseTest):
    @parametrize_virtual_machines(
        bugs=[{"vm_cpu": "arm64", "weblog_variant": "test-app-dotnet-container", "reason": "PROF-10783"}]
    )
    def test_profiling(self, virtual_machine):
        self._test_install(virtual_machine, profile=True)


@features.installer_auto_instrumentation
@scenarios.container_auto_injection_install_script_crashtracking
class TestContainerAutoInjectInstallScriptCrashTracking_NoZombieProcess(base.AutoInjectBaseTest):
    @parametrize_virtual_machines()
    def test_install(self, virtual_machine):
        self.warmup(virtual_machine)

        command_line = self.get_commandline(virtual_machine)

        print(f"Commandline is {command_line}")

        command_output = self.execute_command(virtual_machine, "ps aux --forest")
        logger.info("Initial: " + command_output)

        response = self.fork_and_crash(virtual_machine)

        print(f"Response is {response}")

        output = self.execute_command(virtual_machine, "ps -o pid,ppid,state,cmd | awk '$3 == \"Z\" { print $0 }'")
        output = output.strip()

        print(f'Result: {output}')

        output2 = self.execute_command(virtual_machine, "ps -o pid,ppid,state,cmd")
        print(f'Output2: {output2}')

        output3 = self.execute_command(virtual_machine, "ps -o pid,ppid,state,cmd | grep ' Z '")
        output3 = output.strip()

        print(f'Output3: {output3}')

        output4 = self.execute_command(virtual_machine, "ps -o pid,ppid,state,cmd | sed -n '/ Z /p'")
        output4 = output.strip()

        print(f'Output4: {output4}')

        command_output = self.execute_command(virtual_machine, "ps aux --forest")
        logger.info("Final: " + command_output)
        assert output == ""
        print(f'Test succeeded :(')
        assert False

@features.installer_auto_instrumentation
@scenarios.installer_auto_injection
class TestInstallerAutoInjectManual(base.AutoInjectBaseTest):
    # Note: uninstallation of a single installer package is not available today
    #  on the installer. As we can't only uninstall the injector, we are skipping
    #  the uninstall test today
    @flaky(weblog_variant="test-app-java-buildpack", reason="APMON-1595")
    @parametrize_virtual_machines(
        bugs=[
            {"vm_name": "AlmaLinux_8_arm64", "weblog_variant": "test-app-python-alpine", "reason": "APMON-1576"},
            {"vm_branch": "amazon_linux2", "weblog_variant": "test-app-ruby", "reason": "INPLAT-103"},
            {"vm_branch": "centos_7_amd64", "weblog_variant": "test-app-ruby", "reason": "INPLAT-103"},
            {"vm_branch": "redhat_8_6", "vm_cpu": "arm64", "weblog_variant": "test-app-ruby", "reason": "INPLAT-103"},
        ]
    )
    def test_install_uninstall(self, virtual_machine):
        logger.info(f"Launching test_install_uninstall for : [{virtual_machine.name}]...")
        logger.info(f"Check install for : [{virtual_machine.name}]")
        self._test_install(virtual_machine)
        logger.info(f"Check uninstall for : [{virtual_machine.name}]...")
        self._test_uninstall(virtual_machine)
        logger.info(f"Done test_install_uninstall for : [{virtual_machine.name}]...")


@features.installer_auto_instrumentation
@scenarios.simple_installer_auto_injection
class TestSimpleInstallerAutoInjectManual(base.AutoInjectBaseTest):
    @flaky(weblog_variant="test-app-java-buildpack", reason="APMON-1595")
    @parametrize_virtual_machines(
        bugs=[
            {"vm_name": "AlmaLinux_8_arm64", "weblog_variant": "test-app-python-alpine", "reason": "APMON-1576"},
            {"vm_branch": "amazon_linux2", "weblog_variant": "test-app-ruby", "reason": "INPLAT-103"},
            {"vm_branch": "centos_7_amd64", "weblog_variant": "test-app-ruby", "reason": "INPLAT-103"},
            {"vm_branch": "redhat_8_6", "vm_cpu": "arm64", "weblog_variant": "test-app-ruby", "reason": "INPLAT-103"},
        ]
    )
    def test_install(self, virtual_machine):
        logger.info(f"Launching test_install for : [{virtual_machine.name}]...")
        self._test_install(virtual_machine)
        logger.info(f"Done test_install for : [{virtual_machine.name}]")
