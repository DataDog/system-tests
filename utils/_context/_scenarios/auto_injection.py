import json
import glob
import os
import shutil
import subprocess

import pytest

from utils._context.library_version import LibraryVersion
from utils.tools import logger

from .core import Scenario, ScenarioGroup

from utils._context.virtual_machines import (
    Ubuntu22amd64,
    Ubuntu22arm64,
    Ubuntu18amd64,
    AmazonLinux2023arm64,
    AmazonLinux2023amd64,
    AmazonLinux2DotNet6,
    AmazonLinux2amd64,
    Centos7amd64,
)


class _VirtualMachineScenario(Scenario):
    """Scenario that tests virtual machines"""

    def __init__(
        self,
        name,
        github_workflow,
        doc,
        vm_provision=None,
        include_ubuntu_22_amd64=False,
        include_ubuntu_22_arm64=False,
        include_ubuntu_18_amd64=False,
        include_amazon_linux_2_amd64=False,
        include_amazon_linux_2_dotnet_6=False,
        include_amazon_linux_2023_amd64=False,
        include_amazon_linux_2023_arm64=False,
        include_centos_7_amd64=False,
        agent_env=None,
        app_env=None,
    ) -> None:
        super().__init__(name, doc=doc, github_workflow=github_workflow)
        self.vm_provision_name = vm_provision
        self.vm_provider_id = "vagrant"
        self.vm_provider = None
        self.required_vms = []
        self.required_vm_names = []
        self._tested_components = {}
        # Variables that will populate for the agent installation
        self.agent_env = agent_env
        # Variables that will populate for the app installation
        self.app_env = app_env

        if include_ubuntu_22_amd64:
            self.required_vms.append(Ubuntu22amd64())
        if include_ubuntu_22_arm64:
            self.required_vms.append(Ubuntu22arm64())
        if include_ubuntu_18_amd64:
            self.required_vms.append(Ubuntu18amd64())
        if include_amazon_linux_2_amd64:
            self.required_vms.append(AmazonLinux2amd64())
        if include_amazon_linux_2_dotnet_6:
            self.required_vms.append(AmazonLinux2DotNet6())
        if include_amazon_linux_2023_amd64:
            self.required_vms.append(AmazonLinux2023amd64())
        if include_amazon_linux_2023_arm64:
            self.required_vms.append(AmazonLinux2023arm64())
        if include_centos_7_amd64:
            self.required_vms.append(Centos7amd64())

    def session_start(self):
        super().session_start()
        self.fill_context()
        self.print_installed_components()

    def print_installed_components(self):
        logger.terminal.write_sep("=", "Installed components", bold=True)
        for component in self.components:
            logger.stdout(f"{component}: {self.components[component]}")

    def configure(self, config):
        from utils.virtual_machine.virtual_machine_provider import VmProviderFactory
        from utils.virtual_machine.virtual_machine_provisioner import provisioner

        super().configure(config)
        if config.option.vm_provider:
            self.vm_provider_id = config.option.vm_provider
        self._library = LibraryVersion(config.option.vm_library, "0.0")
        self._env = config.option.vm_env
        self._weblog = config.option.vm_weblog
        self._check_test_environment()
        self.vm_provider = VmProviderFactory().get_provider(self.vm_provider_id)

        provisioner.remove_unsupported_machines(
            self._library.library,
            self._weblog,
            self.required_vms,
            self.vm_provider_id,
            config.option.vm_only_branch,
            config.option.vm_skip_branches,
        )
        for vm in self.required_vms:
            logger.info(f"Adding provision for {vm.name}")
            vm.add_provision(
                provisioner.get_provision(
                    self._library.library,
                    self._env,
                    self._weblog,
                    self.vm_provision_name,
                    vm.os_type,
                    vm.os_distro,
                    vm.os_branch,
                    vm.os_cpu,
                )
            )
            vm.add_agent_env(self.agent_env)
            vm.add_app_env(self.app_env)
            self.required_vm_names.append(vm.name)
        self.vm_provider.configure(self.required_vms)

    def _check_test_environment(self):
        """Check if the test environment is correctly set"""

        assert self._library is not None, "Library is not set (use --vm-library)"
        assert self._env is not None, "Env is not set (use --vm-env)"
        assert self._weblog is not None, "Weblog is not set (use --vm-weblog)"
        assert os.path.isfile(
            f"utils/build/virtual_machine/weblogs/{self._library.library}/provision_{self._weblog}.yml"
        ), "Weblog Provision file not found."
        assert os.path.isfile(
            f"utils/build/virtual_machine/provisions/{self.vm_provision_name}/provision.yml"
        ), "Provision file not found"

        assert os.getenv("DD_API_KEY_ONBOARDING") is not None, "DD_API_KEY_ONBOARDING is not set"
        assert os.getenv("DD_APP_KEY_ONBOARDING") is not None, "DD_APP_KEY_ONBOARDING is not set"

    def _get_warmups(self):
        logger.terminal.write_sep("=", "Provisioning Virtual Machines", bold=True)
        return [self.vm_provider.stack_up]

    def fill_context(self):
        for vm in self.required_vms:
            for key in vm.tested_components:
                self._tested_components[key] = vm.tested_components[key].lstrip(" ")

    def pytest_sessionfinish(self, session):
        logger.info(f"Closing  _VirtualMachineScenario scenario")
        self.close_targets()

    def close_targets(self):
        logger.info(f"Destroying virtual machines")
        self.vm_provider.stack_destroy()

    @property
    def library(self):
        return self._library

    @property
    def weblog_variant(self):
        return self._weblog

    @property
    def components(self):
        return self._tested_components

    def customize_feature_parity_dashboard(self, result):
        for test in result["tests"]:
            last_index = test["path"].rfind("::") + 2
            test["description"] = test["path"][last_index:]


