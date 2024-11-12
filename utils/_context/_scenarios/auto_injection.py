import os
import json
import copy
from utils._context.library_version import LibraryVersion
from utils.tools import logger
from utils.virtual_machine.utils import get_tested_apps_vms

from utils._context.virtual_machines import (
    Ubuntu20amd64,
    Ubuntu20arm64,
    Ubuntu21arm64,
    Ubuntu22amd64,
    Ubuntu22arm64,
    Ubuntu23_04_amd64,
    Ubuntu23_04_arm64,
    Ubuntu23_10_amd64,
    Ubuntu23_10_arm64,
    Ubuntu24amd64,
    Ubuntu24arm64,
    Ubuntu18amd64,
    AmazonLinux2022arm64,
    AmazonLinux2022amd64,
    AmazonLinux2023arm64,
    AmazonLinux2023amd64,
    AmazonLinux2amd64,
    AmazonLinux2arm64,
    Centos7amd64,
    Centos8amd64,
    OracleLinux92amd64,
    OracleLinux92arm64,
    OracleLinux88amd64,
    OracleLinux88arm64,
    OracleLinux79amd64,
    Debian12amd64,
    Debian12arm64,
    AlmaLinux8amd64,
    AlmaLinux8arm64,
    AlmaLinux9amd64,
    AlmaLinux9arm64,
    RedHat7_9amd64,
    RedHat86amd64,
    RedHat86arm64,
    RedHat90amd64,
    RedHat90arm64,
    Fedora36amd64,
    Fedora36arm64,
    Fedora37amd64,
    Fedora37arm64,
)

from .core import Scenario


