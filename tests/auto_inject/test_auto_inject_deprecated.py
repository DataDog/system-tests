from utils import scenarios, features
from utils.tools import logger
from utils.onboarding.weblog_interface import make_get_request, warmup_weblog
from utils.onboarding.wait_for_tcp_port import wait_for_port
from utils import scenarios, features
import tests.auto_inject.utils as base
from tests.auto_inject.test_auto_inject_blocklist import TestAutoInjectBlockListInstallManualHost


class _AutoInjectDeprecatedNotSupportedBaseTest:
    """ Deprecated Test for not supported auto injection. We only check the app is working, although the auto injection is not performed."""

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


@features.host_guardrail
@scenarios.container_not_supported_auto_injection
class TestDeprecatedLanguageVersionNotSupported(_AutoInjectDeprecatedNotSupportedBaseTest):
    pass


class _TestBaseDeprecatedInstallerAutoInjectManual(base.AutoInjectBaseTest):
    # Note: uninstallation of a single installer package is not available today
    #  on the installer. As we can't only uninstall the injector, we are skipping
    #  the uninstall test today
    def test_install(self, virtual_machine):
        logger.info(f"Launching test_install for : [{virtual_machine.name}]...")
        self._test_install(virtual_machine)
        logger.info(f"Done test_install for : [{virtual_machine.name}]")

    def test_uninstall(self, virtual_machine):
        logger.info(f"Launching test_uninstall for : [{virtual_machine.name}]...")
        self._test_uninstall(virtual_machine)
        logger.info(f"Done test_uninstall for : [{virtual_machine.name}]...")


@features.installer_auto_instrumentation
@scenarios.host_auto_injection
class TestHostDeprecatedInstallerAutoInjectManual(_TestBaseDeprecatedInstallerAutoInjectManual):
    pass


@features.installer_auto_instrumentation
@scenarios.container_auto_injection
class TestContainerDeprecatedInstallerAutoInjectManual(_TestBaseDeprecatedInstallerAutoInjectManual):
    pass


@features.host_user_managed_block_list
@scenarios.host_auto_injection_block_list
class TestDeprecatedAutoInjectBlockListInstallManualHost(TestAutoInjectBlockListInstallManualHost):
    pass


@features.installer_auto_instrumentation
@scenarios.simple_host_auto_injection
class TestDeprecatedSimpleHostInstallerAutoInjectManual(base.AutoInjectBaseTest):
    # Note: uninstallation of a single installer package is not available today
    #  on the installer. As we can't only uninstall the injector, we are skipping
    #  the uninstall test today
    def test_install(self, virtual_machine):
        logger.info(f"Launching test_install for : [{virtual_machine.name}]...")
        self._test_install(virtual_machine)
        logger.info(f"Done test_install for : [{virtual_machine.name}]")


@features.installer_auto_instrumentation
@scenarios.simple_container_auto_injection
class TestDeprecatedSimpleContainerInstallerAutoInjectManual(base.AutoInjectBaseTest):
    # Note: uninstallation of a single installer package is not available today
    #  on the installer. As we can't only uninstall the injector, we are skipping
    #  the uninstall test today
    def test_install(self, virtual_machine):
        logger.info(f"Launching test_install for : [{virtual_machine.name}]...")
        self._test_install(virtual_machine)
        logger.info(f"Done test_install for : [{virtual_machine.name}]")


@features.host_auto_instrumentation_profiling
@scenarios.simple_host_auto_injection_profiling
class TestDeprecatedSimpleHostInstallerAutoInjectManualProfiling(base.AutoInjectBaseTest):
    def test_install(self, virtual_machine):
        logger.info(f"Launching test_install for : [{virtual_machine.name}]...")
        self._test_install(virtual_machine, profile=True)
        logger.info(f"Done test_install for : [{virtual_machine.name}]")


@features.host_auto_instrumentation_profiling
@scenarios.simple_container_auto_injection_profiling
class TestDeprecatedSimpleContainerInstallerAutoInjectManualProfiling(base.AutoInjectBaseTest):
    def test_install(self, virtual_machine):
        logger.info(f"Launching test_install for : [{virtual_machine.name}]...")
        self._test_install(virtual_machine, profile=True)
        logger.info(f"Done test_install for : [{virtual_machine.name}]")
