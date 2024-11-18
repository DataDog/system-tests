import re
from utils import scenarios, features, flaky, irrelevant, context
from utils.tools import logger
from utils.onboarding.weblog_interface import warmup_weblog, get_child_pids, get_zombies, fork_and_crash
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
            {"vm_branch": "redhat", "vm_cpu": "arm64", "weblog_variant": "test-app-ruby", "reason": "INPLAT-103"},
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
@scenarios.installer_auto_injection
class TestContainerAutoInjectInstallScriptCrashTracking_NoZombieProcess(base.AutoInjectBaseTest):
    @parametrize_virtual_machines(
        bugs=[
            {"library": "ruby", "reason": "APMLP-312"},
            {"weblog_variant": "test-app-java-buildpack", "reason": "APMON-1595"},
            {"weblog_variant": "test-app-python-alpine", "reason": "APMLP-290"},
        ]
    )
    @irrelevant(
        context.weblog_variant
        not in [
            "test-app-java-container",
            "test-app-dotnet-container",
            "test-app-ruby-container",
            "test-app-python-container",
            "test-app-nodejs-container",
        ],
        reason="Zombies only appears in containers",
    )
    def test_crash_no_zombie(self, virtual_machine):
        vm_ip = virtual_machine.get_ip()
        vm_port = virtual_machine.deffault_open_port
        warmup_weblog(f"http://{vm_ip}:{vm_port}/")

        process_tree = self.execute_command(virtual_machine, "ps aux --forest")
        logger.info("Initial process tree: " + process_tree)

        child_pids = get_child_pids(virtual_machine).strip()

        if child_pids != "":
            logger.warning("Child PIDs found: " + child_pids)
            process_tree = self.execute_command(virtual_machine, "ps aux --forest")
            logger.warning("Failure process tree: " + process_tree)

        assert child_pids == ""

        try:
            crash_result = fork_and_crash(virtual_machine)
            logger.info("fork_and_crash: " + crash_result)
        except Exception as e:
            process_tree = self.execute_command(virtual_machine, "ps aux --forest")
            logger.warning("Failure process tree: " + process_tree)
            raise

        # At this point, there should be no zombies and no child pids
        child_pids = get_child_pids(virtual_machine).strip()

        if child_pids != "":
            logger.warning("Child PIDs found: " + child_pids)
            process_tree = self.execute_command(virtual_machine, "ps aux --forest")
            logger.warning("Failure process tree: " + process_tree)

        assert child_pids == ""

        zombies = get_zombies(virtual_machine).strip()

        if zombies != "":
            logger.warning("Zombies found: " + child_pids)
            process_tree = self.execute_command(virtual_machine, "ps aux --forest")
            logger.warning("Failure process tree: " + process_tree)

        assert zombies == ""


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
            {"vm_branch": "redhat", "vm_cpu": "arm64", "weblog_variant": "test-app-ruby", "reason": "INPLAT-103"},
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
            {"vm_branch": "redhat", "vm_cpu": "arm64", "weblog_variant": "test-app-ruby", "reason": "INPLAT-103"},
            {"weblog_variant": "test-app-nodejs-esm", "reason": "INPLAT-136"},
        ]
    )
    def test_install(self, virtual_machine):
        logger.info(
            f"Launching test_install for : [{virtual_machine.name}] [{virtual_machine.get_current_deployed_weblog().runtime_version}]..."
        )
        self._test_install(virtual_machine)
        logger.info(
            f"Done test_install for : [{virtual_machine.name}][{virtual_machine.get_current_deployed_weblog().runtime_version}]"
        )
