import re
from utils import scenarios, features, flaky, missing_feature
from utils.tools import logger
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
    def test_install(self, virtual_machine):
        logger.info(f"Launching test_install for : [{virtual_machine.name}]...")
        self._test_install(virtual_machine, profile=True)
        logger.info(f"Done test_install for : [{virtual_machine.name}]")


@features.host_auto_installation_script_profiling
@scenarios.host_auto_injection_install_script_profiling
class TestHostAutoInjectInstallScriptProfiling(base.AutoInjectBaseTest):
    @parametrize_virtual_machines(
        bugs=[{"vm_cpu": "arm64", "weblog_variant": "test-app-dotnet", "reason": "PROF-10783"}]
    )
    def test_install(self, virtual_machine):
        logger.info(f"Launching test_install for : [{virtual_machine.name}]...")
        self._test_install(virtual_machine, profile=True)
        logger.info(f"Done test_install for : [{virtual_machine.name}]")


@features.installer_auto_instrumentation
@scenarios.installer_auto_injection_ld_preload
class TestHostAutoInjectManualLdPreload(base.AutoInjectBaseTest):
    @parametrize_virtual_machines(
        bugs=[
            {"vm_branch": "amazon_linux2", "weblog_variant": "test-app-ruby", "reason": "INPLAT-103"},
            {"vm_branch": "centos_7_amd64", "weblog_variant": "test-app-ruby", "reason": "INPLAT-103"},
            {"vm_branch": "redhat_8_6", "vm_cpu": "arm64", "weblog_variant": "test-app-ruby", "reason": "INPLAT-103"},
        ]
    )
    def test_install_after_ld_preload(self, virtual_machine):
        """ We added entries to the ld.so.preload. After that, we can install the dd software and the app should be instrumented."""
        logger.info(f"Launching test_install for : [{virtual_machine.name}]...")
        self._test_install(virtual_machine)
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
    def test_install(self, virtual_machine):
        self._test_install(virtual_machine, profile=True)


@features.installer_auto_instrumentation
@scenarios.container_auto_injection_install_script_crashtracking
class TestContainerAutoInjectInstallScriptCrashTracking(base.AutoInjectBaseTest):
    @parametrize_virtual_machines()
    def test_install(self, virtual_machine):
        self._test_install(virtual_machine, crashlog=True)

@features.installer_auto_instrumentation
@scenarios.container_auto_injection_install_script_crashtracking_childprocess
class TestContainerAutoInjectInstallScriptCrashTracking_NoChildProcess(base.AutoInjectBaseTest):
    @parametrize_virtual_machines()
    def test_install(self, virtual_machine):
        #print(self.execute_command(virtual_machine, "docker ps -a"))
        self.warmup(virtual_machine)

        command_line = self.get_commandline(virtual_machine)

        print(f"Commandline is {command_line}")

        output = self.execute_command(virtual_machine, "ps ax -o pid,ppid,cmd")

        # Split the output into lines, ignoring the header
        lines = output.splitlines()[1:]

        # Create a dictionary to store child-parent relationships
        process_tree = {}
        processes = []

        # Parse the output to fill the dictionary and list
        for line in lines:
            match = re.match(r'\s*(\d+)\s+(\d+)\s+(.+)', line)
            if match:
                pid, ppid, cmd = match.groups()
                pid, ppid = int(pid), int(ppid)
                processes.append((pid, ppid, cmd))
                if ppid not in process_tree:
                    process_tree[ppid] = []
                process_tree[ppid].append(pid)

        # Find the processes with the given command line
        target_pids = [pid for pid, _, cmd in processes if command_line in cmd]

        success = True

        for pid in target_pids:
            # Check if this process has any children
            if pid in process_tree:
                print(f"Process {pid} ('{command_line}') has the following children:")
                for child_pid in process_tree[pid]:
                    # Find the command line for the child process
                    child_cmd = next((cmd for child_pid_, _, cmd in processes if child_pid_ == child_pid), "")
                    print(f"  PID {child_pid}: {child_cmd}")
                    success = False
            else:
                print(f"Process {pid} ('{command_line}') has no children.")

        assert success


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
