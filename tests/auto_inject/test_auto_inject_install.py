import time
from utils import scenarios, features, flaky, irrelevant, bug, context, missing_feature, logger
from utils.onboarding.weblog_interface import warmup_weblog, get_child_pids, get_zombies, fork_and_crash
import tests.auto_inject.utils as base


@features.host_auto_installation_script
@scenarios.host_auto_injection_install_script
class TestHostAutoInjectInstallScript(base.AutoInjectBaseTest):
    @missing_feature(context.vm_os_branch == "windows", reason="Not implemented on Windows")
    def test_install(self):
        self._test_install(context.virtual_machine)


@features.host_auto_installation_script
@scenarios.local_auto_injection_install_script
class TestLocalAutoInjectInstallScript(base.AutoInjectBaseTest):
    def test_install(self):
        self._test_install(context.virtual_machine)


@features.auto_instrumentation_profiling
@scenarios.simple_auto_injection_profiling
class TestSimpleInstallerAutoInjectManualProfiling(base.AutoInjectBaseTest):
    @bug(
        context.vm_os_cpu == "arm64" and context.weblog_variant in ["test-app-dotnet", "test-app-dotnet-container"],
        reason="PROF-10783",
    )
    @irrelevant(
        context.vm_name in ["Ubuntu_24_amd64", "Ubuntu_24_arm64"] and context.weblog_variant == "test-app-nodejs",
        reason="PROF-11264",
    )
    def test_profiling(self):
        logger.info(f"Launching test_install for : [{context.vm_name}]...")
        self._test_install(context.virtual_machine, profile=True)
        logger.info(f"Done test_install for : [{context.vm_name}]")


@features.host_auto_installation_script_profiling
@scenarios.host_auto_injection_install_script_profiling
class TestHostAutoInjectInstallScriptProfiling(base.AutoInjectBaseTest):
    @bug(
        context.vm_os_cpu == "arm64" and context.weblog_variant == "test-app-dotnet",
        reason="PROF-10783",
    )
    @irrelevant(
        context.vm_name in ["Ubuntu_24_amd64", "Ubuntu_24_arm64"] and context.weblog_variant == "test-app-nodejs",
        reason="PROF-11264",
    )
    @missing_feature(context.vm_os_branch == "windows", reason="Not implemented on Windows")
    def test_profiling(self):
        logger.info(f"Launching test_install for : [{context.vm_name}]...")
        self._test_install(context.virtual_machine, profile=True)
        logger.info(f"Done test_install for : [{context.vm_name}]")


@features.container_auto_installation_script
@scenarios.container_auto_injection_install_script
class TestContainerAutoInjectInstallScript(base.AutoInjectBaseTest):
    def test_install(self):
        self._test_install(context.virtual_machine)


@features.container_auto_installation_script_profiling
@scenarios.container_auto_injection_install_script_profiling
class TestContainerAutoInjectInstallScriptProfiling(base.AutoInjectBaseTest):
    @bug(
        context.vm_os_cpu == "arm64" and context.weblog_variant == "test-app-dotnet-container",
        reason="PROF-10783",
    )
    def test_profiling(self):
        self._test_install(context.virtual_machine, profile=True)


@features.installer_auto_instrumentation
@scenarios.installer_auto_injection
@irrelevant(condition=context.weblog_variant == "test-app-dotnet-iis")
class TestContainerAutoInjectInstallScriptCrashTracking_NoZombieProcess(base.AutoInjectBaseTest):
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
    @flaky(library="python", reason="APMLP-313")
    def test_crash_no_zombie(self):
        virtual_machine = context.virtual_machine
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
        except Exception:
            process_tree = self.execute_command(virtual_machine, "ps aux --forest")
            logger.warning("Failure process tree: " + process_tree)
            raise

        # At this point, there should be no zombies and no child pids
        # but we apply a retry policy due to the app can take time to crash
        child_pids = ""
        for _attempt in range(5):
            child_pids = get_child_pids(virtual_machine).strip()

            if child_pids == "":
                break  # Success — exit the retry loop

            time.sleep(1)
        else:
            logger.warning("⚠️ Still getting non-empty child_pids after 5 attempts.")
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
    # on the installer. As we can not only uninstall the injector, we are skipping
    # the uninstall test today

    @irrelevant(condition=context.weblog_variant == "test-app-dotnet-iis")
    def test_install_uninstall(self):
        virtual_machine = context.virtual_machine
        logger.info(f"Launching test_install_uninstall for : [{virtual_machine.name}]...")
        logger.info(f"Check install for : [{virtual_machine.name}]")
        self._test_install(virtual_machine)
        logger.info(f"Check uninstall for : [{virtual_machine.name}]...")
        self._test_uninstall(virtual_machine)
        logger.info(f"Done test_install_uninstall for : [{virtual_machine.name}]...")

    @irrelevant(condition=context.weblog_variant != "test-app-dotnet-iis")
    def test_install(self):
        virtual_machine = context.virtual_machine
        logger.info(f"Launching test_install for : [{virtual_machine.name}]...")
        self._test_install(virtual_machine)
        logger.info(f"Done test_install for : [{virtual_machine.name}]...")


@features.installer_auto_instrumentation
@scenarios.simple_installer_auto_injection
@scenarios.multi_installer_auto_injection
class TestSimpleInstallerAutoInjectManual(base.AutoInjectBaseTest):
    @irrelevant(
        context.library > "python@2.21.0" and context.installed_language_runtime < "3.8.0",
        reason="python 3.7 is not supported on ddtrace >= 3.x",
    )
    def test_install(self):
        virtual_machine = context.virtual_machine
        logger.info(
            f"Launching test_install for : [{virtual_machine.name}] [{virtual_machine.get_deployed_weblog().runtime_version}]..."
        )
        self._test_install(virtual_machine)
        logger.info(
            f"Done test_install for : [{virtual_machine.name}][{virtual_machine.get_deployed_weblog().runtime_version}]"
        )


@features.auto_instrumentation_appsec
@scenarios.simple_auto_injection_appsec
class TestSimpleInstallerAutoInjectManualAppsec(base.AutoInjectBaseTest):
    def test_appsec(self):
        logger.info(f"Launching test_appsec for : [{context.vm_name}]...")
        self._test_install(context.virtual_machine, appsec=True)
        logger.info(f"Done test_appsec for : [{context.vm_name}]")


@features.host_auto_installation_script_appsec
@scenarios.host_auto_injection_install_script_appsec
class TestHostAutoInjectInstallScriptAppsec(base.AutoInjectBaseTest):
    @missing_feature(context.vm_os_branch == "windows", reason="Not implemented on Windows")
    def test_appsec(self):
        logger.info(f"Launching test_appsec for : [{context.vm_name}]...")
        self._test_install(context.virtual_machine, appsec=True)
        logger.info(f"Done test_appsec for : [{context.vm_name}]")


@features.container_auto_installation_script_appsec
@scenarios.container_auto_injection_install_script_appsec
class TestContainerAutoInjectInstallScriptAppsec(base.AutoInjectBaseTest):
    def test_appsec(self):
        self._test_install(context.virtual_machine, appsec=True)

@features.installer_auto_instrumentation
@scenarios.simple_ai_installer_auto_injection
class TestSimpleAIInstallerAutoInjectManual(base.AutoInjectBaseTest):
    def test_install(self):
        virtual_machine = context.virtual_machine
        logger.info(
            f"Launching test_install for : [{virtual_machine.name}]"
        )
        self._test_install(virtual_machine)
        logger.info(
            f"Done test_install for : [{virtual_machine.name}]"
        )