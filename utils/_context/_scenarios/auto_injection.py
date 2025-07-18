import copy
import json
import os
from pathlib import Path
import pytest
from utils._context.component_version import ComponentVersion
from utils._logger import logger
from utils.onboarding.debug_vm import download_vm_logs
from utils.virtual_machine.utils import get_tested_apps_vms
from utils.virtual_machine.virtual_machines import _VirtualMachine, load_virtual_machines
from .core import Scenario


class _VirtualMachineScenario(Scenario):
    """Scenario that tests virtual machines"""

    def __init__(
        self,
        name: str,
        *,
        github_workflow: str,
        doc: str,
        vm_provision=None,
        agent_env=None,
        app_env=None,
        scenario_groups=None,
    ) -> None:
        super().__init__(name, doc=doc, github_workflow=github_workflow, scenario_groups=scenario_groups)
        self.vm_provision_name = vm_provision
        self.vm_provider_id = "vagrant"
        self.vm_provider = None
        self.required_vms = []
        # Variables that will populate for the agent installation
        self.agent_env = agent_env
        # Variables that will populate for the app installation
        self.app_env = app_env
        self.only_default_vms = ""
        # Current selected vm for the scenario (set empty by default)
        self.virtual_machine = _VirtualMachine(
            name="",
            aws_config=None,
            vagrant_config=None,
            krunvm_config=None,
            os_type=None,
            os_distro=None,
            os_branch=None,
            os_cpu=None,
            default_vm=False,
        )

    def print_installed_components(self):
        logger.terminal.write_sep("=", "Installed components", bold=True)
        for component in self.components:
            logger.stdout(f"{component}: {self.components[component]}")
        # Check if the datadog-apm-library is installed.
        if "datadog-apm-library" not in self.components or not self.components["datadog-apm-library"]:
            logger.stdout("No datadog-apm-library found")
            logger.stdout("This is not a valid scenario")
            logger.stdout("Please, check the log file for more details")
            logger.stdout(f"Log file: {self.host_log_folder}/tests.log")
            raise ValueError("No datadog-apm-library found")

    def configure(self, config: pytest.Config):
        from utils.virtual_machine.virtual_machine_provider import VmProviderFactory
        from utils.virtual_machine.virtual_machine_provisioner import provisioner

        if config.option.vm_provider:
            self.vm_provider_id = config.option.vm_provider
        self._library = ComponentVersion(config.option.vm_library, "0.0")
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

        all_vms = load_virtual_machines(self.vm_provider_id)
        assert config.option.vm_only is not None, "No VM selected to run. Use --vm-only"
        self.virtual_machine = next((vm for vm in all_vms if vm.name == config.option.vm_only), None)
        assert self.virtual_machine is not None, f"VM not found: {config.option.vm_only}"
        logger.info(f"Selected VM: {self.virtual_machine.name}")
        self.vm_provider.configure(self.virtual_machine)
        self.virtual_machine.add_provision(
            provisioner.get_provision(
                self._library.name,
                self._env,
                self._weblog,
                self.vm_provision_name,
                self.virtual_machine.os_type,
                self.virtual_machine.os_distro,
                self.virtual_machine.os_branch,
                self.virtual_machine.os_cpu,
            )
        )
        self.virtual_machine.add_agent_env(self.agent_env)
        self.virtual_machine.add_app_env(self.app_env)

    def _check_test_environment(self):
        """Check if the test environment is correctly set"""

        assert self._library is not None, "Library is not set (use --vm-library)"
        assert self._env is not None, "Env is not set (use --vm-env)"
        assert self._weblog is not None, "Weblog is not set (use --vm-weblog)"

        base_folder = "utils/build/virtual_machine"
        weblog_provision_file = f"{base_folder}/weblogs/{self._library.name}/provision_{self._weblog}.yml"
        assert Path(weblog_provision_file).is_file(), f"Weblog Provision file not found: {weblog_provision_file}"

        provision_file = f"{base_folder}/provisions/{self.vm_provision_name}/provision.yml"
        assert Path(provision_file).is_file(), f"Provision file not found: {provision_file}"

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
        for key in self.virtual_machine.tested_components:
            if key in ("host", "runtime_version"):
                continue
            self.components[key] = self.virtual_machine.tested_components[key].lstrip(" ").replace(",", "")
            if key.startswith("datadog-apm-inject") and self.components[key]:
                self._datadog_apm_inject_version = f"v{self.components[key]}"
            if key.startswith("datadog-apm-library-") and self.components[key]:
                self._library = ComponentVersion(self._library.name, self.components[key])
                # We store without the lang sufix
                self.components["datadog-apm-library"] = self.components[key]
                del self.components[key]
            if key.startswith("glibc"):
                # We will all the glibc versions in the feature parity report, due to each machine can have a
                # different version
                del self.components[key]

    def pytest_sessionfinish(self, session, exitstatus):  # noqa: ARG002
        self.close_targets()

    def close_targets(self):
        if self.is_main_worker:
            # Extract logs from the VM before destroy
            download_vm_logs(
                vm=self.virtual_machine,
                remote_folder_paths=["/var/log/datadog", "/var/log/datadog_weblog", "/tmp/datadog/"],
                local_base_logs_folder=self.host_log_folder,
            )
            logger.info("Destroying virtual machines")
            self.vm_provider.stack_destroy()

    @property
    def library(self):
        return self._library

    @property
    def weblog_variant(self):
        return self._weblog

    @property
    def dd_apm_inject_version(self):
        return self._datadog_apm_inject_version

    @property
    def configuration(self):
        return self._os_configurations

    def customize_feature_parity_dashboard(self, result: dict):
        # Customize the general report
        for test in result["tests"]:
            last_index = test["path"].rfind("::") + 2
            test["description"] = test["path"][last_index:]

        # We are going to split the FPD report in multiple reports, one per VM-runtime
        vms, vm_ids = get_tested_apps_vms(self.virtual_machine)
        for i in range(len(vms)):
            vm = vms[i]
            vm_id = vm_ids[i]
            vm_name_clean = vm.name.replace("_amd64", "").replace("_arm64", "")
            new_result = copy.copy(result)
            new_tested_deps = result["testedDependencies"].copy()
            new_result["configuration"] = {"os": vm_name_clean, "arch": vm.os_cpu}
            new_result["configuration"]["app_type"] = vm.get_deployed_weblog().app_type
            if (
                self.virtual_machine.get_deployed_weblog().app_type == "host"
                and "runtime_version" in self.virtual_machine.tested_components
            ):
                new_result["configuration"]["runtime_version"] = (
                    self.virtual_machine.tested_components["runtime_version"].lstrip(" ").replace(",", "")
                )
            else:
                new_result["configuration"]["runtime_version"] = vm.get_deployed_weblog().runtime_version

            if "glibc" in vm.tested_components:
                new_tested_deps.append({"name": "glibc", "version": vm.tested_components["glibc"]})
                new_tested_deps.append({"name": "glibc_type", "version": vm.tested_components["glibc_type"]})
                new_result["testedDependencies"] = new_tested_deps

            new_result["tests"] = []
            for test in result["tests"]:
                new_test = test.copy()
                new_test["description"] = new_test["description"]
                new_test["path"] = new_test["path"]
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
        app_env_defaults = {
            "DD_TRACE_RATE_LIMIT": "1000000000000",
            "DD_TRACE_SAMPLING_RULES": "'[{\"sample_rate\":1}]'",
        }
        if app_env is not None:
            app_env_defaults.update(app_env)

        super().__init__(
            name,
            vm_provision=vm_provision,
            agent_env=agent_env,
            app_env=app_env_defaults,
            doc=doc,
            github_workflow=github_workflow,
            scenario_groups=scenario_groups,
        )
