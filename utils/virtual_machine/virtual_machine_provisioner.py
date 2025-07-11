import os
import yaml
from yamlinclude import YamlIncludeConstructor
from utils._logger import logger
from utils.virtual_machine.utils import nginx_parser


class VirtualMachineProvisioner:
    """Manages the provision parser for the virtual machines."""

    def get_provision(self, library_name, env, weblog, vm_provision_name, os_type, os_distro, os_branch, os_cpu):
        """Parse the provision files (main provision file and weblog provision file) and return a Provision object"""

        YamlIncludeConstructor.add_to_loader_class(loader_class=yaml.FullLoader, base_dir=".")
        provision = Provision(vm_provision_name)
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
        # Load vm logs extractor installation
        provision.vm_logs_installation = self._get_vm_logs(
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
        installation.cache = provision_step.get("cache", False)
        installation.populate_env = provision_step.get("populate_env", True)
        return installation

    def _get_tested_components(self, env, library_name, os_type, os_distro, os_branch, os_cpu, provsion_raw_data):
        assert "tested_components" in provsion_raw_data, "tested_components is required"
        tested_components = provsion_raw_data["tested_components"]
        installations = tested_components["install"]
        installation = self._get_installation(env, library_name, os_type, os_distro, os_branch, os_cpu, installations)
        installation.id = "tested_components"
        return installation

    def _get_vm_logs(self, env, library_name, os_type, os_distro, os_branch, os_cpu, provsion_raw_data):
        if "vm_logs" in provsion_raw_data:
            tested_components = provsion_raw_data["vm_logs"]
            installations = tested_components["install"]
            installation = self._get_installation(
                env, library_name, os_type, os_distro, os_branch, os_cpu, installations
            )
            installation.id = "vm_logs"
            return installation
        return None

    def _get_lang_variant_provision(self, env, library_name, os_type, os_distro, os_branch, os_cpu, weblog_raw_data):
        if "lang_variant" not in weblog_raw_data:
            logger.debug("lang_variant not found in weblog provision file")
            return None
        lang_variant = weblog_raw_data["lang_variant"]
        installations = lang_variant["install"]
        installation = self._get_installation(env, library_name, os_type, os_distro, os_branch, os_cpu, installations)
        installation.id = lang_variant["name"]
        installation.cache = lang_variant.get("cache", False)
        installation.populate_env = lang_variant.get("populate_env", True)
        installation.version = lang_variant.get("version", None)
        return installation

    def _get_weblog_provision(
        self, env, library_name, weblog_name, os_type, os_distro, os_branch, os_cpu, weblog_raw_data
    ):
        assert "weblog" in weblog_raw_data, "weblog is required"
        weblog = weblog_raw_data["weblog"]
        assert weblog["name"] == weblog_name, f"Weblog name {weblog_name} does not match the provision file name"
        installations = weblog["install"]
        # Use GIT does not work for windows machines
        ci_commit_branch = os.getenv("GITLAB_CI") if os_type != "windows" else None
        installation = self._get_installation(
            env,
            library_name,
            os_type,
            os_distro,
            os_branch,
            os_cpu,
            installations,
            use_git=ci_commit_branch is not None,
        )
        installation.id = weblog["name"]
        installation.nginx_config = weblog.get("nginx_config", None)
        installation.version = weblog.get("runtime_version", None)
        return installation

    def _get_installation(
        self, env, library_name, os_type, os_distro, os_branch, os_cpu, installations_raw_data, *, use_git: bool = False
    ):
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
        installation.local_command = installation_raw_data.get("local-command", None)
        installation.local_script = installation_raw_data.get("local-script", None)
        installation.remote_command = installation_raw_data.get("remote-command", None)

        if "copy_files" in installation_raw_data:
            for copy_file in installation_raw_data["copy_files"]:
                installation.copy_files.append(
                    CopyFile(
                        copy_file["name"],
                        copy_file.get("remote_path", None),
                        copy_file["local_path"] if "local_path" in copy_file and not use_git else None,
                        copy_file["local_path"] if "local_path" in copy_file and use_git else None,
                    )
                )

        return installation


class _DeployedWeblog:
    def __init__(self, weblog_name, runtime_version=None, app_type=None, app_context_url="/") -> None:
        self.weblog_name = weblog_name
        self.runtime_version = runtime_version
        self.app_type = app_type
        self.app_context_url = app_context_url
        # The weblog is deployed as a multicontainer app
        self.multicontainer_apps = []


class Provision:
    """Contains all the information about the provision that it will be launched on the vm 1"""

    def __init__(self, provision_name):
        self.provision_name = provision_name
        self.env = {}
        self.installations = []
        self.lang_variant_installation = None
        self.weblog_installation = None
        self.tested_components_installation = None
        self.vm_logs_installation = None
        self.deployed_weblog = None

    def get_deployed_weblog(self):
        """Usually we have only one weblog deployed in the VM. But in some cases(multicontainer) we can have multiple
        weblogs deployed.
        """
        if not self.deployed_weblog:
            # App on Container/Alpine
            if self.weblog_installation and self.weblog_installation.version:
                self.deployed_weblog = _DeployedWeblog(
                    weblog_name=self.weblog_installation.id,
                    runtime_version=str(self.weblog_installation.version),
                    app_type="container" if "container" in self.weblog_installation.id else "alpine",
                    app_context_url="/",
                )

            # Multicontainer app
            elif self.weblog_installation and self.weblog_installation.nginx_config:
                # Define the main weblog as multicontainer
                self.deployed_weblog = _DeployedWeblog(
                    weblog_name=self.weblog_installation.id,
                    runtime_version=None,
                    app_type="multicontainer",
                    app_context_url="/",
                )
                # Now add the multicontainer apps
                apps_json = nginx_parser(self.weblog_installation.nginx_config)
                logger.debug(f"Multicontainer/multialpine apps definition: {apps_json}")

                for app in apps_json:
                    self.deployed_weblog.multicontainer_apps.append(
                        _DeployedWeblog(
                            weblog_name=self.weblog_installation.id,
                            runtime_version=str(app["runtime"]),
                            app_type=app["type"],
                            app_context_url=app["url"],
                        )
                    )
            # App on Host
            elif self.lang_variant_installation and self.lang_variant_installation.version:
                self.deployed_weblog = _DeployedWeblog(
                    weblog_name=self.weblog_installation.id,
                    runtime_version=str(self.lang_variant_installation.version),
                    app_type="host",
                    app_context_url="/",
                )
            else:
                # Assume the app is on host but the weblog provision doesn't have the lang_variant section
                self.deployed_weblog = _DeployedWeblog(
                    weblog_name=self.weblog_installation.id,
                    runtime_version="default",
                    app_type="host",
                    app_context_url="/",
                )

        return self.deployed_weblog


class Intallation:
    """Generic installation object. It can be a installation, lang_variant installation or weblog installation."""

    def __init__(self):
        self.id = False
        self.cache = False
        self.populate_env = True
        self.local_command = None
        self.local_script = None
        self.remote_command = None
        self.version = None
        self.nginx_config = None
        self.copy_files = []

    def __repr__(self):
        """We use this method to calculate the hash of the object (cache)"""
        return (
            self.id
            + "_"
            + (self.local_command or "")
            + "_"
            + (self.remote_command or "")
            + "_"
            + (self.local_script or "")
            + "_"
            + repr(self.copy_files)
        )


class CopyFile:
    def __init__(self, name, remote_path, local_path, git_path):
        self.remote_path = remote_path
        self.local_path = local_path
        self.git_path = git_path
        self.name = name

    def __repr__(self):
        """We use this method to calculate the hash of the object (cache)"""
        return (
            (self.remote_path or "")
            + "_"
            + (self.git_path if self.git_path else self.local_path or "")
            + "_"
            + self.name
        )


provisioner = VirtualMachineProvisioner()
