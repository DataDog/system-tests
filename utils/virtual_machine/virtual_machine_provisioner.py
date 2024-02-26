import os
import yaml
from yamlinclude import YamlIncludeConstructor
from utils.tools import logger


class VirtualMachineProvisioner:
    """ Manages the provision parser for the virtual machines."""

    def remove_unsupported_machines(
        self, library_name, weblog, required_vms, vm_provider_id, vm_only_branch, vm_skip_branches
    ):
        """ Remove unsupported machines based on the provision file, weblog, provider_id and local testing parameter: vm_only_branch  """

        weblog_provision_file = f"utils/build/virtual_machine/weblogs/{library_name}/provision_{weblog}.yml"
        config_data = None
        with open(weblog_provision_file, encoding="utf-8") as f:
            config_data = yaml.load(f, Loader=yaml.FullLoader)
        vms_to_remove = []

        # Skipped branches seted by the user parameter
        skipped_branches = []
        if vm_skip_branches:
            skipped_branches = vm_skip_branches.split(",")

        for vm in required_vms:
            installations = config_data["weblog"]["install"]
            allowed = False
            # Exclude by vm_only_branch
            if vm_only_branch and vm.os_branch != vm_only_branch:
                logger.stdout(f"WARNING: Removed VM [{vm.name}] due to vm_only_branch directive")
                vms_to_remove.append(vm)
                continue
            # Exclude by vm_skip_branches
            if vm_skip_branches and vm.os_branch in skipped_branches:
                logger.stdout(f"WARNING: Removed VM [{vm.name}] due to vm_skip_branches directive")
                vms_to_remove.append(vm)
                continue

            # Exclude by excluded_os_branches
            if (
                "excluded_os_branches" in config_data["weblog"]
                and vm.os_branch in config_data["weblog"]["excluded_os_branches"]
            ):
                logger.stdout(f"WARNING: Removed VM [{vm.name}] due to weblog directive in excluded_os_branches")
                vms_to_remove.append(vm)
                continue
            # Exlude by vm_provider_id and vm configuration. IE: vm_provider_id: vagrant exclude all vms that don't have vagrant configuration
            if vm_provider_id == "vagrant" and vm.vagrant_config is None:
                logger.stdout(f"WARNING: Removed VM [{vm.name}] due to it's not a Vagrant VM")
                vms_to_remove.append(vm)
                continue
            if vm_provider_id == "aws" and vm.aws_config is None:
                logger.stdout(f"WARNING: Removed VM [{vm.name}] due to it's not a AWS VM")
                vms_to_remove.append(vm)
                continue

            # Exclude by vm fields: os_distro, os_branch, os_cpu
            for installation in installations:
                assert "os_type" in installation, "os_type is required for weblog installation"
                if installation["os_type"] == vm.os_type:
                    allowed = True
                    if "os_distro" in installation and installation["os_distro"] != vm.os_distro:
                        allowed = False
                        continue
                    if "os_branch" in installation and installation["os_branch"] != vm.os_branch:
                        allowed = False
                        continue
                    if "os_cpu" in installation and installation["os_cpu"] != vm.os_cpu:
                        allowed = False
                        continue
                    if allowed == True:
                        break
            if allowed == False:
                logger.stdout(f"WARNING: Weblog doesn't support VM [{vm.name}]. Removed!")
                vms_to_remove.append(vm)
        # Ok remove the vms
        for vm in vms_to_remove:
            required_vms.remove(vm)

    def get_provision(self, library_name, env, weblog, vm_provision_name, os_type, os_distro, os_branch, os_cpu):
        """ Parse the provision files (main provision file and weblog provision file) and return a Provision object"""

        YamlIncludeConstructor.add_to_loader_class(loader_class=yaml.FullLoader, base_dir=".")
        provision = Provision()
        provision_file = f"utils/build/virtual_machine/provisions/{vm_provision_name}/provision.yml"
        weblog_provision_file = f"utils/build/virtual_machine/weblogs/{library_name}/provision_{weblog}.yml"

        provsion_raw_data = None
        with open(provision_file, encoding="utf-8") as f:
            provsion_raw_data = yaml.load(f, Loader=yaml.FullLoader)
        assert provsion_raw_data is not None, "Provision file is empty"

        weblog_raw_data = None
        with open(weblog_provision_file, encoding="utf-8") as f:
            weblog_raw_data = yaml.load(f, Loader=yaml.FullLoader)
        assert weblog_raw_data is not None, "Weblog provision file is empty"
        # Get environtment variables to be injected in the remote commands
        provision.env = self._get_env(env, library_name, provsion_raw_data)
        # Load all custom defined provision steps
        for provision_step in self.get_provision_steps(provsion_raw_data):
            provision.installations.append(
                self._get_provision_step(
                    env, library_name, os_type, os_distro, os_branch, os_cpu, provsion_raw_data, provision_step
                )
            )
        # Load tested components installation
        provision.tested_components_installation = self._get_tested_components(
            env, library_name, os_type, os_distro, os_branch, os_cpu, provsion_raw_data
        )
        # Load lang variant installation if exists. Lang variant is denfined in the weblog provision file
        provision.lang_variant_installation = self._get_lang_variant_provision(
            env, library_name, os_type, os_distro, os_branch, os_cpu, weblog_raw_data
        )
        # Load weblog installation
        provision.weblog_installation = self._get_weblog_provision(
            env, library_name, weblog, os_type, os_distro, os_branch, os_cpu, weblog_raw_data
        )
        return provision

    def _get_env(self, env, library_name, provsion_raw_data):
        provision_env = {"LANG": library_name}
        if "init-environment" not in provsion_raw_data:
            return provision_env
        init_environment = provsion_raw_data["init-environment"]
        for env_data in init_environment:
            if env_data["env"] == env:
                for key in env_data:
                    provision_env[key] = env_data[key]
        return provision_env

    def get_provision_steps(self, provsion_raw_data):
        assert "provision_steps" in provsion_raw_data, "provision_steps is required"
        return provsion_raw_data["provision_steps"]

    def _get_provision_step(
        self, env, library_name, os_type, os_distro, os_branch, os_cpu, provsion_raw_data, step_name
    ):
        assert step_name in provsion_raw_data, f"{step_name} is required"
        provision_step = provsion_raw_data[step_name]
        installations = provision_step["install"]
        installation = self._get_installation(env, library_name, os_type, os_distro, os_branch, os_cpu, installations)
        installation.id = step_name
        installation.cache = provision_step["cache"] if "cache" in provision_step else False
        return installation

    def _get_tested_components(self, env, library_name, os_type, os_distro, os_branch, os_cpu, provsion_raw_data):
        assert "tested_components" in provsion_raw_data, "tested_components is required"
        tested_components = provsion_raw_data["tested_components"]
        installations = tested_components["install"]
        installation = self._get_installation(env, library_name, os_type, os_distro, os_branch, os_cpu, installations)
        installation.id = "tested_components"
        return installation

    def _get_lang_variant_provision(self, env, library_name, os_type, os_distro, os_branch, os_cpu, weblog_raw_data):
        if "lang_variant" not in weblog_raw_data:
            logger.debug(f"lang_variant not found in weblog provision file")
            return None
        lang_variant = weblog_raw_data["lang_variant"]
        installations = lang_variant["install"]
        installation = self._get_installation(env, library_name, os_type, os_distro, os_branch, os_cpu, installations)
        installation.id = lang_variant["name"]
        installation.cache = lang_variant["cache"] if "cache" in lang_variant else False
        return installation

    def _get_weblog_provision(
        self, env, library_name, weblog_name, os_type, os_distro, os_branch, os_cpu, weblog_raw_data
    ):
        assert "weblog" in weblog_raw_data, "weblog is required"
        weblog = weblog_raw_data["weblog"]
        assert weblog["name"] == weblog_name, f"Weblog name {weblog_name} does not match the provision file name"
        installations = weblog["install"]
        installation = self._get_installation(env, library_name, os_type, os_distro, os_branch, os_cpu, installations)
        installation.id = weblog["name"]
        return installation

    def _get_installation(self, env, library_name, os_type, os_distro, os_branch, os_cpu, installations_raw_data):
        installation_raw_data = None
        for install in installations_raw_data:
            if "env" in install and install["env"] != env:
                continue
            if "lang" in install and install["lang"] != library_name:
                continue
            if "os_cpu" in install and install["os_cpu"] != os_cpu:
                continue
            if install["os_type"] == os_type:
                if "os_distro" in install and install["os_distro"] != os_distro:
                    continue
                if "os_branch" in install and install["os_branch"] != os_branch:
                    continue
                installation_raw_data = install
                break
        assert (
            installation_raw_data is not None
        ), f"Installation data not found for {env} {library_name} {os_type} {os_distro} {os_branch} {os_cpu}"
        installation = Intallation()
        installation.local_command = (
            installation_raw_data["local-command"] if "local-command" in installation_raw_data else None
        )
        installation.local_script = (
            installation_raw_data["local-script"] if "local-script" in installation_raw_data else None
        )
        installation.remote_command = (
            installation_raw_data["remote-command"] if "remote-command" in installation_raw_data else None
        )
        if "copy_files" in installation_raw_data:
            for copy_file in installation_raw_data["copy_files"]:
                installation.copy_files.append(
                    CopyFile(
                        copy_file["name"],
                        copy_file["remote_path"] if "remote_path" in copy_file else None,
                        copy_file["local_path"],
                    )
                )

        return installation


class Provision:
    """ Contains all the information about the provision that it will be launched on the vm 1"""

    def __init__(self):
        self.env = {}
        self.installations = []
        self.lang_variant_installation = None
        self.weblog_installation = None
        self.tested_components_installation = None


class Intallation:
    """ Generic installation object. It can be a installation, lang_variant installation or weblog installation."""

    def __init__(self):
        self.id = False
        self.cache = False
        self.local_command = None
        self.local_script = None
        self.remote_command = None
        self.copy_files = []


class CopyFile:
    def __init__(self, name, remote_path, local_path):
        self.remote_path = remote_path
        self.local_path = local_path
        self.name = name


provisioner = VirtualMachineProvisioner()