class HostAutoInjectionScenario(_VirtualMachineScenario):
    def __init__(self, name, doc, vm_provision="host-auto-inject", agent_env=None, app_env=None) -> None:
        super().__init__(
            name,
            vm_provision=vm_provision,
            agent_env=agent_env,
            app_env=app_env,
            doc=doc,
            github_workflow=None,
            include_ubuntu_22_amd64=True,
            include_ubuntu_22_arm64=True,
            include_ubuntu_18_amd64=True,
            include_amazon_linux_2_amd64=True,
            include_amazon_linux_2_dotnet_6=True,
            include_amazon_linux_2023_amd64=True,
            include_amazon_linux_2023_arm64=True,
        )


class ContainerAutoInjectionScenario(_VirtualMachineScenario):
    def __init__(self, name, doc, vm_provision="container-auto-inject", agent_env=None, app_env=None) -> None:
        super().__init__(
            name,
            vm_provision=vm_provision,
            agent_env=agent_env,
            app_env=app_env,
            doc=doc,
            github_workflow=None,
            include_ubuntu_22_amd64=True,
            include_ubuntu_22_arm64=True,
            include_ubuntu_18_amd64=True,
            include_amazon_linux_2_amd64=False,
            include_amazon_linux_2_dotnet_6=False,
            include_amazon_linux_2023_amd64=True,
            include_amazon_linux_2023_arm64=True,
        )


class InstallerAutoInjectionScenario(_VirtualMachineScenario):
    def __init__(self, name, doc, vm_provision="installer-auto-inject", agent_env=None, app_env=None) -> None:
        super().__init__(
            name,
            vm_provision=vm_provision,
            agent_env=agent_env,
            app_env=app_env,
            doc=doc,
            github_workflow=None,
            include_ubuntu_22_amd64=True,
            include_ubuntu_22_arm64=True,
            include_ubuntu_18_amd64=True,
            include_amazon_linux_2_amd64=True,
            include_amazon_linux_2_dotnet_6=True,
            include_amazon_linux_2023_amd64=True,
            include_amazon_linux_2023_arm64=True,
            include_centos_7_amd64=True,
        )
