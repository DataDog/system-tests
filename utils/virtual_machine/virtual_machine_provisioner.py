import os
import yaml
from yamlinclude import YamlIncludeConstructor
from utils.tools import logger


class VirtualMachineProvisioner:
    def remove_unsupported_machines(self, library_name, weblog, required_vms):
        weblog_provision_file = f"utils/build/virtual_machine/weblogs/{library_name}/provision_{weblog}.yml"
        config_data = None
        with open(weblog_provision_file, encoding="utf-8") as f:
            config_data = yaml.load(f, Loader=yaml.FullLoader)
        vms_to_remove = []
        for vm in required_vms:
            installations = config_data["weblog"]["install"]
            allowed = False
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
                vms_to_remove.append(vm)
        # Ok remove the vms
        for vm in vms_to_remove:
            required_vms.remove(vm)

    def get_provision(self, library_name, env, weblog, vm_provision_name, os_type, os_distro, os_branch, os_cpu):
        YamlIncludeConstructor.add_to_loader_class(loader_class=yaml.FullLoader, base_dir=".")
        provision = Provision()
        provision_file = f"utils/build/virtual_machine/provisions/{vm_provision_name}/provision.yml"
        weblog_provision_file = f"utils/build/virtual_machine/weblogs/{library_name}/provision_{weblog}.yml"
        provsion_raw_data = None
        with open(provision_file, encoding="utf-8") as f:
            provsion_raw_data = yaml.load(f, Loader=yaml.FullLoader)
        assert provsion_raw_data is not None, "Provision file is empty"
        provision.env = self._get_env(env, library_name, provsion_raw_data)
        logger.info(f"Setting provision env [{ provision.env}]")
        provision.installations.append(
            self._get_components(env, library_name, os_type, os_distro, os_branch, os_cpu, provsion_raw_data)
        )

        return provision

    def _get_env(self, env, library_name, provsion_raw_data):
        provision_env = {"lang": library_name}
        if "init-environment" not in provsion_raw_data:
            return provision_env
        init_environment = provsion_raw_data["init-environment"]
        for env_data in init_environment:
            if env_data["env"] == env:
                for key in env_data:
                    provision_env[key] = env_data[key]
        return provision_env

    def _get_components(self, env, library_name, os_type, os_distro, os_branch, os_cpu, provsion_raw_data):
        assert "installed_components" in provsion_raw_data, "installed_components is required"
        installed_components = provsion_raw_data["installed_components"]
        installations = installed_components["install"]
        return self._get_installation(env, library_name, os_type, os_distro, os_branch, os_cpu, installations)

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
                    CopyFile(copy_file["remote_path"] if "remote_path" in copy_file else None, copy_file["local_path"])
                )
        logger.debug(f"RMM Setting provision installation [{ installation}]")

        return installation


class Provision:
    def __init__(self):
        self.env = {}
        self.installations = []


class Intallation:
    def __init__(self):
        self.local_command = None
        self.local_script = None
        self.remote_command = None
        self.copy_files = []

    def __str__(self):
        return f"local_command:{self.local_command} local_script:{self.local_script} remote_command:{self.remote_command} copy_files:{self.copy_files}"


class CopyFile:
    def __init__(self, remote_path, local_path):
        self.remote_path = remote_path
        self.local_path = local_path

    def __str__(self):
        return f"remote_path:{self.remote_path} local_path:{self.local_path}"


provisioner = VirtualMachineProvisioner()