class _VirtualMachineScenario(Scenario):
    """Scenario that tests virtual machines"""

    def __init__(
        self,
        name,
        github_workflow,
        doc,
        vm_provision=None,
        include_ubuntu_20_amd64=False,
        include_ubuntu_20_arm64=False,
        include_ubuntu_21_arm64=False,
        include_ubuntu_22_amd64=False,
        include_ubuntu_22_arm64=False,
        include_ubuntu_23_04_amd64=False,
        include_ubuntu_23_04_arm64=False,
        include_ubuntu_23_10_amd64=False,
        include_ubuntu_23_10_arm64=False,
        include_ubuntu_24_amd64=False,
        include_ubuntu_24_arm64=False,
        include_ubuntu_18_amd64=False,
        include_amazon_linux_2_amd64=False,
        include_amazon_linux_2_arm64=False,
        include_amazon_linux_2022_amd64=False,
        include_amazon_linux_2022_arm64=False,
        include_amazon_linux_2023_amd64=False,
        include_amazon_linux_2023_arm64=False,
        include_centos_7_amd64=False,
        include_centos_8_amd64=False,
        include_oraclelinux_9_2_amd64=False,
        include_oraclelinux_9_2_arm64=False,
        include_oraclelinux_8_8_amd64=False,
        include_oraclelinux_8_8_arm64=False,
        include_oraclelinux_7_9_amd64=False,
        include_debian_12_amd64=False,
        include_debian_12_arm64=False,
        include_almalinux_8_amd64=False,
        include_almalinux_8_arm64=False,
        include_almalinux_9_amd64=False,
        include_almalinux_9_arm64=False,
        include_redhat_7_9_amd64=False,
        include_redhat_8_amd64=False,
        include_redhat_8_arm64=False,
        include_redhat_9_amd64=False,
        include_redhat_9_arm64=False,
        include_fedora_36_amd64=False,
        include_fedora_36_arm64=False,
        include_fedora_37_amd64=False,
        include_fedora_37_arm64=False,
        agent_env=None,
        app_env=None,
        scenario_groups=None,
    ) -> None:
        super().__init__(name, doc=doc, github_workflow=github_workflow, scenario_groups=scenario_groups)
        self.vm_provision_name = vm_provision
        self.vm_provider_id = "vagrant"
        self.vm_provider = None
        self.required_vms = []
        self._tested_components = {}
        # Variables that will populate for the agent installation
        self.agent_env = agent_env
        # Variables that will populate for the app installation
        self.app_env = app_env
        self.only_default_vms = ""
        if include_ubuntu_20_amd64:
            self.required_vms.append(Ubuntu20amd64())
        if include_ubuntu_20_arm64:
            self.required_vms.append(Ubuntu20arm64())
        if include_ubuntu_21_arm64:
            self.required_vms.append(Ubuntu21arm64())
        if include_ubuntu_22_amd64:
            self.required_vms.append(Ubuntu22amd64())
        if include_ubuntu_22_arm64:
            self.required_vms.append(Ubuntu22arm64())
        if include_ubuntu_23_04_amd64:
            self.required_vms.append(Ubuntu23_04_amd64())
        if include_ubuntu_23_04_arm64:
            self.required_vms.append(Ubuntu23_04_arm64())
        if include_ubuntu_23_10_amd64:
            self.required_vms.append(Ubuntu23_10_amd64())
        if include_ubuntu_23_10_arm64:
            self.required_vms.append(Ubuntu23_10_arm64())
        if include_ubuntu_24_amd64:
            self.required_vms.append(Ubuntu24amd64())
        if include_ubuntu_24_arm64:
            self.required_vms.append(Ubuntu24arm64())
        if include_ubuntu_18_amd64:
            self.required_vms.append(Ubuntu18amd64())
        if include_amazon_linux_2022_amd64:
            self.required_vms.append(AmazonLinux2022amd64())
        if include_amazon_linux_2022_arm64:
            self.required_vms.append(AmazonLinux2022arm64())
        if include_amazon_linux_2_amd64:
            self.required_vms.append(AmazonLinux2amd64())
        if include_amazon_linux_2_arm64:
            self.required_vms.append(AmazonLinux2arm64())
        if include_amazon_linux_2023_amd64:
            self.required_vms.append(AmazonLinux2023amd64())
        if include_amazon_linux_2023_arm64:
            self.required_vms.append(AmazonLinux2023arm64())
        if include_centos_7_amd64:
            self.required_vms.append(Centos7amd64())
        if include_centos_8_amd64:
            self.required_vms.append(Centos8amd64())
        # Include Oracle Linux (not default vms)
        if include_oraclelinux_9_2_amd64:
            self.required_vms.append(OracleLinux92amd64())
        if include_oraclelinux_9_2_arm64:
            self.required_vms.append(OracleLinux92arm64())
        if include_oraclelinux_8_8_amd64:
            self.required_vms.append(OracleLinux88amd64())
        if include_oraclelinux_8_8_arm64:
            self.required_vms.append(OracleLinux88arm64())
        if include_oraclelinux_7_9_amd64:
            self.required_vms.append(OracleLinux79amd64())
        if include_debian_12_amd64:
            self.required_vms.append(Debian12amd64())
        if include_debian_12_arm64:
            self.required_vms.append(Debian12arm64())
        if include_almalinux_8_amd64:
            self.required_vms.append(AlmaLinux8amd64())
        if include_almalinux_8_arm64:
            self.required_vms.append(AlmaLinux8arm64())
        if include_almalinux_9_amd64:
            self.required_vms.append(AlmaLinux9amd64())
        if include_almalinux_9_arm64:
            self.required_vms.append(AlmaLinux9arm64())
        if include_redhat_7_9_amd64:
            self.required_vms.append(RedHat7_9amd64())
        if include_redhat_8_amd64:
            self.required_vms.append(RedHat86amd64())
        if include_redhat_8_arm64:
            self.required_vms.append(RedHat86arm64())
        if include_redhat_9_amd64:
            self.required_vms.append(RedHat90amd64())
        if include_redhat_9_arm64:
            self.required_vms.append(RedHat90arm64())
        if include_fedora_36_amd64:
            self.required_vms.append(Fedora36amd64())
        if include_fedora_36_arm64:
            self.required_vms.append(Fedora36arm64())
        if include_fedora_37_amd64:
            self.required_vms.append(Fedora37amd64())
        if include_fedora_37_arm64:
            self.required_vms.append(Fedora37arm64())

    def print_installed_components(self):
        logger.terminal.write_sep("=", "Installed components", bold=True)
        for component in self.components:
            logger.stdout(f"{component}: {self.components[component]}")

    def configure(self, config):
        from utils.virtual_machine.virtual_machine_provider import VmProviderFactory
        from utils.virtual_machine.virtual_machine_provisioner import provisioner

        if config.option.vm_provider:
            self.vm_provider_id = config.option.vm_provider
        self._library = LibraryVersion(config.option.vm_library, "0.0")
        self._datadog_apm_inject_version = "v0.00.00"
        self._os_configurations = {}
        self._env = config.option.vm_env
        self._weblog = config.option.vm_weblog
        self._check_test_environment()
        self.vm_provider = VmProviderFactory().get_provider(self.vm_provider_id)
        self.only_default_vms = config.option.vm_default_vms
        logger.info(f"Default vms policy: {self.only_default_vms}")
        if self.only_default_vms not in ["All", "True", "False"]:
            raise ValueError(
                f"Invalid value for --vm-default-vms: {self.only_default_vms}. Use 'All', 'True' or 'False'"
            )

        provisioner.remove_unsupported_machines(
            self._library.library,
            self._weblog,
            self.required_vms,
            self.vm_provider_id,
            config.option.vm_only_branch,
            config.option.vm_skip_branches,
            self.only_default_vms,
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
        self.vm_provider.configure(self.required_vms)

    def _check_test_environment(self):
        """Check if the test environment is correctly set"""

        assert self._library is not None, "Library is not set (use --vm-library)"
        assert self._env is not None, "Env is not set (use --vm-env)"
        assert self._weblog is not None, "Weblog is not set (use --vm-weblog)"

        base_folder = "utils/build/virtual_machine"
        weblog_provision_file = f"{base_folder}/weblogs/{self._library.library}/provision_{self._weblog}.yml"
        assert os.path.isfile(weblog_provision_file), f"Weblog Provision file not found: {weblog_provision_file}"

        provision_file = f"{base_folder}/provisions/{self.vm_provision_name}/provision.yml"
        assert os.path.isfile(provision_file), f"Provision file not found: {provision_file}"

        assert os.getenv("DD_API_KEY_ONBOARDING") is not None, "DD_API_KEY_ONBOARDING is not set"
        assert os.getenv("DD_APP_KEY_ONBOARDING") is not None, "DD_APP_KEY_ONBOARDING is not set"

    def get_warmups(self):
        warmups = super().get_warmups()

        if self.is_main_worker:
            warmups.append(lambda: logger.terminal.write_sep("=", "Provisioning Virtual Machines", bold=True))
            warmups.append(self.vm_provider.stack_up)

        warmups.append(self.fill_context)

        if self.is_main_worker:
            warmups.append(self.print_installed_components)

        return warmups

    def fill_context(self):
        for vm in self.required_vms:
            for key in vm.tested_components:
                if key == "host":
                    continue
                self._tested_components[key] = vm.tested_components[key].lstrip(" ").replace(",", "")
                if key.startswith("datadog-apm-inject") and self._tested_components[key]:
                    self._datadog_apm_inject_version = f"v{self._tested_components[key]}"
                if key.startswith("datadog-apm-library-") and self._tested_components[key]:
                    self._library.version = self._tested_components[key]
                    # We store without the lang sufix
                    self._tested_components["datadog-apm-library"] = self._tested_components[key]
                    del self._tested_components[key]
                if key.startswith("glibc"):
                    # We will all the glibc versions in the feature parity report, due to each machine can have a different version
                    del self._tested_components[key]

    def close_targets(self):
        if self.is_main_worker:
            logger.info("Destroying virtual machines")
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

    @property
    def dd_apm_inject_version(self):
        return self._datadog_apm_inject_version

    @property
    def configuration(self):
        return self._os_configurations

    def customize_feature_parity_dashboard(self, result):
        # Customize the general report
        for test in result["tests"]:
            last_index = test["path"].rfind("::") + 2
            test["description"] = test["path"][last_index:]

        # We are going to split the FPD report in multiple reports, one per VM-runtime
        vms, vm_ids = get_tested_apps_vms()
        for i in range(len(vms)):
            vm = vms[i]
            vm_id = vm_ids[i]
            vm_name_clean = vm.name.replace("_amd64", "").replace("_arm64", "")
            new_result = copy.copy(result)
            new_tested_deps = result["testedDependencies"].copy()
            new_result["configuration"] = {"os": vm_name_clean, "arch": vm.os_cpu}
            new_result["configuration"]["runtime_version"] = vm.get_current_deployed_weblog().runtime_version
            new_result["configuration"]["app_type"] = vm.get_current_deployed_weblog().app_type
            if "glibc" in vm.tested_components:
                new_tested_deps.append({"name": "glibc", "version": vm.tested_components["glibc"]})
                new_tested_deps.append({"name": "glibc_type", "version": vm.tested_components["glibc_type"]})
                new_result["testedDependencies"] = new_tested_deps

            new_result["tests"] = []
            for test in result["tests"]:
                if vm_id in test["description"]:
                    new_test = test.copy()
                    new_test["description"] = new_test["description"].split("[", 1)[0]
                    new_test["path"] = new_test["path"].split("[", 1)[0]
                    new_result["tests"].append(new_test)
            with open(f"{self.host_log_folder}/{vm_id}_feature_parity.json", "w", encoding="utf-8") as f:
                json.dump(new_result, f, indent=2)


class InstallerAutoInjectionScenario(_VirtualMachineScenario):
    def __init__(
        self,
        name,
        doc,
        vm_provision="installer-auto-inject",
        agent_env=None,
        app_env=None,
        scenario_groups=None,
        github_workflow=None,
    ) -> None:
        # Force full tracing without limits
        app_env_defaults = {"DD_TRACE_RATE_LIMIT": "1000000000000", "DD_TRACE_SAMPLING_RULES": "[{'sample_rate':1}]", "DD_TRACE_DEBUG": "true"}
        if app_env is not None:
            app_env_defaults.update(app_env)

        super().__init__(
            name,
            vm_provision=vm_provision,
            agent_env=agent_env,
            app_env=app_env_defaults,
            doc=doc,
            github_workflow=github_workflow,
            include_ubuntu_20_amd64=True,
            include_ubuntu_20_arm64=True,
            include_ubuntu_21_arm64=True,
            include_ubuntu_22_amd64=True,
            include_ubuntu_22_arm64=True,
            include_ubuntu_23_04_amd64=True,
            include_ubuntu_23_04_arm64=True,
            include_ubuntu_23_10_amd64=True,
            include_ubuntu_23_10_arm64=True,
            include_ubuntu_24_amd64=True,
            include_ubuntu_24_arm64=True,
            include_ubuntu_18_amd64=False,
            include_amazon_linux_2_amd64=True,
            include_amazon_linux_2_arm64=True,
            include_amazon_linux_2022_amd64=True,
            include_amazon_linux_2022_arm64=True,
            include_amazon_linux_2023_amd64=True,
            include_amazon_linux_2023_arm64=True,
            include_centos_7_amd64=True,
            include_centos_8_amd64=True,
            include_oraclelinux_9_2_amd64=False,
            include_oraclelinux_9_2_arm64=False,
            include_oraclelinux_8_8_amd64=False,
            include_oraclelinux_8_8_arm64=False,
            include_oraclelinux_7_9_amd64=False,
            include_debian_12_amd64=True,
            include_debian_12_arm64=True,
            include_almalinux_8_amd64=False,
            include_almalinux_8_arm64=False,
            include_almalinux_9_amd64=False,
            include_almalinux_9_arm64=False,
            include_redhat_7_9_amd64=True,
            include_redhat_8_amd64=True,
            include_redhat_8_arm64=True,
            include_redhat_9_amd64=True,
            include_redhat_9_arm64=True,
            include_fedora_36_amd64=False,
            include_fedora_36_arm64=False,
            include_fedora_37_amd64=False,
            include_fedora_37_arm64=False,
            scenario_groups=scenario_groups,
        )


class InstallerAutoInjectionScenarioProfiling(_VirtualMachineScenario):
    """ As Profiling is not included in GA (2024/11) we reduce the number of VMS to speed up the execution 
    Until we fix the performance problems on the AWS architecture and speed up the tests"""

    def __init__(
        self,
        name,
        doc,
        vm_provision="installer-auto-inject",
        agent_env=None,
        app_env=None,
        scenario_groups=None,
        github_workflow=None,
    ) -> None:
        # Force full tracing without limits
        app_env_defaults = {"DD_TRACE_RATE_LIMIT": "1000000000000", "DD_TRACE_SAMPLING_RULES": "[{'sample_rate':1}]", "DD_TRACE_DEBUG": "true"}
        if app_env is not None:
            app_env_defaults.update(app_env)

        super().__init__(
            name,
            vm_provision=vm_provision,
            agent_env=agent_env,
            app_env=app_env_defaults,
            doc=doc,
            github_workflow=github_workflow,
            include_ubuntu_22_amd64=True,
            include_ubuntu_22_arm64=True,
            include_amazon_linux_2_amd64=True,
            include_amazon_linux_2_arm64=True,
            include_amazon_linux_2023_amd64=True,
            include_amazon_linux_2023_arm64=True,
            include_redhat_7_9_amd64=True,
            include_redhat_8_amd64=True,
            include_redhat_8_arm64=True,
            include_redhat_9_amd64=True,
            include_redhat_9_arm64=True,
            scenario_groups=scenario_groups,
        )
